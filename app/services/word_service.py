"""Word banks, backed by the native memory-mapped bank.

Previously this module parsed six JSON files into Python lists and then built
sets from the same strings, which measured 121 ms of parsing and 74 MB resident
with both copies alive. A .wbk is mmap'd instead: opening one is a syscall, the
pages are shared between processes, and membership is a binary search over
packed letter codes with no allocation.
"""

from __future__ import annotations

import random
import threading
from typing import Dict, List, Sequence

import wordle_core as wc

from app import config
from app.errors import BANK_UNAVAILABLE, NO_WORDS, Unavailable, Unprocessable

_banks: Dict[str, wc.Bank] = {}
_lock = threading.Lock()


def bank(language: str) -> wc.Bank:
    """Open (once) and return the bank for a language."""
    existing = _banks.get(language)
    if existing is not None:
        return existing
    if language not in config.LANGUAGES:
        raise Unprocessable("unsupported_language", f"unsupported language: {language}")
    with _lock:
        existing = _banks.get(language)
        if existing is not None:
            return existing
        path = config.BANK_DIR / f"{language}.wbk"
        try:
            opened = wc.Bank(str(path))
        except Exception as exc:  # missing, truncated, or a stale format version
            raise Unavailable(
                BANK_UNAVAILABLE,
                f"word bank for {language} is unavailable: {exc}. "
                "Run: python -m scripts.build_wordbanks",
            ) from exc
        _banks[language] = opened
        return opened


def warm_up() -> None:
    """Open every bank at startup so a missing one fails loudly, not mid-game."""
    for language in config.LANGUAGES:
        bank(language)


def fold(language: str, word: str) -> str:
    """Locale-correct lowercase. See native/src/normalize.cpp for why."""
    return wc.fold(word, language)


def display(language: str, word: str) -> str:
    """Presentation form — German nouns keep their capital."""
    return bank(language).display(word)


def is_allowed_guess(language: str, word: str) -> bool:
    return bank(language).is_allowed(word)


def tiers_for(difficulty: str) -> Sequence[str]:
    return config.TIERS_BY_DIFFICULTY.get(difficulty, config.TIERS_BY_DIFFICULTY["classic"])


def attempts_for(word_length: int, difficulty: str = "classic") -> int:
    if word_length not in config.ATTEMPTS_BY_LENGTH:
        low, high = min(config.ATTEMPTS_BY_LENGTH), max(config.ATTEMPTS_BY_LENGTH)
        raise Unprocessable(
            "unsupported_length",
            f"word length must be {low}..{high}, got {word_length}",
            word_length=word_length,
        )
    base = config.ATTEMPTS_BY_LENGTH[word_length]
    if difficulty == "chill":
        return base + config.CHILL_BONUS_ATTEMPTS
    return base


def sample_length(language: str, difficulty: str) -> int:
    """Draw a length from the configured distribution, skipping empty buckets."""
    tiers = tiers_for(difficulty)
    b = bank(language)
    lengths = [
        length
        for length in config.LENGTH_DISTRIBUTION
        if b.count_targets(length, tiers=tiers) > 0
    ]
    if not lengths:
        raise Unavailable(BANK_UNAVAILABLE, f"no playable words for {language}/{difficulty}")
    weights = [config.LENGTH_DISTRIBUTION[length] for length in lengths]
    return random.choices(lengths, weights=weights, k=1)[0]


def pick_target(language: str, word_length: int, difficulty: str = "classic") -> str:
    """Pick an answer of exactly `word_length` letters.

    Unlike the previous implementation this never falls back to a different
    length. That fallback stored the requested length on the game while the
    answer had another, so every subsequent guess failed the length check and the
    game was unwinnable.
    """
    tiers = tiers_for(difficulty)
    b = bank(language)
    word = b.pick(word_length, tiers=tiers)
    if word is None:
        raise Unprocessable(
            NO_WORDS,
            f"no {word_length}-letter words for {language} at difficulty {difficulty}",
            language=language,
            word_length=word_length,
        )
    assert len(word) == word_length, "bank returned a word of the wrong length"
    return word


def suggest(language: str, word: str, limit: int = 3, same_length_only: bool = True) -> List[str]:
    """"Did you mean" candidates, for a guess that was not in the bank."""
    return bank(language).suggest(
        word, limit=limit, max_distance=2, same_length_only=same_length_only
    )


def bank_summary() -> Dict[str, Dict[str, object]]:
    """Diagnostics. Only reachable when WORDLE_DEBUG=1."""
    out: Dict[str, Dict[str, object]] = {}
    for language in config.LANGUAGES:
        b = bank(language)
        out[language] = {
            "targets": b.target_count,
            "allowed": b.allowed_count,
            "by_length": {
                str(length): {
                    "targets": b.count_targets(length),
                    "allowed": b.count_allowed(length),
                    **{
                        tier: b.count_targets(length, tiers=(tier,))
                        for tier in wc.TIERS
                    },
                }
                for length in range(wc.MIN_LEN, wc.MAX_LEN + 1)
            },
        }
    return out
