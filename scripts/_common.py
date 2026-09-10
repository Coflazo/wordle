"""Shared plumbing for the word-bank builders.

Validation delegates to the native core rather than re-implementing alphabets in
Python. That is the point: a word is folded and alphabet-checked by exactly the
same code the runtime guess path uses, so a word can never be stored in one form
and rejected in another at play time.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

import wordle_core as wc

from scripts.blocklist import allowed_as_target, allowed_in_bank, block_reason

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "app" / "data" / "raw"
PROCESSED = ROOT / "app" / "data" / "processed"
BANKS = ROOT / "app" / "data" / "banks"

MIN_LEN = wc.MIN_LEN
MAX_LEN = wc.MAX_LEN
LANGUAGES = ("en", "tr", "de")

# Anything with these anywhere in it is not a single word.
NON_WORD = re.compile(r"[\s\-'’.,;:!?/\\_()\[\]{}\"“”0-9]")


@dataclass
class Entry:
    """One word on its way into a bank."""

    fold: str
    display: str
    is_target: bool = False
    tier: str = "standard"
    # Lower is more common. None means "no frequency evidence for this word".
    rank: int | None = None
    # Free-form provenance, printed by the build report.
    sources: set[str] = field(default_factory=set)

    def as_bank_entry(self) -> dict:
        return {
            "fold": self.fold,
            "display": self.display,
            "is_target": self.is_target,
            "tier": self.tier,
        }


def normalize(raw: str, lang: str) -> str | None:
    """Fold a raw source word, or None if it is not a playable word.

    Rejects on: junk characters, length, and any letter outside the language's
    alphabet. Length is measured after folding, which matters — Python's
    `'İSTANBUL'.lower()` is 9 characters for an 8-letter word.
    """
    raw = raw.strip()
    if not raw or NON_WORD.search(raw):
        return None
    folded = wc.fold(raw, lang)
    if not (MIN_LEN <= len(folded) <= MAX_LEN):
        return None
    if not wc.encodable(folded, lang):
        return None
    if not allowed_in_bank(folded):
        return None
    return folded


def read_lines(path: Path) -> list[str]:
    if not path.exists():
        return []
    text = path.read_text(encoding="utf-8", errors="ignore")
    return [line.strip() for line in text.splitlines() if line.strip()]


def read_ranked(path: Path) -> list[tuple[str, int]]:
    """Read a frequency list. Accepts bare words or '<word> <count>' lines.

    Returns (word, rank) with rank 0 for the most frequent word. Rank, not raw
    count, because the two sources use incomparable count scales.
    """
    out: list[tuple[str, int]] = []
    for i, line in enumerate(read_lines(path)):
        word = line.split()[0].strip() if " " in line or "\t" in line else line
        if word:
            out.append((word, i))
    return out


def bucket_summary(words: list[str]) -> dict[int, int]:
    out = {length: 0 for length in range(MIN_LEN, MAX_LEN + 1)}
    for w in words:
        if len(w) in out:
            out[len(w)] += 1
    return out


def apply_target_policy(entries: dict[str, Entry]) -> dict[str, int]:
    """Demote blocked words from target to allowed-only. Returns a reason tally."""
    tally: dict[str, int] = {}
    for entry in entries.values():
        if not entry.is_target:
            continue
        reason = block_reason(entry.fold)
        if reason is not None:
            entry.is_target = False
            tally[reason] = tally.get(reason, 0) + 1
    return tally


def report(lang: str, entries: dict[str, Entry], blocked: dict[str, int]) -> None:
    targets = [e.fold for e in entries.values() if e.is_target]
    tiers: dict[str, int] = {}
    for e in entries.values():
        if e.is_target:
            tiers[e.tier] = tiers.get(e.tier, 0) + 1
    blocked_note = ", ".join(f"{k}={v}" for k, v in sorted(blocked.items())) or "none"
    print(
        f"  {lang.upper()}: targets={len(targets)} allowed={len(entries)}\n"
        f"       buckets={bucket_summary(targets)}\n"
        f"       tiers={tiers}  blocked={blocked_note}"
    )


# Kept so tests and any external caller written against the old helper still
# work. The pipeline itself uses `normalize`, which also folds.
def is_valid(word: str, lang: str) -> bool:
    return normalize(word, lang) is not None


__all__ = [
    "ROOT", "RAW", "PROCESSED", "BANKS", "MIN_LEN", "MAX_LEN", "LANGUAGES",
    "Entry", "normalize", "read_lines", "read_ranked", "bucket_summary",
    "apply_target_policy", "report", "is_valid", "allowed_as_target",
]
