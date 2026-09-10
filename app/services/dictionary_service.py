"""Dispatch language-specific dictionary lookups with a normalized payload + SQLite cache."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Dict, Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app import models
from app.services import (
    english_dictionary_service,
    german_dictionary_service,
    tdk_service,
    word_service,
)

SOURCE_BY_LANG = {
    "en": ("dictionaryapi.dev", "Free Dictionary"),
    "tr": ("tdk-all-api", "TDK"),
    "de": ("openthesaurus", "German word context"),
}


async def get_meaning(db: Session, language: str, word: str) -> Dict:
    """Return normalized meaning payload; consult cache first."""
    word_norm = word.strip().lower()
    source_key, label = SOURCE_BY_LANG.get(language, ("unknown", "Dictionary"))

    cached = (
        db.execute(
            select(models.DictionaryCache).where(
                models.DictionaryCache.language == language,
                models.DictionaryCache.word == word_norm,
                models.DictionaryCache.source == source_key,
            )
        )
        .scalars()
        .first()
    )
    if cached is not None:
        payload = json.loads(cached.response_json)
        if language != "tr" or _has_meaning(payload):
            payload["from_cache"] = True
            return payload

    if language == "en":
        payload = await english_dictionary_service.lookup(word_norm)
    elif language == "tr":
        payload = await tdk_service.lookup(word_norm)
        if not _has_meaning(payload):
            for candidate in word_service.turkish_spelling_candidates(word_norm):
                candidate_payload = await tdk_service.lookup(candidate)
                if _has_meaning(candidate_payload):
                    payload = candidate_payload
                    break
    elif language == "de":
        payload = await german_dictionary_service.lookup(word_norm)
    else:
        payload = _empty_payload(word_norm, language, source_key, label)

    payload.setdefault("source", source_key)
    payload.setdefault("source_label", label)
    payload.setdefault("word", word_norm)
    payload["language"] = language
    payload["fetched_at"] = datetime.now(timezone.utc).isoformat()
    payload["from_cache"] = False

    simplified = _simplify(payload)

    if cached is None:
        row = models.DictionaryCache(
            language=language,
            word=word_norm,
            source=source_key,
            response_json=json.dumps(payload, ensure_ascii=False),
            simplified_definition=simplified,
        )
        db.add(row)
    else:
        cached.response_json = json.dumps(payload, ensure_ascii=False)
        cached.simplified_definition = simplified
    db.commit()
    return payload


def _empty_payload(word: str, language: str, source: str, label: str) -> Dict:
    return {
        "word": word,
        "language": language,
        "source": source,
        "source_label": label,
        "phonetic": None,
        "audio_url": None,
        "entries": [],
        "extras": {},
    }


def _simplify(payload: Dict) -> Optional[str]:
    entries = payload.get("entries") or []
    for e in entries:
        if e.get("definition"):
            return e["definition"][:280]
    if payload.get("extras", {}).get("similar"):
        return "Similar: " + ", ".join(payload["extras"]["similar"][:5])
    return None


def _has_meaning(payload: Dict) -> bool:
    for entry in payload.get("entries") or []:
        if entry.get("definition"):
            return True
    extras = payload.get("extras") or {}
    return any(extras.get(key) for key in ("compounds", "proverbs", "similar"))
