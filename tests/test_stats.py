"""Mastery + category logic."""

from types import SimpleNamespace

from app.services.stats_service import (
    _recompute_mastery,
    is_known,
    is_mastered,
    is_struggling,
)


def _row(**kwargs):
    defaults = dict(
        seen_count=0,
        solved_count=0,
        failed_count=0,
        meaning_opened_count=0,
        mastery_score=0.0,
    )
    defaults.update(kwargs)
    return SimpleNamespace(**defaults)


def test_mastered_true_after_three_solves():
    r = _row(seen_count=3, solved_count=3, meaning_opened_count=1)
    _recompute_mastery(r)
    assert is_mastered(r) is True


def test_mastered_false_after_many_fails():
    r = _row(seen_count=5, solved_count=3, failed_count=3, meaning_opened_count=1)
    assert is_mastered(r) is False


def test_struggling_after_failure():
    r = _row(seen_count=1, failed_count=1)
    assert is_struggling(r) is True


def test_known_after_solving_once():
    r = _row(seen_count=1, solved_count=1)
    assert is_known(r) is True
