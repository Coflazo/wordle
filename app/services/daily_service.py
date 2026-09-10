"""The daily puzzle.

One word per (date, language, length), derived from the date rather than stored.
Two people who have never spoken get the same word on the same day, and a device
that has been offline for a week can still work out what yesterday's word was.

The seed goes through the C++ `pick(seed=)` path, which walks the tier-filtered
target list deterministically, so the same seed always lands on the same word
even as the bank grows — as long as the bank version is unchanged, which is why
the format version is part of the seed.
"""

from __future__ import annotations

import hashlib
from datetime import date, datetime, timedelta, timezone
from typing import Dict, Optional

import wordle_core as wc

from app import config
from app.services import word_service

# The daily puzzle is a fixed shape so results are comparable.
DAILY_LENGTH = 5
DAILY_DIFFICULTY = "classic"

# Day zero. Puzzle numbering counts from here.
EPOCH = date(2026, 1, 1)


def today(tz_offset_minutes: int = 0) -> date:
    """The player's local date.

    Offset comes from the browser rather than the server clock: a phone in
    Istanbul and a laptop in Amsterdam should roll over to the next puzzle at
    their own midnights, not at the server's.
    """
    now = datetime.now(timezone.utc) + timedelta(minutes=tz_offset_minutes)
    return now.date()


def puzzle_number(day: date) -> int:
    return (day - EPOCH).days


def seed_for(day: date, language: str, length: int) -> int:
    """A stable 64-bit seed. Hashed so consecutive days are unrelated."""
    material = f"oflaz-wordle:v{wc.FORMAT_VERSION}:{day.isoformat()}:{language}:{length}"
    digest = hashlib.sha256(material.encode("utf-8")).digest()
    # Never 0: the native pick() treats 0 as "draw fresh".
    return int.from_bytes(digest[:8], "big") | 1


def word_for(day: date, language: str, length: int = DAILY_LENGTH) -> Optional[str]:
    bank = word_service.bank(language)
    tiers = word_service.tiers_for(DAILY_DIFFICULTY)
    return bank.pick(length, tiers=tiers, seed=seed_for(day, language, length))


def describe(day: date, language: str, length: int = DAILY_LENGTH) -> Dict:
    return {
        "date": day.isoformat(),
        "number": puzzle_number(day),
        "language": language,
        "word_length": length,
        "difficulty": DAILY_DIFFICULTY,
        "attempts_allowed": word_service.attempts_for(length, DAILY_DIFFICULTY),
    }


# Emoji grid, the thing people paste into a chat. Built server-side so the
# squares match the player's theme choice for correct/present.
SQUARES = {
    "default": {"green": "\U0001F7E9", "yellow": "\U0001F7E8", "gray": "⬛"},
    "colorblind": {"green": "\U0001F7E6", "yellow": "\U0001F7E7", "gray": "⬛"},
}


def share_text(game, marks_by_turn, theme: str = "default") -> str:
    """A spoiler-free result grid."""
    palette = SQUARES.get("colorblind" if theme == "colorblind" else "default")
    header_number = game.daily_number if game.daily_number is not None else None
    title = "Oflaz Wordle"
    if header_number is not None:
        title += f" #{header_number}"
    score = f"{game.attempts_used}/{game.attempts_allowed}" if game.status == "won" else "X/" + str(
        game.attempts_allowed
    )
    lines = [f"{title} {game.language.upper()} {score}", ""]
    for marks in marks_by_turn:
        lines.append("".join(palette[mark] for mark in marks))
    return "\n".join(lines)
