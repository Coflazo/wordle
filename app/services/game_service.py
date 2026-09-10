"""Game engine: start, guess scoring, terminal-state bookkeeping."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import List, Optional

import wordle_core as wc
from sqlalchemy import update
from sqlalchemy.orm import Session

from app import config, models
from app.errors import (
    GAME_FINISHED,
    GAME_NOT_FOUND,
    NOT_A_WORD,
    PROFILE_NOT_FOUND,
    WRONG_LENGTH,
    Conflict,
    NotFound,
    Unprocessable,
)
from app.services import stats_service, word_service


def _now() -> datetime:
    return datetime.now(timezone.utc)


def score_guess(answer: str, guess: str, language: str = "en") -> List[str]:
    """Green/yellow/gray for a guess, computed by the native core.

    Duplicate letters are budgeted: greens claim their letter first, then yellows
    are drawn from what is left, so SPEED against ERASE scores the second E gray.
    """
    return wc.score(answer, guess, language)


def start_game(
    db: Session,
    profile_id: int,
    language: str,
    difficulty: str = "classic",
    word_length: Optional[int] = None,
) -> models.Game:
    profile = db.get(models.Profile, profile_id)
    if profile is None:
        raise NotFound(PROFILE_NOT_FOUND, f"profile {profile_id} not found", profile_id=profile_id)

    if word_length is None:
        word_length = word_service.sample_length(language, difficulty)

    answer = word_service.pick_target(language, word_length, difficulty)
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
        raise NotFound(GAME_NOT_FOUND, "game not found", game_id=game_id)
    if game.status != "active":
        raise Conflict(GAME_FINISHED, f"game is {game.status}", status=game.status)

    # Locale-correct folding. Invariant str.lower() turned 'İSTANBUL' into nine
    # codepoints for an eight-letter word, and 'KIZIL' into 'kizil'.
    guess_norm = word_service.fold(game.language, guess)
    if len(guess_norm) != game.word_length:
        raise Unprocessable(
            WRONG_LENGTH,
            f"expected a {game.word_length}-letter guess, got {len(guess_norm)}",
            expected=game.word_length,
            got=len(guess_norm),
        )
    if not word_service.is_allowed_guess(game.language, guess_norm):
        raise Unprocessable(
            NOT_A_WORD,
            f"{guess_norm!r} is not in the {game.language} word list",
            word=guess_norm,
            language=game.language,
            suggestions=word_service.suggest(game.language, guess_norm),
        )

    result = score_guess(game.answer, guess_norm, game.language)
    turn = game.attempts_used + 1

    # Claim the turn with a conditional UPDATE before writing anything else.
    # Two guesses submitted at once used to be a read-modify-write race: both
    # read attempts_used, both wrote the same value, and one turn vanished.
    # FastAPI runs these sync handlers on a thread pool, so this is reachable
    # from one player double-tapping Enter.
    claimed = db.execute(
        update(models.Game)
        .where(
            models.Game.id == game.id,
            models.Game.attempts_used == game.attempts_used,
            models.Game.status == "active",
        )
        .values(attempts_used=turn)
    ).rowcount
    if claimed == 0:
        db.rollback()
        raise Conflict(GAME_FINISHED, "another guess for this game is already in flight")

    db.add(
        models.Guess(
            game_id=game.id,
            turn=turn,
            guess=guess_norm,
            result=_pack_result(result),
        )
    )

    won = all(mark == "green" for mark in result)
    exhausted = turn >= game.attempts_allowed
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
        "turn": turn,
        "attempts_used": game.attempts_used,
        "attempts_allowed": game.attempts_allowed,
        "status": game.status,
        "answer": _reveal(game),
        "answer_display": _reveal_display(game),
    }


def give_up(db: Session, game_id: str) -> dict:
    game = db.get(models.Game, game_id)
    if game is None:
        raise NotFound(GAME_NOT_FOUND, "game not found", game_id=game_id)
    if game.status != "active":
        raise Conflict(GAME_FINISHED, f"game is {game.status}", status=game.status)

    game.status = "lost"
    game.resigned = True
    game.finished_at = _now()
    stats_service.increment_failed(db, game.profile_id, game.answer, game.language)
    db.commit()
    db.refresh(game)

    return {
        "guess": None,
        "result": [],
        "turn": game.attempts_used,
        "attempts_used": game.attempts_used,
        "attempts_allowed": game.attempts_allowed,
        "status": game.status,
        "answer": game.answer,
        "answer_display": word_service.display(game.language, game.answer),
    }


# Results are stored as one digit per position rather than a JSON array: it is
# a third of the bytes, it sorts and compares in SQL, and it is the same
# encoding the solver protocol uses, so no translation is needed to ask for a
# hint from a stored history.
_MARK_TO_DIGIT = {"gray": "0", "yellow": "1", "green": "2"}
_DIGIT_TO_MARK = {"0": "gray", "1": "yellow", "2": "green"}


def _pack_result(result: List[str]) -> str:
    return "".join(_MARK_TO_DIGIT[mark] for mark in result)


def unpack_result(packed: str) -> List[str]:
    return [_DIGIT_TO_MARK[ch] for ch in packed]


def _reveal(game: models.Game) -> Optional[str]:
    return game.answer if game.status in {"won", "lost"} else None


def _reveal_display(game: models.Game) -> Optional[str]:
    if game.status not in {"won", "lost"}:
        return None
    return word_service.display(game.language, game.answer)


def game_to_dict(game: models.Game, reveal_answer: bool = False) -> dict:
    reveal = reveal_answer or game.status != "active"
    # Ordered by turn, not by created_at: two rows written inside the same
    # microsecond used to sort non-deterministically.
    guesses = sorted(game.guesses, key=lambda row: row.turn)
    return {
        "game_id": game.id,
        "profile_id": game.profile_id,
        "language": game.language,
        "difficulty": game.difficulty,
        "word_length": game.word_length,
        "attempts_allowed": game.attempts_allowed,
        "attempts_used": game.attempts_used,
        "status": game.status,
        "resigned": bool(game.resigned),
        "guesses": [
            {"guess": row.guess, "turn": row.turn, "result": unpack_result(row.result)}
            for row in guesses
        ],
        "answer": game.answer if reveal else None,
        "answer_display": word_service.display(game.language, game.answer) if reveal else None,
        "tiers": list(word_service.tiers_for(game.difficulty)),
    }


def history_for_solver(game: models.Game) -> List[tuple[str, str]]:
    """(guess, digit-mask) pairs, in turn order — the solver's input format."""
    return [(row.guess, row.result) for row in sorted(game.guesses, key=lambda r: r.turn)]
