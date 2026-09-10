"""dictionaryapi.dev adapter → normalized meaning payload."""

from __future__ import annotations

from typing import Dict

import httpx

BASE = "https://api.dictionaryapi.dev/api/v2/entries/en"
TIMEOUT = httpx.Timeout(10.0)


async def lookup(word: str) -> Dict:
    url = f"{BASE}/{word}"
    try:
        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            resp = await client.get(url)
        if resp.status_code != 200:
            return _empty(word)
        data = resp.json()
    except Exception:
        return _empty(word)

    if not isinstance(data, list) or not data:
        return _empty(word)

    entry0 = data[0]
    phonetic = entry0.get("phonetic")
    if not phonetic:
        for p in entry0.get("phonetics", []) or []:
            if p.get("text"):
                phonetic = p["text"]
                break
    audio_url = None
    for p in entry0.get("phonetics", []) or []:
        if p.get("audio"):
            audio_url = p["audio"]
            break

    entries = []
    for e in data:
        for m in e.get("meanings", []) or []:
            pos = m.get("partOfSpeech")
            defs = m.get("definitions", []) or []
            for d in defs[:3]:
                entries.append(
                    {
                        "part_of_speech": pos,
                        "definition": d.get("definition"),
                        "example": d.get("example"),
                        "synonyms": (d.get("synonyms") or m.get("synonyms") or [])[:8],
                        "antonyms": (d.get("antonyms") or m.get("antonyms") or [])[:8],
                    }
                )

    return {
        "word": word,
        "phonetic": phonetic,
        "audio_url": audio_url,
        "entries": entries,
        "extras": {},
        "source": "dictionaryapi.dev",
        "source_label": "Free Dictionary",
    }


def _empty(word: str) -> Dict:
    return {
        "word": word,
        "phonetic": None,
        "audio_url": None,
        "entries": [],
        "extras": {"error": "Word not found in Free Dictionary"},
        "source": "dictionaryapi.dev",
        "source_label": "Free Dictionary",
    }
