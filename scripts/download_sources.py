"""Download the word-source files from upstream repos into app/data/raw/.

Idempotent: skips files that already exist.
"""

from __future__ import annotations

import sys
from pathlib import Path
from urllib.request import Request, urlopen

from scripts._common import RAW

SOURCES = [
    (
        "english/words_alpha.txt",
        "https://raw.githubusercontent.com/dwyl/english-words/master/words_alpha.txt",
    ),
    (
        "english/google-10000-english-usa.txt",
        # A pragmatic "common English" list to seed target picks.
        "https://raw.githubusercontent.com/first20hours/google-10000-english/master/google-10000-english-usa-no-swears.txt",
    ),
    (
        # utkusen/turkce-wordlist corpus (ASCII-transliterated; long words only).
        # Kept for completeness even though we no longer use it as the primary bank.
        "turkish/corpus.txt",
        "https://raw.githubusercontent.com/utkusen/turkce-wordlist/master/corpus.txt",
    ),
    (
        # Turkish word list with proper diacritics (ç ğ ı i ö ş ü), broad length range.
        "turkish/turkce-kelime-listesi.txt",
        "https://raw.githubusercontent.com/CanNuhlar/Turkce-Kelime-Listesi/master/turkce_kelime_listesi.txt",
    ),
    (
        # Second Turkish source with short words + full diacritics.
        "turkish/mertemin-words.txt",
        "https://raw.githubusercontent.com/mertemin/turkish-word-list/master/words.txt",
    ),
    (
        # German word list with proper umlauts and eszett, ~1.9M lines.
        "german/german-wordlist.txt",
        "https://raw.githubusercontent.com/enz/german-wordlist/master/words",
    ),
    (
        # Common German words — small curated list used to pick friendly targets.
        "german/derewo-common.txt",
        "https://raw.githubusercontent.com/hermitdave/FrequencyWords/master/content/2018/de/de_50k.txt",
    ),
]


def _download(rel: str, url: str) -> None:
    dst = RAW / rel
    dst.parent.mkdir(parents=True, exist_ok=True)
    if dst.exists() and dst.stat().st_size > 0:
        print(f"  ✓ {rel} exists ({dst.stat().st_size} bytes) — skipping")
        return

    print(f"  ↓ {rel}  ←  {url}")
    req = Request(url, headers={"User-Agent": "OflazWordle/0.1 (+download-sources)"})
    with urlopen(req, timeout=60) as resp:
        data = resp.read()
    dst.write_bytes(data)
    print(f"    wrote {len(data)} bytes")


def main() -> int:
    RAW.mkdir(parents=True, exist_ok=True)
    for rel, url in SOURCES:
        try:
            _download(rel, url)
        except Exception as e:
            print(f"  ! failed {rel}: {e}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
