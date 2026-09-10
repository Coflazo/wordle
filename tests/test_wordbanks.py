"""Word bank contents and the content policy."""

from __future__ import annotations

import pytest
import wordle_core as wc

from app import config
from app.services import word_service
from scripts.blocklist import NOT_AS_ANSWER, SLURS


@pytest.fixture(scope="module")
def banks():
    return {language: word_service.bank(language) for language in config.LANGUAGES}


def test_every_language_has_a_bank(banks):
    for language, bank in banks.items():
        assert bank.language == language
        assert bank.target_count > 0
        assert bank.allowed_count >= bank.target_count


def test_every_length_is_playable(banks):
    """A player who picks any length must get a game, at any difficulty."""
    for language, bank in banks.items():
        for length in range(wc.MIN_LEN, wc.MAX_LEN + 1):
            assert bank.count_targets(length) > 0, f"{language} has no {length}-letter targets"
            for difficulty in config.DIFFICULTIES:
                tiers = config.TIERS_BY_DIFFICULTY[difficulty]
                assert bank.count_targets(length, tiers=tiers) > 0, (
                    f"{language}/{difficulty} has no {length}-letter targets"
                )


def test_slurs_are_absent_entirely(banks):
    """Not merely un-servable as answers: not in the bank at all."""
    for language, bank in banks.items():
        for word in SLURS:
            assert not bank.is_allowed(word), f"{language} still allows {word!r}"


def test_blocked_words_are_never_answers(banks):
    for language, bank in banks.items():
        for word in NOT_AS_ANSWER:
            assert not bank.is_target(word), f"{language} can serve {word!r} as the answer"


def test_real_words_stay_guessable(banks):
    """Vulgar-but-real words are still valid guesses, just never the answer."""
    assert banks["en"].is_allowed("bitch")
    assert not banks["en"].is_target("bitch")


@pytest.mark.parametrize("word", [
    "egypt", "honda", "ottawa", "leeds", "israel", "amazon",
])
def test_english_proper_nouns_are_not_answers(banks, word):
    assert not banks["en"].is_target(word)
    assert banks["en"].is_allowed(word), "still a legal guess"


@pytest.mark.parametrize("word", ["giuseppe", "milan", "aberdeen", "about", "above"])
def test_german_contamination_is_not_answers(banks, word):
    """Names and English words rode in on an OpenSubtitles frequency list."""
    assert not banks["de"].is_target(word)


def test_german_display_form_keeps_capitals(banks):
    """Every German noun was lowercased in the shipped bank."""
    for word, expected in [("apfel", "Apfel"), ("straße", "Straße"), ("zucker", "Zucker")]:
        assert banks["de"].display(word) == expected


@pytest.mark.parametrize("word", ["abanmak", "abanabilme", "acıkabilme"])
def test_turkish_morphology_is_not_answers(banks, word):
    """Infinitives and potential-mood nominals are not guessable vocabulary."""
    assert not banks["tr"].is_target(word)
    assert banks["tr"].is_allowed(word)


def test_turkish_ascii_twins_are_not_answers(banks):
    """aksam is a transliteration artifact; akşam is the word."""
    assert banks["tr"].is_target("akşam")
    assert not banks["tr"].is_target("aksam")
    assert banks["tr"].is_allowed("aksam"), "still accepted if the player types it"


def test_picked_words_have_the_requested_length(banks):
    """The old fallback returned another length and made the game unwinnable."""
    for language in config.LANGUAGES:
        for length in range(wc.MIN_LEN, wc.MAX_LEN + 1):
            for difficulty in config.DIFFICULTIES:
                word = word_service.pick_target(language, length, difficulty)
                assert len(word) == length
                assert banks[language].is_allowed(word)


def test_pick_is_reproducible_with_a_seed(banks):
    first = banks["en"].pick(5, seed=1234)
    assert first is not None
    assert banks["en"].pick(5, seed=1234) == first


def test_tiers_partition_the_targets(banks):
    for language, bank in banks.items():
        for length in range(wc.MIN_LEN, wc.MAX_LEN + 1):
            total = bank.count_targets(length)
            by_tier = sum(bank.count_targets(length, tiers=(tier,)) for tier in wc.TIERS)
            assert by_tier == total, f"{language} length {length} tiers do not partition"


def test_difficulty_changes_the_pool():
    """Scholar was a no-op: it returned the same attempts and the same words."""
    chill = set(word_service.bank("en").targets(5, tiers=("common",)))
    scholar = set(word_service.bank("en").targets(5, tiers=("standard", "rare")))
    assert chill and scholar
    assert not (chill & scholar)


def test_attempts_by_difficulty():
    assert word_service.attempts_for(5, "chill") == word_service.attempts_for(5, "classic") + 1
    assert word_service.attempts_for(10, "chill") == config.MAX_ATTEMPTS


def test_suggestions_find_the_diacritic_spelling():
    """A player typing ASCII Turkish should be pointed at the real spelling."""
    assert "sebatlı" in word_service.suggest("tr", "sebatli", limit=5, same_length_only=True)
