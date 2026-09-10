"""Scoring, including a differential test against an independent reference."""

from __future__ import annotations

import random

import pytest
import wordle_core as wc

from app.services.game_service import score_guess


def reference_score(answer: str, guess: str) -> list[str]:
    """The two-pass algorithm, written plainly.

    This is deliberately a separate implementation from the C++ one. Its whole
    job is to disagree if the optimized version ever drifts.
    """
    answer_chars = list(answer)
    guess_chars = list(guess)
    result = ["gray"] * len(guess_chars)
    remaining: dict[str, int] = {}

    for i, ch in enumerate(answer_chars):
        if guess_chars[i] == ch:
            result[i] = "green"
        else:
            remaining[ch] = remaining.get(ch, 0) + 1

    for i, ch in enumerate(guess_chars):
        if result[i] == "green":
            continue
        if remaining.get(ch, 0) > 0:
            result[i] = "yellow"
            remaining[ch] -= 1
    return result


@pytest.mark.parametrize(
    "answer,guess,expected",
    [
        ("crane", "crane", ["green"] * 5),
        ("crane", "boils", ["gray"] * 5),
        # The classic duplicate-letter case: only one E can be credited, and the
        # green one claims it, so the guess's first E scores gray.
        ("speed", "erase", ["yellow", "gray", "gray", "yellow", "yellow"]),
        ("kayak", "aaaaa", ["gray", "green", "gray", "green", "gray"]),
        ("level", "hello", ["gray", "green", "yellow", "yellow", "gray"]),
        # b and e land in place; the leading b and a are present but misplaced.
        ("abbey", "babes", ["yellow", "yellow", "green", "green", "gray"]),
    ],
)
def test_known_cases(answer, guess, expected):
    assert score_guess(answer, guess, "en") == expected
    assert reference_score(answer, guess) == expected


@pytest.mark.parametrize("language,alphabet", [
    ("en", "abcdefghijklmnopqrstuvwxyz"),
    ("tr", "abcçdefgğhıijklmnoöprsştuüvyz"),
    ("de", "abcdefghijklmnopqrstuvwxyzäöüß"),
])
def test_matches_reference_on_random_words(language, alphabet):
    """The native scorer must agree with the reference on every input.

    Random words rather than dictionary words on purpose: dense repeats are
    where duplicate-letter budgeting goes wrong, and a real word list barely
    exercises them.
    """
    rng = random.Random(20260910)
    letters = list(alphabet)
    for _ in range(4000):
        length = rng.randint(5, 10)
        # A small pool most of the time, so repeats are common.
        pool = rng.sample(letters, rng.choice([2, 3, 4, len(letters)]))
        answer = "".join(rng.choice(pool) for _ in range(length))
        guess = "".join(rng.choice(pool) for _ in range(length))
        assert score_guess(answer, guess, language) == reference_score(answer, guess), (
            f"{language}: {answer} vs {guess}"
        )


def test_all_green_only_when_equal():
    rng = random.Random(7)
    for _ in range(500):
        length = rng.randint(5, 10)
        answer = "".join(rng.choice("abcde") for _ in range(length))
        guess = "".join(rng.choice("abcde") for _ in range(length))
        all_green = all(mark == "green" for mark in score_guess(answer, guess, "en"))
        assert all_green == (answer == guess)


def test_score_rejects_mismatched_lengths():
    with pytest.raises(ValueError):
        wc.score("crane", "boil", "en")


def test_score_rejects_letters_outside_the_alphabet():
    # q, w and x are not Turkish letters.
    with pytest.raises(ValueError):
        wc.score("kalem", "qwxyz", "tr")
