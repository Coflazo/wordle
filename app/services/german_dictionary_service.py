"""OpenThesaurus adapter → normalized meaning payload."""

from __future__ import annotations

import asyncio
import time
from collections import deque
from typing import Deque, Dict

import httpx

BASE = "https://www.openthesaurus.de/synonyme/search"
UA = "OflazWordle/0.1 (contact: cagan04oflazoglu@gmail.com)"
TIMEOUT = httpx.Timeout(10.0)


# 60 requests / minute / IP — trivial token bucket.
_bucket_window = 60.0
_bucket_limit = 55  # keep 5 in reserve
_events: Deque[float] = deque()
_lock = asyncio.Lock()


async def _acquire() -> None:
    async with _lock:
        now = time.monotonic()
        while _events and now - _events[0] > _bucket_window:
            _events.popleft()
        if len(_events) >= _bucket_limit:
            wait = _bucket_window - (now - _events[0])
            if wait > 0:
                await asyncio.sleep(wait)
        _events.append(time.monotonic())


async def lookup(word: str) -> Dict:
    await _acquire()

    params = {
        "q": word,
        "format": "application/json",
        "similar": "true",
        "baseform": "true",
        "supersynsets": "true",
    }
    try:
        async with httpx.AsyncClient(
            timeout=TIMEOUT, headers={"User-Agent": UA}
        ) as client:
            resp = await client.get(BASE, params=params)
        if resp.status_code != 200:
            return _empty(word)
        data = resp.json()
    except Exception:
        return _empty(word)

    synonyms = []
    for synset in data.get("synsets", []) or []:
        for term in synset.get("terms", []) or []:
            if term.get("term") and term["term"].lower() != word.lower():
                synonyms.append(term["term"])
        if len(synonyms) >= 24:
            break

    similar_words = []
    for s in data.get("similarterms", []) or []:
        if s.get("term"):
            similar_words.append(s["term"])
    baseforms = data.get("baseforms", []) or []

    entries = []
    if synonyms:
        entries.append(
            {
                "part_of_speech": None,
                "definition": None,
                "example": None,
                "synonyms": synonyms[:12],
                "antonyms": [],
            }
        )

    return {
        "word": word,
        "phonetic": None,
        "audio_url": None,
        "entries": entries,
        "extras": {
            "similar": similar_words[:12],
            "baseforms": baseforms[:6],
        },
        "source": "openthesaurus",
        "source_label": "German word context",
    }


def _empty(word: str) -> Dict:
    return {
        "word": word,
        "phonetic": None,
        "audio_url": None,
        "entries": [],
        "extras": {"error": "Not found in OpenThesaurus"},
        "source": "openthesaurus",
        "source_label": "German word context",
    }
