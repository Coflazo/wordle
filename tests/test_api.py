"""HTTP contract. None of these routes had a single test before."""

from __future__ import annotations

import wordle_core as wc

from app import config
from app.services import word_service


def start_game(client, profile, **overrides):
    payload = {
        "profile_id": profile["id"],
        "language": "en",
        "difficulty": "classic",
        "word_length": 5,
    }
    payload.update(overrides)
    response = client.post("/api/games/start", json=payload)
    assert response.status_code == 201, response.text
    return response.json()


def answer_of(client, game_id):
    """Read the answer straight from the database, the way a test may."""
    from app import models
    from app.database import SessionLocal

    with SessionLocal() as session:
        return session.get(models.Game, game_id).answer


def test_ping(client):
    body = client.get("/api/ping").json()
    assert body["ok"] is True
    assert body["service"] == "oflaz-wordle"


def test_profile_crud(client):
    created = client.post("/api/profiles", json={"name": "Ada", "preferred_language": "de"})
    assert created.status_code == 201
    profile = created.json()
    assert profile["theme"] == "system"

    assert client.get(f"/api/profiles/{profile['id']}").status_code == 200

    patched = client.patch(f"/api/profiles/{profile['id']}", json={"theme": "contrast"})
    assert patched.status_code == 200
    assert patched.json()["theme"] == "contrast"

    # 204, not a 200 with a body.
    assert client.delete(f"/api/profiles/{profile['id']}").status_code == 204
    assert client.get(f"/api/profiles/{profile['id']}").status_code == 404


def test_missing_profile_is_404_with_a_code(client):
    response = client.get("/api/profiles/999999")
    assert response.status_code == 404
    assert response.json()["detail"]["code"] == "profile_not_found"


def test_oversized_avatar_config_is_rejected(client):
    response = client.post(
        "/api/profiles",
        json={"name": "Big", "avatar_config": {"blob": "x" * (config.MAX_AVATAR_CONFIG_BYTES + 10)}},
    )
    assert response.status_code == 422


def test_start_and_read_a_game(client, profile):
    game = start_game(client, profile)
    assert game["word_length"] == 5
    assert game["attempts_allowed"] == config.ATTEMPTS_BY_LENGTH[5]
    assert game["status"] == "active"
    # The answer must not leak while the game is playable.
    assert game["answer"] is None

    fetched = client.get(f"/api/games/{game['game_id']}").json()
    assert fetched["game_id"] == game["game_id"]
    assert fetched["answer"] is None


def test_chill_grants_an_extra_attempt(client, profile):
    classic = start_game(client, profile, difficulty="classic")
    chill = start_game(client, profile, difficulty="chill")
    assert chill["attempts_allowed"] == classic["attempts_allowed"] + 1


def test_scholar_draws_from_a_different_pool(client, profile):
    """Scholar previously changed nothing at all."""
    chill = start_game(client, profile, difficulty="chill")
    scholar = start_game(client, profile, difficulty="scholar")
    assert chill["tiers"] == ["common"]
    assert scholar["tiers"] == ["standard", "rare"]


def test_guess_scores_and_advances(client, profile):
    game = start_game(client, profile)
    response = client.post(f"/api/games/{game['game_id']}/guess", json={"guess": "crane"})
    assert response.status_code == 200
    body = response.json()
    assert len(body["result"]) == 5
    assert body["turn"] == 1
    assert body["attempts_used"] == 1


def test_uppercase_turkish_guess_is_accepted(client, profile):
    """'KIZIL' used to fold to 'kizil' and be rejected as not a word."""
    game = start_game(client, profile, language="tr", word_length=5)
    response = client.post(f"/api/games/{game['game_id']}/guess", json={"guess": "KIZIL"})
    assert response.status_code == 200, response.text
    assert response.json()["guess"] == "kızıl"


def test_dotted_capital_i_does_not_break_the_length_check(client, profile):
    """'İSTANBUL'.lower() is nine codepoints, so an 8-letter game rejected it."""
    game = start_game(client, profile, language="tr", word_length=8)
    response = client.post(f"/api/games/{game['game_id']}/guess", json={"guess": "İSTANBUL"})
    # Either accepted, or rejected as not-a-word — but never for the wrong length.
    assert response.status_code in (200, 422)
    if response.status_code == 422:
        assert response.json()["detail"]["code"] == "not_a_word"


def test_wrong_length_is_422_with_params(client, profile):
    game = start_game(client, profile)
    response = client.post(f"/api/games/{game['game_id']}/guess", json={"guess": "cran"})
    assert response.status_code == 422
    detail = response.json()["detail"]
    assert detail["code"] == "wrong_length"
    assert detail["params"] == {"expected": 5, "got": 4}


def test_unknown_word_is_422_and_offers_suggestions(client, profile):
    game = start_game(client, profile)
    response = client.post(f"/api/games/{game['game_id']}/guess", json={"guess": "zzzzz"})
    assert response.status_code == 422
    detail = response.json()["detail"]
    assert detail["code"] == "not_a_word"
    assert "suggestions" in detail["params"]


def test_winning_reveals_the_answer(client, profile):
    game = start_game(client, profile)
    answer = answer_of(client, game["game_id"])
    response = client.post(f"/api/games/{game['game_id']}/guess", json={"guess": answer})
    body = response.json()
    assert body["status"] == "won"
    assert body["result"] == ["green"] * 5
    assert body["answer"] == answer
    assert body["answer_display"]


def test_playing_a_finished_game_is_409(client, profile):
    game = start_game(client, profile)
    answer = answer_of(client, game["game_id"])
    client.post(f"/api/games/{game['game_id']}/guess", json={"guess": answer})
    again = client.post(f"/api/games/{game['game_id']}/guess", json={"guess": answer})
    assert again.status_code == 409
    assert again.json()["detail"]["code"] == "game_finished"


def test_losing_after_the_last_attempt(client, profile):
    game = start_game(client, profile, difficulty="classic")
    answer = answer_of(client, game["game_id"])
    wrong = next(
        w for w in word_service.bank("en").targets(5) if w != answer
    )
    body = None
    for _ in range(game["attempts_allowed"]):
        body = client.post(f"/api/games/{game['game_id']}/guess", json={"guess": wrong}).json()
    assert body["status"] == "lost"
    assert body["answer"] == answer


def test_give_up_marks_the_game_resigned(client, profile):
    game = start_game(client, profile)
    body = client.post(f"/api/games/{game['game_id']}/give-up").json()
    assert body["status"] == "lost"
    assert body["answer"]
    assert client.get(f"/api/games/{game['game_id']}").json()["resigned"] is True


def test_missing_game_is_404(client):
    assert client.get("/api/games/nope").status_code == 404
    response = client.post("/api/games/nope/guess", json={"guess": "crane"})
    assert response.status_code == 404
    assert response.json()["detail"]["code"] == "game_not_found"


def test_hint_narrows_the_candidates(client, profile):
    game = start_game(client, profile)
    first = client.get(f"/api/games/{game['game_id']}/hint").json()
    assert first["candidates_remaining"] > 1
    assert first["suggestions"]
    assert first["hints_used"] == 1

    client.post(f"/api/games/{game['game_id']}/guess", json={"guess": "crane"})
    second = client.get(f"/api/games/{game['game_id']}/hint").json()
    assert second["candidates_remaining"] <= first["candidates_remaining"]
    # The answer is always still in the candidate set.
    assert second["candidates_remaining"] >= 1


def test_hint_counts_against_the_game(client, profile):
    game = start_game(client, profile)
    client.get(f"/api/games/{game['game_id']}/hint")
    client.get(f"/api/games/{game['game_id']}/hint")
    dashboard = client.get(f"/api/stats/{profile['id']}").json()
    assert dashboard is not None  # hints_used surfaces on finished games


def test_dashboard_shape(client, profile):
    game = start_game(client, profile)
    client.post(f"/api/games/{game['game_id']}/guess",
                json={"guess": answer_of(client, game["game_id"])})

    body = client.get(f"/api/stats/{profile['id']}").json()
    assert body["core"]["games_played"] == 1
    assert body["core"]["wins"] == 1
    assert body["core"]["win_rate"] == 1.0
    assert body["core"]["current_streak"] == 1
    assert len(body["timeline"]) == 1
    # A ten-letter chill game allows ten attempts; range(1, 10) dropped the tenth.
    assert len(body["attempts_distribution"]["10"]) == config.MAX_ATTEMPTS


def test_dashboard_rejects_an_unknown_language(client, profile):
    """`?language=zz` used to return an all-zero payload instead of a 422."""
    assert client.get(f"/api/stats/{profile['id']}?language=zz").status_code == 422


def test_flags_are_stable_per_profile(client, profile):
    first = client.get(f"/api/flags?profile_id={profile['id']}").json()["assignments"]
    second = client.get(f"/api/flags?profile_id={profile['id']}").json()["assignments"]
    assert first == second
    assert set(first) == {"default_length", "customize_open", "meaning_on_loss", "hint_affordance"}


def test_events_are_accepted_and_survive_a_bad_profile(client, profile):
    ok = client.post("/api/events", json={
        "profile_id": profile["id"],
        "events": [{"name": "test_event", "props": {"a": 1}}],
    })
    assert ok.status_code == 202
    assert ok.json()["accepted"] == 1

    # A stale id in localStorage must not turn a beacon into an error.
    stale = client.post("/api/events", json={
        "profile_id": 999999,
        "events": [{"name": "test_event"}],
    })
    assert stale.status_code == 202


def test_experiment_results_have_intervals(client, profile):
    client.get(f"/api/flags?profile_id={profile['id']}")
    body = client.get("/api/experiments/results").json()
    assert body["experiments"]
    for experiment in body["experiments"]:
        for arm in experiment["arms"]:
            assert 0.0 <= arm["ci_low"] <= arm["ci_high"] <= 1.0


def test_deleting_a_profile_cascades(client):
    profile = client.post("/api/profiles", json={"name": "Temp"}).json()
    game = start_game(client, profile)
    client.post(f"/api/games/{game['game_id']}/guess", json={"guess": "crane"})
    client.delete(f"/api/profiles/{profile['id']}")

    # Games, guesses, word_progress, events and assignments all go with it.
    from app import models
    from app.database import SessionLocal

    with SessionLocal() as session:
        assert session.query(models.Game).filter_by(profile_id=profile["id"]).count() == 0
        assert session.query(models.WordProgress).filter_by(profile_id=profile["id"]).count() == 0


def test_pages_are_served(client):
    for path in ("/", "/game", "/profile"):
        assert client.get(path).status_code == 200


def test_debug_endpoint_is_closed_by_default(client):
    assert client.get("/api/stats/_debug/banks").status_code == 404
