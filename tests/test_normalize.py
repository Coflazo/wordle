"""Locale-aware normalization.

Each of these is a bug that shipped: invariant str.lower() rejected valid
Turkish words and miscounted their length.
"""

from __future__ import annotations

import pytest
import wordle_core as wc


@pytest.mark.parametrize("raw,expected", [
    # The headline case. Python's str.lower() gives 'i̇stanbul' — nine
    # codepoints for an eight-letter word — so the length check reported
    # "expected 8, got 9" and the guess could never be accepted.
    ("İSTANBUL", "istanbul"),
    ("İyi", "iyi"),
    # Dotless i. str.lower() gives 'kizil', which is not a word, so a valid
    # guess came back as "not in dictionary".
    ("KIZIL", "kızıl"),
    ("IŞIK", "ışık"),
    ("kızıl", "kızıl"),
    ("SEBATKÂR", "sebatkâr"),
    ("ÇÖĞÜŞ", "çöğüş"),
])
def test_turkish_folding(raw, expected):
    assert wc.fold(raw, "tr") == expected


def test_turkish_length_is_preserved():
    assert len(wc.fold("İSTANBUL", "tr")) == 8
    assert len("İSTANBUL".lower()) == 9  # what the old code did


@pytest.mark.parametrize("raw,expected", [
    ("STRASSE", "strasse"),
    ("Straße", "straße"),
    ("MÜDE", "müde"),
    ("GROẞ", "groß"),  # U+1E9E capital sharp s
    ("Äpfel", "äpfel"),
])
def test_german_folding(raw, expected):
    assert wc.fold(raw, "de") == expected


@pytest.mark.parametrize("locale", ["en", "de"])
def test_dotted_capital_i_outside_turkish(locale):
    """İ folds to a plain i rather than i + a combining dot above."""
    assert wc.fold("İ", locale) == "i"
    assert len(wc.fold("İ", locale)) == 1


def test_turkish_case_round_trip():
    for word in ["kızıl", "istanbul", "ilik", "ışık", "çiğdem"]:
        assert wc.fold(wc.upper(word, "tr"), "tr") == word


def test_decomposed_input_is_composed():
    """A keyboard that emits u + combining diaeresis must match the bank.

    Nothing normalized before, so a decomposed umlaut missed the bank entirely.
    """
    decomposed = "müde"
    assert len(decomposed) == 5
    assert wc.fold(decomposed, "de") == "müde"
    assert len(wc.fold(decomposed, "de")) == 4

    decomposed_tr = "çiğdem"
    assert wc.fold(decomposed_tr, "tr") == "çiğdem"


def test_whitespace_is_trimmed():
    assert wc.fold("  crane \n", "en") == "crane"


@pytest.mark.parametrize("word,expected", [
    ("sebatkâr", "sebatkar"),
    ("akşam", "aksam"),
    ("müde", "muede" if False else "mude"),
    ("straße", "strasse"),
])
def test_deaccent(word, expected):
    assert wc.deaccent(word) == expected


def test_alphabets_fit_five_bits():
    """The packing everywhere else depends on this."""
    for language in wc.LANGUAGES:
        assert len(wc.alphabet(language)) <= 32


def test_encodable_rejects_foreign_letters():
    assert wc.encodable("kalem", "tr")
    assert not wc.encodable("qwxyz", "tr")   # q, w, x are not Turkish
    assert wc.encodable("müde", "de")
    assert not wc.encodable("müde", "en")     # ü is not English
