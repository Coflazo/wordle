"""Word progress bookkeeping + dashboard aggregations."""

from __future__ import annotations

import json
from collections import Counter, defaultdict
from datetime import datetime, timezone
from typing import Dict, List, Optional

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app import models


def _clamp01(x: float) -> float:
    return max(0.0, min(1.0, x))


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _get_or_create_progress(
    db: Session, profile_id: int, word: str, language: str
) -> models.WordProgress:
    row = (
        db.execute(
            select(models.WordProgress).where(
                models.WordProgress.profile_id == profile_id,
                models.WordProgress.word == word,
                models.WordProgress.language == language,
            )
        )
        .scalars()
        .first()
    )
    if row is None:
        row = models.WordProgress(
            profile_id=profile_id, word=word, language=language, last_seen_at=_now()
        )
        db.add(row)
        db.flush()
    return row


def _recompute_mastery(row: models.WordProgress) -> None:
    """mastery = 0.6*solved/3 + 0.3*(1 - failed/3) + 0.1*(meaning_opened>0)."""
    solved = _clamp01(row.solved_count / 3.0)
    failed = _clamp01(row.failed_count / 3.0)
    opened_bonus = 0.1 if row.meaning_opened_count > 0 else 0.0
    row.mastery_score = round(0.6 * solved + 0.3 * (1.0 - failed) + opened_bonus, 4)


def increment_seen(db: Session, profile_id: int, word: str, language: str) -> None:
    row = _get_or_create_progress(db, profile_id, word, language)
    row.seen_count += 1
    row.last_seen_at = _now()
    _recompute_mastery(row)


def increment_solved(db: Session, profile_id: int, word: str, language: str) -> None:
    row = _get_or_create_progress(db, profile_id, word, language)
    row.solved_count += 1
    row.last_seen_at = _now()
    _recompute_mastery(row)


def increment_failed(db: Session, profile_id: int, word: str, language: str) -> None:
    row = _get_or_create_progress(db, profile_id, word, language)
    row.failed_count += 1
    row.last_seen_at = _now()
    _recompute_mastery(row)


def increment_meaning_opened(
    db: Session, profile_id: int, word: str, language: str
) -> None:
    row = _get_or_create_progress(db, profile_id, word, language)
    row.meaning_opened_count += 1
    row.last_seen_at = _now()
    _recompute_mastery(row)


# ----- Category logic (§7 in plan) -----


def is_mastered(row: models.WordProgress) -> bool:
    return (
        row.solved_count >= 3
        and row.failed_count <= 1
        and (row.meaning_opened_count > 0 or row.solved_count >= 2)
    )


def is_known(row: models.WordProgress) -> bool:
    return row.seen_count >= 1 and (
        row.solved_count >= 1 or row.meaning_opened_count > 0
    )


def is_struggling(row: models.WordProgress) -> bool:
    return row.failed_count >= 1 or row.meaning_opened_count >= 3


# ----- Dashboard aggregations -----


def _games_query(db: Session, profile_id: int, language: Optional[str]):
    q = db.execute(
        select(models.Game).where(models.Game.profile_id == profile_id)
    ).scalars().all()
    if language:
        q = [g for g in q if g.language == language]
    return q


def _progress_query(db: Session, profile_id: int, language: Optional[str]):
    rows = (
        db.execute(
            select(models.WordProgress).where(
                models.WordProgress.profile_id == profile_id
            )
        )
        .scalars()
        .all()
    )
    if language:
        rows = [r for r in rows if r.language == language]
    return rows


def dashboard(
    db: Session, profile_id: int, language: Optional[str] = None
) -> Dict[str, object]:
    games = _games_query(db, profile_id, language)
    finished = [g for g in games if g.status in {"won", "lost"}]
    wins = [g for g in finished if g.status == "won"]
    losses = [g for g in finished if g.status == "lost"]
    win_rate = round(len(wins) / len(finished), 4) if finished else 0.0

    # Streaks: order finished games by finished_at and walk.
    ordered = sorted(finished, key=lambda g: g.finished_at or g.started_at)
    current_streak = 0
    best_streak = 0
    run = 0
    for g in ordered:
        if g.status == "won":
            run += 1
            best_streak = max(best_streak, run)
        else:
            run = 0
    # current_streak = trailing run
    for g in reversed(ordered):
        if g.status == "won":
            current_streak += 1
        else:
            break

    avg_guesses = (
        round(sum(g.attempts_used for g in wins) / len(wins), 2) if wins else 0.0
    )
    avg_word_length = (
        round(sum(g.word_length for g in wins) / len(wins), 2) if wins else 0.0
    )
    longest = max((g.word_length for g in wins), default=0)
    fastest = None
    for g in wins:
        if g.finished_at and g.started_at:
            elapsed = (g.finished_at - g.started_at).total_seconds()
            if fastest is None or elapsed < fastest:
                fastest = round(elapsed, 2)

    # Vocabulary metrics.
    progress = _progress_query(db, profile_id, language)
    known = [r for r in progress if is_known(r)]
    mastered = [r for r in progress if is_mastered(r)]
    struggling = [r for r in progress if is_struggling(r)]
    meaning_opened_total = sum(r.meaning_opened_count for r in progress)
    solved_no_help = sum(
        1
        for r in progress
        if r.solved_count >= 1 and r.meaning_opened_count == 0
    )
    repeated_failed = sorted(
        [
            {"word": r.word, "language": r.language, "fails": r.failed_count}
            for r in progress
            if r.failed_count >= 2
        ],
        key=lambda d: -d["fails"],
    )[:10]

    # Favorite language: most games played.
    lang_counts = Counter(g.language for g in games)
    favorite = lang_counts.most_common(1)[0][0] if lang_counts else None

    # Delta over last 7 games vs prior 7.
    last_finished = sorted(
        finished, key=lambda g: g.finished_at or g.started_at, reverse=True
    )
    def _rate(chunk):
        if not chunk:
            return 0.0
        w = sum(1 for g in chunk if g.status == "won")
        return w / len(chunk)
    delta = round(
        _rate(last_finished[:7]) - _rate(last_finished[7:14]), 4
    )

    # Attempts distribution per length.
    dist: Dict[str, Dict[str, int]] = {
        str(l): {str(k): 0 for k in range(1, 10)} for l in range(5, 11)
    }
    for g in wins:
        length_key = str(g.word_length)
        used_key = str(g.attempts_used)
        if length_key in dist and used_key in dist[length_key]:
            dist[length_key][used_key] += 1

    timeline = [
        {
            "game_id": g.id,
            "language": g.language,
            "word_length": g.word_length,
            "status": g.status,
            "attempts_used": g.attempts_used,
            "attempts_allowed": g.attempts_allowed,
            "started_at": (g.started_at.isoformat() if g.started_at else None),
            "finished_at": (g.finished_at.isoformat() if g.finished_at else None),
            "answer": (g.answer if g.status in {"won", "lost"} else None),
        }
        for g in last_finished[:30]
    ]

    def _word_list(rows: List[models.WordProgress]) -> List[Dict[str, object]]:
        return [
            {
                "word": r.word,
                "language": r.language,
                "mastery_score": r.mastery_score,
                "solved": r.solved_count,
                "failed": r.failed_count,
                "seen": r.seen_count,
                "meaning_opened": r.meaning_opened_count,
            }
            for r in sorted(rows, key=lambda x: -x.mastery_score)
        ][:100]

    return {
        "core": {
            "games_played": len(games),
            "wins": len(wins),
            "losses": len(losses),
            "win_rate": win_rate,
            "current_streak": current_streak,
            "best_streak": best_streak,
            "avg_guesses_per_win": avg_guesses,
            "avg_word_length_solved": avg_word_length,
            "longest_word_solved": longest,
            "fastest_solve_seconds": fastest,
        },
        "vocab": {
            "known_count": len(known),
            "mastered_count": len(mastered),
            "struggling_count": len(struggling),
            "solved_without_help_count": solved_no_help,
            "meaning_opened_count": meaning_opened_total,
            "repeated_failed_words": repeated_failed,
            "favorite_language": favorite,
            "delta_last_7_games": delta,
        },
        "attempts_distribution": dist,
        "language_split": dict(lang_counts),
        "timeline": timeline,
        "mastered_words": _word_list(mastered),
        "known_words": _word_list(known),
        "struggling_words": _word_list(struggling),
    }
