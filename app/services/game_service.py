"""Game engine: start, guess scoring, terminal-state bookkeeping."""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from typing import List, Optional

from sqlalchemy.orm import Session

from app import models
from app.services import stats_service, word_service


class GameError(Exception):
    """Raised for user-facing game errors (400)."""


def _now() -> datetime:
    return datetime.now(timezone.utc)


def score_guess(answer: str, guess: str) -> List[str]:
    """Two-pass Wordle scoring with correct duplicate-letter handling.

    First pass marks greens and tallies remaining letters in the answer.
    Second pass marks yellows only if that letter has budget left.
    """
    answer = answer.lower()
    guess = guess.lower()
    assert len(answer) == len(guess), "answer and guess must be same length"

    result: List[str] = ["gray"] * len(answer)
    remaining: dict[str, int] = {}

    for i, ch in enumerate(answer):
        if guess[i] == ch:
            result[i] = "green"
        else:
            remaining[ch] = remaining.get(ch, 0) + 1

    for i, ch in enumerate(guess):
        if result[i] == "green":
            continue
        if remaining.get(ch, 0) > 0:
            result[i] = "yellow"
            remaining[ch] -= 1

    return result


def start_game(
    db: Session,
    profile_id: int,
    language: str,
    difficulty: str = "classic",
    word_length: Optional[int] = None,
) -> models.Game:
    profile = db.get(models.Profile, profile_id)
    if profile is None:
        raise GameError(f"profile {profile_id} not found")

    if word_length is None:
        word_length = word_service.sample_length()

    answer = word_service.pick_target(language, word_length)
    attempts_allowed = word_service.attempts_for(word_length, difficulty)

    game = models.Game(
        id=str(uuid.uuid4()),
        profile_id=profile_id,
        language=language,
        word_length=word_length,
        difficulty=difficulty,
        answer=answer,
        attempts_allowed=attempts_allowed,
        attempts_used=0,
        status="active",
    )
    db.add(game)

    stats_service.increment_seen(db, profile_id, answer, language)
    db.commit()
    db.refresh(game)
    return game


def submit_guess(db: Session, game_id: str, guess: str) -> dict:
    game = db.get(models.Game, game_id)
    if game is None:
        raise GameError("game not found")
    if game.status != "active":
        raise GameError(f"game is {game.status}")

    guess_norm = guess.strip().lower()
    if len(guess_norm) != game.word_length:
        raise GameError(
            f"expected {game.word_length}-letter guess, got {len(guess_norm)}"
        )
    if not word_service.is_allowed_guess(game.language, guess_norm):
        raise GameError("word not in dictionary")

    result = score_guess(game.answer, guess_norm)
    game.attempts_used += 1

    guess_row = models.Guess(
        game_id=game.id,
        guess=guess_norm,
        result_json=json.dumps(result),
    )
    db.add(guess_row)

    won = all(m == "green" for m in result)
    exhausted = game.attempts_used >= game.attempts_allowed

    if won:
        game.status = "won"
        game.finished_at = _now()
        stats_service.increment_solved(db, game.profile_id, game.answer, game.language)
    elif exhausted:
        game.status = "lost"
        game.finished_at = _now()
        stats_service.increment_failed(db, game.profile_id, game.answer, game.language)

    db.commit()
    db.refresh(game)

    return {
        "guess": guess_norm,
        "result": result,
        "attempts_used": game.attempts_used,
        "attempts_allowed": game.attempts_allowed,
        "status": game.status,
        "answer": game.answer if game.status in {"won", "lost"} else None,
    }


def give_up(db: Session, game_id: str) -> dict:
    game = db.get(models.Game, game_id)
    if game is None:
        raise GameError("game not found")
    if game.status != "active":
        raise GameError(f"game is {game.status}")

    game.status = "lost"
    game.finished_at = _now()
    stats_service.increment_failed(db, game.profile_id, game.answer, game.language)
    db.commit()
    db.refresh(game)

    return {
        "guess": None,
        "result": [],
        "attempts_used": game.attempts_used,
        "attempts_allowed": game.attempts_allowed,
        "status": game.status,
        "answer": game.answer,
    }


def game_to_dict(game: models.Game, reveal_answer: bool = False) -> dict:
    return {
        "game_id": game.id,
        "profile_id": game.profile_id,
        "language": game.language,
        "difficulty": game.difficulty,
        "word_length": game.word_length,
        "attempts_allowed": game.attempts_allowed,
        "attempts_used": game.attempts_used,
        "status": game.status,
        "guesses": [
            {"guess": g.guess, "result": json.loads(g.result_json)}
            for g in sorted(game.guesses, key=lambda x: x.created_at)
        ],
        "answer": game.answer if reveal_answer or game.status != "active" else None,
    }
