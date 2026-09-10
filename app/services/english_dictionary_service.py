"""dictionaryapi.dev adapter, normalized to the shared meaning payload."""

from __future__ import annotations

import logging
from typing import Dict
from urllib.parse import quote

import httpx

from app import config

log = logging.getLogger("wordle.dictionary.en")

BASE = "https://api.dictionaryapi.dev/api/v2/entries/en"
# Separate connect and read budgets: a host that is refusing connections should
# fail fast, while a slow response is worth waiting on.
TIMEOUT = httpx.Timeout(config.DICTIONARY_TIMEOUT, connect=4.0)
MAX_DEFINITIONS_PER_SENSE = 3
MAX_RELATED = 8


async def lookup(word: str) -> Dict:
    # quote(), not raw interpolation. The word reaches this from a URL path
    # segment, and it used to be pasted straight into the outbound URL.
    url = f"{BASE}/{quote(word, safe='')}"
    try:
        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            response = await client.get(url)
    except httpx.HTTPError as exc:
        # Could not reach the dictionary. This is not the same as "this word
        # has no definition", and telling the player the latter is a lie — the
        # frontend renders a different message for each.
        log.info("dictionaryapi.dev unreachable for %r: %s", word, exc)
        return _empty(word, unreachable=True)

    if response.status_code == 404:
        return _empty(word)
    if response.status_code != 200:
        log.info("dictionaryapi.dev returned %s for %r", response.status_code, word)
        return _empty(word, unreachable=True)

    try:
        data = response.json()
    except ValueError:
        return _empty(word, unreachable=True)
    if not isinstance(data, list) or not data:
        return _empty(word)

    first = data[0]
    phonetic = first.get("phonetic")
    audio_url = None
    for item in first.get("phonetics") or []:
        if not phonetic and item.get("text"):
            phonetic = item["text"]
        if not audio_url and item.get("audio"):
            audio_url = item["audio"]

    entries = []
    for block in data:
        for sense in block.get("meanings") or []:
            part_of_speech = sense.get("partOfSpeech")
            for definition in (sense.get("definitions") or [])[:MAX_DEFINITIONS_PER_SENSE]:
                entries.append({
                    "part_of_speech": part_of_speech,
                    "definition": definition.get("definition"),
                    "example": definition.get("example"),
                    "synonyms": (definition.get("synonyms") or sense.get("synonyms") or [])[:MAX_RELATED],
                    "antonyms": (definition.get("antonyms") or sense.get("antonyms") or [])[:MAX_RELATED],
                })

    return {
        "word": word,
        "phonetic": phonetic,
        "audio_url": audio_url,
        "entries": entries,
        "extras": {},
        "source": "dictionaryapi.dev",
        "source_label": "Free Dictionary",
    }


def _empty(word: str, unreachable: bool = False) -> Dict:
    return {
        "word": word,
        "phonetic": None,
        "audio_url": None,
        "entries": [],
        # A code, not prose: the client renders its own localized message.
        "extras": {"error": "source_unreachable" if unreachable else "not_found"},
        "source": "dictionaryapi.dev",
        "source_label": "Free Dictionary",
    }
