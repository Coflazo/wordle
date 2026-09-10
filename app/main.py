"""FastAPI entrypoint: mounts API routes and serves the frontend."""

from __future__ import annotations

import logging
import time
from collections import defaultdict, deque
from contextlib import asynccontextmanager
from typing import Deque, Dict

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from app import config
from app.database import init_db
from app.errors import ApiError
from app.routes import experiments, games, meanings, profiles, stats
from app.services import solverd_client, word_service

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-7s %(name)s: %(message)s",
)
log = logging.getLogger("wordle")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown. `on_event` is deprecated in current FastAPI."""
    init_db()
    # Open every bank now so a missing or stale one is a startup failure with a
    # build instruction, not a 503 in the middle of someone's game.
    word_service.warm_up()
    if solverd_client.ping():
        log.info("solverd is up; hints will use the sidecar")
    else:
        log.info("solverd is not running; hints will be answered in-process")
    yield


app = FastAPI(title="Oflaz Wordle", version="1.0.0", lifespan=lifespan)

if config.CORS_ORIGINS:
    # Default is no CORS middleware at all, because the frontend is served from
    # this same origin. The previous setting paired allow_origins=["*"] with
    # allow_credentials=True — invalid per the Fetch spec, and it meant any site
    # the player visited could read and delete their profiles.
    app.add_middleware(
        CORSMiddleware,
        allow_origins=config.CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PATCH", "PUT", "DELETE"],
        allow_headers=["Content-Type"],
    )


_hits: Dict[str, Deque[float]] = defaultdict(deque)


@app.middleware("http")
async def rate_limit(request: Request, call_next):
    """A cheap per-client ceiling on API calls.

    Not a security boundary — this is a local app. It stops a runaway loop in
    the frontend from filling the events table or hammering an upstream
    dictionary, which is the failure this has actually seen.
    """
    if not request.url.path.startswith("/api/"):
        return await call_next(request)

    client = request.client.host if request.client else "local"
    now = time.monotonic()
    window = _hits[client]
    while window and now - window[0] > 60.0:
        window.popleft()
    if len(window) >= config.RATE_LIMIT_PER_MINUTE:
        return JSONResponse(
            status_code=429,
            content={
                "detail": {
                    "code": "rate_limited",
                    "message": "too many requests; slow down",
                    "params": {"limit_per_minute": config.RATE_LIMIT_PER_MINUTE},
                }
            },
            headers={"Retry-After": "10"},
        )
    window.append(now)
    return await call_next(request)


@app.exception_handler(Exception)
async def unhandled(request: Request, exc: Exception):
    """Log the traceback and return a coded error.

    There was no handler and no logging at all before, so an unexpected failure
    was an opaque 500 with nothing written down anywhere.
    """
    log.exception("unhandled error on %s %s", request.method, request.url.path)
    return JSONResponse(
        status_code=500,
        content={
            "detail": {
                "code": "internal_error",
                "message": "something went wrong on the server",
                "params": {},
            }
        },
    )


@app.get("/api/ping")
def ping():
    return {
        "ok": True,
        "service": "oflaz-wordle",
        "version": app.version,
        "solverd": solverd_client.ping(),
    }


app.include_router(profiles.router)
app.include_router(games.router)
app.include_router(meanings.router)
app.include_router(stats.router)
app.include_router(experiments.router)


class _CachedStatic(StaticFiles):
    """Static files with a short revalidating cache.

    No cache headers were configured at all, so every navigation refetched the
    whole CSS and JS set. `must-revalidate` keeps edits visible immediately
    during development while still allowing a conditional request.
    """

    def file_response(self, *args, **kwargs):
        response = super().file_response(*args, **kwargs)
        response.headers["Cache-Control"] = "public, max-age=0, must-revalidate"
        return response


for mount, folder in (("/css", "css"), ("/js", "js"), ("/assets", "assets")):
    directory = config.FRONTEND_DIR / folder
    if directory.exists():
        app.mount(mount, _CachedStatic(directory=directory), name=folder)


def _page(name: str) -> FileResponse:
    path = config.FRONTEND_DIR / name
    if not path.exists():
        raise ApiError(500, "frontend_missing", f"{name} is missing from {config.FRONTEND_DIR}")
    return FileResponse(path)


@app.get("/sw.js", include_in_schema=False)
def service_worker():
    """Served from the root, not /js/, so its scope covers every page.

    A worker registered from /js/sw.js could only control /js/*.
    """
    response = FileResponse(config.FRONTEND_DIR / "sw.js", media_type="application/javascript")
    # Never cache the worker itself, or a broken one becomes permanent.
    response.headers["Cache-Control"] = "no-cache"
    return response


@app.get("/", include_in_schema=False)
def welcome_page():
    return _page("index.html")


@app.get("/game", include_in_schema=False)
def game_page():
    return _page("game.html")


@app.get("/profile", include_in_schema=False)
def profile_page():
    return _page("profile.html")
