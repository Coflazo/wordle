"""Vocabulary progress and the profile dashboard."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Dict, List, Optional

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app import config, models
from app.services import word_service

TIMELINE_LIMIT = 30
WORD_LIST_LIMIT = 100

MASTERED_AT = 0.80
KNOWN_AT = 0.40

# How many clean solves count as "I know this word cold".
SOLVES_FOR_DEPTH = 3


def _clamp01(value: float) -> float:
    return max(0.0, min(1.0, value))


def compute_mastery(row: models.WordProgress) -> float:
    """Confidence that the player knows this word, in [0, 1].

    The previous formula scored 0.3 for a word that had only ever been *shown*
    to the player and never solved, because its failure term started at full
    credit. Merely meeting a word is not partial knowledge, so an unsolved word
    now scores 0.

        depth         repeated success, saturating at three solves
        success       solve rate among decided attempts
        understanding did the player read what it means
    """
    decided = row.solved_count + row.failed_count
    if decided == 0 and row.meaning_opened_count == 0:
        return 0.0

    depth = _clamp01(row.solved_count / SOLVES_FOR_DEPTH)
    success = (row.solved_count / decided) if decided else 0.0
    understanding = 1.0 if row.meaning_opened_count > 0 else 0.0
    return round(0.50 * depth + 0.35 * success + 0.15 * understanding, 4)


def is_mastered(row: models.WordProgress) -> bool:
    return compute_mastery(row) >= MASTERED_AT


def is_known(row: models.WordProgress) -> bool:
    return compute_mastery(row) >= KNOWN_AT


def is_struggling(row: models.WordProgress) -> bool:
    return row.failed_count >= 1 and compute_mastery(row) < KNOWN_AT


def _get_or_create_progress(
    db: Session, profile_id: int, word: str, language: str
) -> models.WordProgress:
    row = db.execute(
        select(models.WordProgress).where(
            models.WordProgress.profile_id == profile_id,
            models.WordProgress.word == word,
            models.WordProgress.language == language,
        )
    ).scalar_one_or_none()
    if row is None:
        # Column defaults are applied by the INSERT, not by the constructor, so
        # a freshly built row still has None counters until it is flushed.
        # Setting them here keeps the callers' `+= 1` valid before the flush.
        row = models.WordProgress(
            profile_id=profile_id,
            word=word,
            language=language,
            seen_count=0,
            solved_count=0,
            failed_count=0,
            meaning_opened_count=0,
            mastery_score=0.0,
        )
        db.add(row)
    return row


def _touch(row: models.WordProgress) -> None:
    row.mastery_score = compute_mastery(row)
    row.last_seen_at = datetime.now(timezone.utc)


def increment_seen(db: Session, profile_id: int, word: str, language: str) -> None:
    row = _get_or_create_progress(db, profile_id, word, language)
    row.seen_count += 1
    _touch(row)


def increment_solved(db: Session, profile_id: int, word: str, language: str) -> None:
    row = _get_or_create_progress(db, profile_id, word, language)
    row.solved_count += 1
    _touch(row)


def increment_failed(db: Session, profile_id: int, word: str, language: str) -> None:
    row = _get_or_create_progress(db, profile_id, word, language)
    row.failed_count += 1
    _touch(row)


def increment_meaning_opened(db: Session, profile_id: int, word: str, language: str) -> None:
    row = _get_or_create_progress(db, profile_id, word, language)
    row.meaning_opened_count += 1
    _touch(row)


def _wilson_interval(successes: int, trials: int, z: float = 1.96) -> tuple[float, float]:
    """95% confidence interval for a proportion.

    Wilson rather than the normal approximation because this app is played by
    one person: at n=8 the normal interval can run below 0 or above 1, and at
    n=0 it divides by zero.
    """
    if trials == 0:
        return (0.0, 0.0)
    p = successes / trials
    denom = 1 + z * z / trials
    center = (p + z * z / (2 * trials)) / denom
    margin = z * ((p * (1 - p) / trials + z * z / (4 * trials * trials)) ** 0.5) / denom
    return (round(max(0.0, center - margin), 4), round(min(1.0, center + margin), 4))


def dashboard(db: Session, profile_id: int, language: Optional[str] = None) -> dict:
    profile = db.get(models.Profile, profile_id)
    if profile is None:
        return {}

    game_filter = [models.Game.profile_id == profile_id]
    progress_filter = [models.WordProgress.profile_id == profile_id]
    if language:
        game_filter.append(models.Game.language == language)
        progress_filter.append(models.WordProgress.language == language)

    finished_filter = game_filter + [models.Game.status.in_(("won", "lost"))]

    # Aggregate in SQL. The previous implementation loaded every game row into
    # Python and made about ten full passes over the list plus three sorts, with
    # no limit and no date window.
    totals = db.execute(
        select(
            func.count(models.Game.id),
            func.sum(func.iif(models.Game.status == "won", 1, 0)),
            func.avg(func.iif(models.Game.status == "won", models.Game.attempts_used, None)),
            func.avg(models.Game.word_length),
            func.max(func.iif(models.Game.status == "won", models.Game.word_length, 0)),
        ).where(*finished_filter)
    ).one()
    finished_count = totals[0] or 0
    wins = totals[1] or 0

    fastest = db.execute(
        select(
            func.min(
                func.julianday(models.Game.finished_at) - func.julianday(models.Game.started_at)
            )
        ).where(*finished_filter, models.Game.status == "won", models.Game.finished_at.isnot(None))
    ).scalar()

    core = {
        "games_played": finished_count,
        "wins": wins,
        "win_rate": round(wins / finished_count, 4) if finished_count else 0.0,
        "avg_attempts": round(totals[2], 2) if totals[2] is not None else 0.0,
        "avg_word_length": round(totals[3], 2) if totals[3] is not None else 0.0,
        "longest_word_solved": totals[4] or 0,
        "fastest_solve_seconds": round(fastest * 86400.0, 1) if fastest else None,
    }

    outcomes = db.execute(
        select(models.Game.status)
        .where(*finished_filter)
        .order_by(models.Game.finished_at.asc(), models.Game.id.asc())
    ).scalars().all()
    core["best_streak"], core["current_streak"] = _streaks(outcomes)

    recent = list(reversed(outcomes))
    core["delta_last_7_games"] = round(_rate(recent[:7]) - _rate(recent[7:14]), 4)
    # An empty comparison window is not a 0% baseline. Reporting a delta against
    # nothing rendered a new player's first wins as pure improvement.
    core["delta_is_meaningful"] = len(recent) >= 14

    attempts_rows = db.execute(
        select(models.Game.word_length, models.Game.attempts_used, func.count(models.Game.id))
        .where(*finished_filter, models.Game.status == "won")
        .group_by(models.Game.word_length, models.Game.attempts_used)
    ).all()
    # Range runs to MAX_ATTEMPTS: a ten-letter chill game allows ten attempts,
    # and the old range(1, 10) silently discarded a win on the tenth.
    distribution = {
        str(length): {str(k): 0 for k in range(1, config.MAX_ATTEMPTS + 1)}
        for length in config.ATTEMPTS_BY_LENGTH
    }
    for length, used, count in attempts_rows:
        bucket = distribution.get(str(length))
        if bucket is not None and str(used) in bucket:
            bucket[str(used)] = count

    language_rows = db.execute(
        select(
            models.Game.language,
            func.count(models.Game.id),
            func.sum(func.iif(models.Game.status == "won", 1, 0)),
        )
        .where(*finished_filter)
        .group_by(models.Game.language)
    ).all()
    language_split = [
        {
            "language": lang,
            "games": count,
            "wins": won or 0,
            "win_rate": round((won or 0) / count, 4) if count else 0.0,
        }
        for lang, count, won in language_rows
    ]
    language_split.sort(key=lambda row: -row["games"])
    core["favorite_language"] = language_split[0]["language"] if language_split else None

    progress_rows = db.execute(
        select(models.WordProgress).where(*progress_filter)
    ).scalars().all()
    # Recompute rather than trusting the stored score: mastery_score is written
    # at play time, so a formula change would otherwise leave every historical
    # row reporting the old number with no backfill.
    scored = [(row, compute_mastery(row)) for row in progress_rows]

    mastered = [pair for pair in scored if pair[1] >= MASTERED_AT]
    known = [pair for pair in scored if KNOWN_AT <= pair[1] < MASTERED_AT]
    struggling = [pair for pair in scored if pair[0].failed_count >= 1 and pair[1] < KNOWN_AT]

    vocabulary = {
        "total_words_seen": len(scored),
        "mastered_count": len(mastered),
        "known_count": len(known),
        "struggling_count": len(struggling),
        "mastered": _word_list(mastered, descending=True),
        "known": _word_list(known, descending=True),
        "struggling": _word_list(struggling, descending=False),
    }

    timeline_rows = db.execute(
        select(models.Game)
        .where(*finished_filter)
        .order_by(models.Game.finished_at.desc(), models.Game.id.desc())
        .limit(TIMELINE_LIMIT)
    ).scalars().all()
    timeline = [
        {
            "game_id": game.id,
            "language": game.language,
            "answer": game.answer,
            "answer_display": word_service.display(game.language, game.answer),
            "word_length": game.word_length,
            "difficulty": game.difficulty,
            "attempts_used": game.attempts_used,
            "attempts_allowed": game.attempts_allowed,
            "status": game.status,
            "resigned": bool(game.resigned),
            "hints_used": game.hints_used,
            "finished_at": game.finished_at.isoformat() if game.finished_at else None,
        }
        for game in timeline_rows
    ]

    return {
        "profile": {
            "id": profile.id,
            "name": profile.name,
            "preferred_language": profile.preferred_language,
            "created_at": profile.created_at.isoformat() if profile.created_at else None,
        },
        "language": language,
        "core": core,
        "attempts_distribution": distribution,
        "language_split": language_split,
        "vocabulary": vocabulary,
        "timeline": timeline,
    }


def _streaks(outcomes: List[str]) -> tuple[int, int]:
    best = run = 0
    for status in outcomes:
        run = run + 1 if status == "won" else 0
        best = max(best, run)
    current = 0
    for status in reversed(outcomes):
        if status != "won":
            break
        current += 1
    return best, current


def _rate(chunk: List[str]) -> float:
    if not chunk:
        return 0.0
    return sum(1 for status in chunk if status == "won") / len(chunk)


def _word_list(pairs, descending: bool) -> List[dict]:
    ordered = sorted(pairs, key=lambda pair: (-pair[1] if descending else pair[1], pair[0].word))
    return [
        {
            "word": row.word,
            "display": word_service.display(row.language, row.word),
            "language": row.language,
            "mastery": score,
            "seen": row.seen_count,
            "solved": row.solved_count,
            "failed": row.failed_count,
            "meaning_opened": row.meaning_opened_count,
            "last_seen_at": row.last_seen_at.isoformat() if row.last_seen_at else None,
        }
        for row, score in ordered[:WORD_LIST_LIMIT]
    ]


__all__ = [
    "compute_mastery", "is_mastered", "is_known", "is_struggling",
    "increment_seen", "increment_solved", "increment_failed", "increment_meaning_opened",
    "dashboard", "_wilson_interval",
]
