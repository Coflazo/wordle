"""Runtime configuration. Every value has a working default; nothing is required."""

from __future__ import annotations

import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

DATA_DIR = ROOT / "app" / "data"
BANK_DIR = Path(os.environ.get("WORDLE_BANKS", DATA_DIR / "banks"))
FRONTEND_DIR = ROOT / "frontend"
RUN_DIR = Path(os.environ.get("WORDLE_RUN_DIR", ROOT / "run"))

DB_URL = os.environ.get("WORDLE_DB_URL", f"sqlite:///{ROOT / 'oflaz_wordle.db'}")

SOLVERD_SOCKET = Path(os.environ.get("WORDLE_SOLVERD_SOCKET", RUN_DIR / "solverd.sock"))
SOLVERD_TIMEOUT = float(os.environ.get("WORDLE_SOLVERD_TIMEOUT", "5.0"))
# When solverd is not running, hints are answered in-process by wordle_core.
# Slower on the first turn and without the candidate cache, but never a 503.
SOLVERD_FALLBACK = os.environ.get("WORDLE_SOLVERD_FALLBACK", "1") != "0"

LANGUAGES = ("en", "tr", "de")
DIFFICULTIES = ("chill", "classic", "scholar")

# Which word tiers each difficulty draws answers from. This is what makes the
# difficulty selector real — it previously changed nothing but the attempt count,
# while the UI advertised "rarer words".
TIERS_BY_DIFFICULTY = {
    "chill": ("common",),
    "classic": ("common", "standard"),
    "scholar": ("standard", "rare"),
}

ATTEMPTS_BY_LENGTH = {5: 6, 6: 7, 7: 7, 8: 8, 9: 8, 10: 9}
CHILL_BONUS_ATTEMPTS = 1
MAX_ATTEMPTS = max(ATTEMPTS_BY_LENGTH.values()) + CHILL_BONUS_ATTEMPTS

# Weighted draw when the player picks "Mix" rather than a specific length.
LENGTH_DISTRIBUTION = {5: 0.35, 6: 0.25, 7: 0.15, 8: 0.10, 9: 0.08, 10: 0.07}

# Dictionary lookups are cached in SQLite. A hit is cached indefinitely; a miss
# expires, so one upstream outage does not poison a word forever.
DICTIONARY_TTL_HIT_DAYS = 365
DICTIONARY_TTL_MISS_HOURS = 6
DICTIONARY_TIMEOUT = float(os.environ.get("WORDLE_DICT_TIMEOUT", "8.0"))

# Same-origin by default. Set WORDLE_CORS_ORIGINS to a comma-separated list only
# if you are serving the frontend from somewhere else. The previous setting was
# allow_origins=["*"] together with allow_credentials=True, which is invalid per
# the Fetch spec and meant any page the player visited could delete their data.
CORS_ORIGINS = [o for o in os.environ.get("WORDLE_CORS_ORIGINS", "").split(",") if o]

RATE_LIMIT_PER_MINUTE = int(os.environ.get("WORDLE_RATE_LIMIT", "240"))
DEBUG_ENDPOINTS = os.environ.get("WORDLE_DEBUG", "0") == "1"

MAX_AVATAR_CONFIG_BYTES = 4096
MAX_PROFILE_NAME = 64
MAX_EVENTS_PER_BATCH = 50
