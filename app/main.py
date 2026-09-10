"""FastAPI entrypoint: mounts API routes and serves the frontend."""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.database import init_db
from app.routes import games, meanings, profiles, stats

app = FastAPI(title="Oflaz Wordle", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def _startup() -> None:
    init_db()


@app.get("/api/ping")
def ping():
    return {"ok": True, "service": "oflaz-wordle"}


app.include_router(profiles.router)
app.include_router(games.router)
app.include_router(meanings.router)
app.include_router(stats.router)


FRONTEND_DIR = Path(__file__).resolve().parent.parent / "frontend"


# Static assets, css, js
if (FRONTEND_DIR / "css").exists():
    app.mount("/css", StaticFiles(directory=FRONTEND_DIR / "css"), name="css")
if (FRONTEND_DIR / "js").exists():
    app.mount("/js", StaticFiles(directory=FRONTEND_DIR / "js"), name="js")
if (FRONTEND_DIR / "assets").exists():
    app.mount(
        "/assets", StaticFiles(directory=FRONTEND_DIR / "assets"), name="assets"
    )


@app.get("/")
def welcome_page():
    return FileResponse(FRONTEND_DIR / "index.html")


@app.get("/game")
def game_page():
    return FileResponse(FRONTEND_DIR / "game.html")


@app.get("/profile")
def profile_page():
    return FileResponse(FRONTEND_DIR / "profile.html")
