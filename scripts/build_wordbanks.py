"""Build the .wbk word banks from the raw sources.

    python -m scripts.build_wordbanks              # fast: tiers from frequency
    python -m scripts.build_wordbanks --difficulty # also run the C++ solver sweep
    python -m scripts.build_wordbanks --skip-download

Tiers are what make the difficulty selector real. Before this, "Scholar" claimed
"rarer words" and did nothing at all — `attempts_for()` returned the same number
for classic and scholar, and no word-rarity filter existed anywhere.

    chill    -> common words only, plus one extra attempt
    classic  -> common + standard
    scholar  -> standard + rare

The split is per length bucket, so a 10-letter chill game still has a common
pool to draw from rather than falling back to whatever the global cut left.

With --difficulty, the frequency rank is blended with the number of turns a
greedy-entropy solver needs to reach each word (computed in C++, threaded). A
word can be common and still hard: "mummy" repeats letters and shares a rhyme
family, so it survives longer under optimal play than its frequency suggests.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import wordle_core as wc

from scripts import clean_english, clean_german, clean_turkish, download_sources
from scripts._common import BANKS, LANGUAGES, MAX_LEN, MIN_LEN, PROCESSED, Entry, report

# Share of each length bucket, most common first.
TIER_SPLIT = (("common", 0.30), ("standard", 0.45), ("rare", 0.25))

# Openers for the difficulty sweep. Fixed per language so a rebuild reproduces
# the same tiers; chosen by `best_opener` on the length-5 target pool.
SWEEP_OPENERS = {"en": "raise", "tr": "kalem", "de": "sauer"}

BUILDERS = {"en": clean_english.build, "tr": clean_turkish.build, "de": clean_german.build}

NO_RANK = 1 << 30


def assign_tiers(entries: dict[str, Entry], difficulty: dict[str, float] | None) -> None:
    """Split each length bucket into common / standard / rare."""
    by_length: dict[int, list[Entry]] = {}
    for entry in entries.values():
        if entry.is_target:
            by_length.setdefault(len(entry.fold), []).append(entry)

    for bucket in by_length.values():
        if difficulty:
            # Normalize turns into the same 0..1 scale as the rank position, then
            # weight frequency 70 / solver 30. Frequency is the stronger signal
            # for "have I met this word"; the solver only breaks ties sensibly.
            turns = [difficulty.get(e.fold, 0.0) for e in bucket]
            lo, hi = min(turns), max(turns)
            span = (hi - lo) or 1.0

            def blended(entry: Entry) -> float:
                base = float(entry.rank if entry.rank is not None else NO_RANK)
                hardness = (difficulty.get(entry.fold, lo) - lo) / span
                return base + hardness * len(bucket) * 0.43  # 0.30/0.70 of a full span

            bucket.sort(key=lambda e: (blended(e), e.fold))
        else:
            bucket.sort(key=lambda e: (e.rank if e.rank is not None else NO_RANK, e.fold))

        cut = 0
        total = len(bucket)
        for index, (name, share) in enumerate(TIER_SPLIT):
            end = total if index == len(TIER_SPLIT) - 1 else cut + round(total * share)
            for entry in bucket[cut:end]:
                entry.tier = name
            cut = end


def run_sweep(bank_path: Path, lang: str, budget: int) -> dict[str, float]:
    """Greedy-entropy solve turns per target, from the freshly written bank."""
    bank = wc.Bank(str(bank_path))
    opener = SWEEP_OPENERS.get(lang, "")
    out: dict[str, float] = {}
    for length in range(MIN_LEN, MAX_LEN + 1):
        if bank.count_targets(length) == 0:
            continue
        # The opener has to be the same length as the words it opens against.
        probe = opener if len(opener) == length else (bank.pick(length, seed=7) or "")
        if not probe:
            continue
        started = time.perf_counter()
        turns = bank.sweep_difficulty(length, probe, guess_budget=budget)
        out.update(turns)
        print(
            f"       len {length}: {len(turns)} words, opener {probe!r}, "
            f"{time.perf_counter() - started:.1f}s"
        )
    return out


def write_bank(lang: str, entries: dict[str, Entry]) -> Path:
    BANKS.mkdir(parents=True, exist_ok=True)
    path = BANKS / f"{lang}.wbk"
    wc.write_bank(str(path), lang, [e.as_bank_entry() for e in entries.values()])
    return path


def write_json_dump(lang: str, entries: dict[str, Entry]) -> None:
    """Dump the same data as sorted JSON, for eyeballing a data-quality diff.

    Nothing at runtime reads these — the app loads the .wbk. They are gitignored
    and opt-in via --emit-json, because a binary bank and a 8 MB JSON copy of it
    in the same commit is just two chances to disagree.
    """
    PROCESSED.mkdir(parents=True, exist_ok=True)
    targets = sorted(e.fold for e in entries.values() if e.is_target)
    allowed = sorted(entries)
    (PROCESSED / f"{lang}_targets.json").write_text(
        json.dumps(targets, ensure_ascii=False), encoding="utf-8"
    )
    (PROCESSED / f"{lang}_allowed.json").write_text(
        json.dumps(allowed, ensure_ascii=False), encoding="utf-8"
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--skip-download", action="store_true")
    parser.add_argument(
        "--difficulty",
        action="store_true",
        help="run the C++ solver sweep and blend it into the tier split (slow)",
    )
    parser.add_argument("--guess-budget", type=int, default=400)
    parser.add_argument("--languages", default=",".join(LANGUAGES))
    parser.add_argument(
        "--emit-json",
        action="store_true",
        help="also dump sorted JSON copies of each bank for diffing (gitignored)",
    )
    args = parser.parse_args(argv)

    langs = [lang.strip() for lang in args.languages.split(",") if lang.strip()]
    for lang in langs:
        if lang not in LANGUAGES:
            parser.error(f"unknown language {lang!r}; expected one of {', '.join(LANGUAGES)}")

    if not args.skip_download:
        print("[1] downloading raw sources …")
        download_sources.main()
    else:
        print("[1] skipping download")

    for step, lang in enumerate(langs, start=2):
        print(f"[{step}] building {lang} …")
        entries, blocked = BUILDERS[lang]()

        # Tiers need a bank to sweep against, so on the difficulty path the bank
        # is written twice: once with provisional tiers, once with final ones.
        assign_tiers(entries, None)
        path = write_bank(lang, entries)

        if args.difficulty:
            print(f"     sweeping {lang} difficulty …")
            turns = run_sweep(path, lang, args.guess_budget)
            assign_tiers(entries, turns)
            path = write_bank(lang, entries)

        if args.emit_json:
            write_json_dump(lang, entries)
        report(lang, entries, blocked)
        print(f"       wrote {path} ({path.stat().st_size / 1e6:.2f} MB)")

    print("done.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
