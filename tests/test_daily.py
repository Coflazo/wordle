"""The daily puzzle: same word for everyone, derived rather than stored."""

from __future__ import annotations

from datetime import date, timedelta

import pytest

from app.services import daily_service


def test_same_day_gives_the_same_word():
    day = date(2026, 9, 10)
    for language in ("en", "tr", "de"):
        first = daily_service.word_for(day, language)
        assert first
        assert daily_service.word_for(day, language) == first


def test_different_days_give_different_words():
    """Not a hard guarantee, but a repeat inside a fortnight would be a bug."""
    words = {
        daily_service.word_for(date(2026, 9, 1) + timedelta(days=n), "en")
        for n in range(14)
    }
    assert len(words) >= 13


def test_languages_are_independent():
    day = date(2026, 9, 10)
    words = {lang: daily_service.word_for(day, lang) for lang in ("en", "tr", "de")}
    assert len(set(words.values())) == 3


def test_the_word_is_playable():
    from app.services import word_service

    day = date(2026, 9, 10)
    for language in ("en", "tr", "de"):
        word = daily_service.word_for(day, language)
        assert len(word) == daily_service.DAILY_LENGTH
        assert word_service.bank(language).is_allowed(word)
        assert word_service.bank(language).is_target(word)


def test_puzzle_numbers_advance_by_one_a_day():
    day = date(2026, 9, 10)
    assert daily_service.puzzle_number(day + timedelta(days=1)) == (
        daily_service.puzzle_number(day) + 1
    )


def test_seed_is_never_zero():
    """The native pick() reads seed 0 as 'draw a fresh random word'."""
    for n in range(400):
        seed = daily_service.seed_for(date(2026, 1, 1) + timedelta(days=n), "en", 5)
        assert seed != 0


def test_timezone_offset_moves_the_day():
    """A player 14 hours ahead can be on tomorrow's puzzle already."""
    behind = daily_service.today(-720)
    ahead = daily_service.today(840)
    assert (ahead - behind).days in (0, 1, 2)


# ------------------------------------------------------------------ routes

def start_daily(client, profile, language="en"):
    return client.post(
        f"/api/games/daily?profile_id={profile['id']}&language={language}&tz_offset_minutes=0"
    )


def test_daily_route_returns_a_playable_game(client, profile):
    response = start_daily(client, profile)
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["word_length"] == daily_service.DAILY_LENGTH
    assert body["game"]["status"] == "active"
    assert body["game"]["daily_number"] == body["number"]


def test_daily_resumes_rather_than_redealing(client, profile):
    first = start_daily(client, profile).json()["game"]
    client.post(f"/api/games/{first['game_id']}/guess", json={"guess": "crane"})
    second = start_daily(client, profile).json()["game"]
    assert second["game_id"] == first["game_id"]
    assert len(second["guesses"]) == 1


def test_daily_is_separate_per_language(client, profile):
    en = start_daily(client, profile, "en").json()["game"]
    de = start_daily(client, profile, "de").json()["game"]
    assert en["game_id"] != de["game_id"]


def test_share_text_only_appears_once_the_game_is_over(client, profile):
    game = start_daily(client, profile).json()["game"]
    assert game["share_text"] is None

    from app import models
    from app.database import SessionLocal

    with SessionLocal() as session:
        answer = session.get(models.Game, game["game_id"]).answer

    client.post(f"/api/games/{game['game_id']}/guess", json={"guess": answer})
    finished = client.get(f"/api/games/{game['game_id']}").json()
    assert finished["share_text"]
    lines = finished["share_text"].split("\n")
    assert lines[0].startswith("Oflaz Wordle #")
    assert "1/6" in lines[0]
    # The grid must not spell out the answer.
    assert answer.lower() not in finished["share_text"].lower()
    assert lines[-1] == "\U0001F7E9" * 5


def test_share_text_uses_colourblind_squares_when_asked(client, profile):
    game = start_daily(client, profile).json()["game"]

    from app import models
    from app.database import SessionLocal

    with SessionLocal() as session:
        answer = session.get(models.Game, game["game_id"]).answer
    client.post(f"/api/games/{game['game_id']}/guess", json={"guess": answer})

    normal = client.get(f"/api/games/{game['game_id']}").json()["share_text"]
    cb = client.get(f"/api/games/{game['game_id']}?theme=colorblind").json()["share_text"]
    assert "\U0001F7E9" in normal      # green square
    assert "\U0001F7E6" in cb          # blue square
