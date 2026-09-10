"""The bank build pipeline: validation, blocklists, and morphology filters."""

from __future__ import annotations

import pytest

from scripts._common import MAX_LEN, MIN_LEN, normalize
from scripts.blocklist import allowed_as_target, allowed_in_bank, block_reason
from scripts.clean_turkish import _derivational_depth, _is_infinitive, _is_potential


@pytest.mark.parametrize("word,language", [
    ("crane", "en"), ("kalem", "tr"), ("straße", "de"), ("häuser", "de"), ("kızıl", "tr"),
])
def test_valid_words_survive(word, language):
    assert normalize(word, language) == word


@pytest.mark.parametrize("word,language", [
    ("cat", "en"),                 # too short
    ("extraordinary", "en"),       # too long
    ("ice cream", "en"),           # space
    ("mother-in-law", "en"),       # hyphen
    ("don't", "en"),               # apostrophe
    ("crane5", "en"),              # digit
    ("qwxyz", "tr"),               # q, w and x are not Turkish letters
    ("müde", "en"),                # ü is not English
    ("naïve", "en"),
])
def test_invalid_words_are_dropped(word, language):
    assert normalize(word, language) is None


def test_normalize_folds_before_measuring_length():
    """Length is measured after folding.

    'İSTANBUL'.lower() is nine codepoints, so a naive length check treated an
    eight-letter word as nine and threw it out.
    """
    assert normalize("İSTANBUL", "tr") == "istanbul"
    assert normalize("KIZIL", "tr") == "kızıl"


def test_length_bounds():
    assert normalize("a" * (MIN_LEN - 1), "en") is None
    assert normalize("a" * MIN_LEN, "en") is not None
    assert normalize("a" * MAX_LEN, "en") is not None
    assert normalize("a" * (MAX_LEN + 1), "en") is None


def test_slurs_never_enter_the_bank():
    assert not allowed_in_bank("nigger")
    assert normalize("nigger", "en") is None


def test_vulgar_words_stay_guessable_but_are_not_answers():
    assert allowed_in_bank("bitch")
    assert not allowed_as_target("bitch")
    assert block_reason("bitch") == "not_as_answer"


def test_proper_nouns_are_flagged():
    assert block_reason("istanbul") == "proper_noun"
    assert block_reason("giuseppe") == "proper_noun"
    assert block_reason("crane") is None


@pytest.mark.parametrize("word", ["abanmak", "gelmek", "yazmak", "gitmek"])
def test_infinitives_are_detected(word):
    assert _is_infinitive(word)


@pytest.mark.parametrize("word", ["kalem", "akşam", "merhem"])
def test_ordinary_words_are_not_infinitives(word):
    assert not _is_infinitive(word)


@pytest.mark.parametrize("word", ["abanabilme", "acıkabilme", "gelebilme"])
def test_potential_mood_is_detected(word):
    assert _is_potential(word)


def test_derivational_depth_grows_with_suffixes():
    assert _derivational_depth("kalem") == 0
    assert _derivational_depth("kalemlik") > _derivational_depth("kalem")
    assert _derivational_depth("kafasızlık") >= 1
