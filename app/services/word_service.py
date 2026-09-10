"""Word bank loading and target selection."""

from __future__ import annotations

import json
import random
from functools import lru_cache
from pathlib import Path
from typing import Dict, List, Set

DATA_DIR = Path(__file__).resolve().parent.parent / "data" / "processed"

# Attempts by length + difficulty modifier.
ATTEMPTS_BY_LENGTH = {5: 6, 6: 7, 7: 7, 8: 8, 9: 8, 10: 9}

# Length distribution for random draws.
LENGTH_DISTRIBUTION = {5: 0.35, 6: 0.25, 7: 0.15, 8: 0.10, 9: 0.08, 10: 0.07}

TR_ASCII_FOLD = str.maketrans(
    {
        "ç": "c",
        "ğ": "g",
        "ı": "i",
        "ö": "o",
        "ş": "s",
        "ü": "u",
    }
)


@lru_cache(maxsize=8)
def _load_bank(language: str, kind: str) -> List[str]:
    """Return the processed word bank for (language, kind='targets'|'allowed')."""
    path = DATA_DIR / f"{language}_{kind}.json"
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8") as fh:
        return json.load(fh)


@lru_cache(maxsize=8)
def _allowed_set(language: str) -> Set[str]:
    """Frozen set for O(1) guess validation. Includes targets ∪ allowed."""
    return set(_load_bank(language, "targets")) | set(_load_bank(language, "allowed"))


@lru_cache(maxsize=32)
def _targets_by_length(language: str, length: int) -> List[str]:
    return [w for w in _load_bank(language, "targets") if len(w) == length]


def is_allowed_guess(language: str, word: str) -> bool:
    return word.lower() in _allowed_set(language)


def _fold_turkish_ascii(word: str) -> str:
    return word.translate(TR_ASCII_FOLD)


@lru_cache(maxsize=1)
def _turkish_spelling_index() -> Dict[str, List[str]]:
    target_words = set(_load_bank("tr", "targets"))
    index: Dict[str, List[str]] = {}
    for word in _allowed_set("tr"):
        folded = _fold_turkish_ascii(word)
        if folded == word:
            continue
        index.setdefault(folded, []).append(word)

    for folded, words in index.items():
        words.sort(key=lambda w: (0 if w in target_words else 1, len(w), w))
    return index


def turkish_spelling_candidates(word: str, limit: int = 5) -> List[str]:
    norm = word.strip().lower()
    return [w for w in _turkish_spelling_index().get(norm, []) if w != norm][:limit]


def sample_length(exclude: List[int] | None = None) -> int:
    """Sample a word length from the recommended distribution."""
    lengths = [l for l in LENGTH_DISTRIBUTION if not exclude or l not in exclude]
    weights = [LENGTH_DISTRIBUTION[l] for l in lengths]
    return random.choices(lengths, weights=weights, k=1)[0]


def pick_target(language: str, word_length: int) -> str:
    """Pick a random target word of the requested length."""
    pool = _targets_by_length(language, word_length)
    if not pool:
        # Fall back to any length that has words.
        for candidate_length in [5, 6, 7, 8, 9, 10]:
            pool = _targets_by_length(language, candidate_length)
            if pool:
                break
    if not pool:
        raise RuntimeError(f"No target words for language={language}")
    return random.choice(pool)


def attempts_for(word_length: int, difficulty: str = "classic") -> int:
    base = ATTEMPTS_BY_LENGTH.get(word_length, 6)
    if difficulty == "chill":
        return base + 1
    return base


def bank_summary() -> Dict[str, Dict[str, int]]:
    """Diagnostics: counts by (language, length)."""
    out: Dict[str, Dict[str, int]] = {}
    for lang in ("en", "tr", "de"):
        buckets: Dict[str, int] = {}
        for length in range(5, 11):
            buckets[str(length)] = len(_targets_by_length(lang, length))
        buckets["allowed_total"] = len(_allowed_set(lang))
        out[lang] = buckets
    return out
