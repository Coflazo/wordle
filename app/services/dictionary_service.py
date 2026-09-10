"""Dispatch language-specific dictionary lookups, with a normalized payload and
a SQLite cache that expires misses."""

from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime, timedelta, timezone
from typing import Dict, Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app import config, models
from app.services import (
    english_dictionary_service,
    german_dictionary_service,
    tdk_service,
    wiktionary_service,
    word_service,
)

log = logging.getLogger("wordle.dictionary")

SOURCE_BY_LANG = {
    "en": ("dictionaryapi.dev", "Free Dictionary"),
    "tr": ("tdk-all-api", "TDK"),
    "de": ("openthesaurus", "OpenThesaurus"),
}

# Each language tries its preferred source, then Wiktionary. One upstream going
# quiet used to empty out a whole language: dictionaryapi.dev stopped answering
# and every English lookup returned nothing, with no second opinion to fall back
# on. Wiktionary covers all three, so it backs each of them up.
FALLBACK_LABEL = "Wiktionary"

# Give the diacritic retry chain a hard ceiling. Turkish used to try the word
# plus five spelling candidates one after another at 10 s each, so a single
# request could hang for a minute with nothing to cancel it.
TURKISH_RETRY_BUDGET = 6.0
TURKISH_MAX_CANDIDATES = 3


def _is_fresh(row: models.DictionaryCache) -> bool:
    if row.created_at is None:
        return False
    age = datetime.now(timezone.utc) - row.created_at
    if row.found:
        return age < timedelta(days=config.DICTIONARY_TTL_HIT_DAYS)
    # A miss expires quickly. Previously a failed en/de lookup was written to
    # the cache and served forever, so one upstream 503 poisoned that word
    # permanently — created_at existed but was never read.
    return age < timedelta(hours=config.DICTIONARY_TTL_MISS_HOURS)


async def get_meaning(db: Session, language: str, word: str) -> Dict:
    word_norm = word_service.fold(language, word)
    source_key, label = SOURCE_BY_LANG.get(language, ("unknown", "Dictionary"))

    cached = db.execute(
        select(models.DictionaryCache).where(
            models.DictionaryCache.language == language,
            models.DictionaryCache.word == word_norm,
            models.DictionaryCache.source == source_key,
        )
    ).scalars().first()

    if cached is not None and _is_fresh(cached):
        try:
            payload = json.loads(cached.response_json)
        except ValueError:
            payload = None
        if payload is not None:
            payload["from_cache"] = True
            payload["display"] = word_service.display(language, word_norm)
            return payload

    payload = await _fetch(language, word_norm, source_key, label)

    # Fall back when the primary source gave nothing, and top up when it gave
    # only related words. OpenThesaurus is a thesaurus: it answers German
    # lookups with synonyms and no definition at all, which tells a learner what
    # else to say but never what the word means.
    if not _has_definition(payload):
        fallback = await wiktionary_service.lookup(
            word_norm, language, display=word_service.display(language, word_norm)
        )
        if _has_definition(fallback):
            payload = _merge(payload, fallback, label)
        elif not _has_meaning(payload) and _has_meaning(fallback):
            payload = fallback

    if payload.get("source") != "wiktionary":
        payload["source"] = source_key
        # The canonical label, not whatever the adapter set. One of them
        # returned "German word context", shown to the player in every locale.
        payload["source_label"] = label
    else:
        payload["source_label"] = FALLBACK_LABEL
    payload.setdefault("word", word_norm)
    payload["display"] = word_service.display(language, word_norm)
    payload["language"] = language
    payload["fetched_at"] = datetime.now(timezone.utc).isoformat()
    payload["from_cache"] = False

    found = _has_meaning(payload)
    encoded = json.dumps(payload, ensure_ascii=False)
    simplified = _simplify(payload)

    if cached is None:
        db.add(
            models.DictionaryCache(
                language=language,
                word=word_norm,
                source=source_key,
                response_json=encoded,
                simplified_definition=simplified,
                found=1 if found else 0,
            )
        )
    else:
        cached.response_json = encoded
        cached.simplified_definition = simplified
        cached.found = 1 if found else 0
        cached.created_at = datetime.now(timezone.utc)
    db.commit()
    return payload


async def _fetch(language: str, word: str, source_key: str, label: str) -> Dict:
    if language == "en":
        return await english_dictionary_service.lookup(word)
    if language == "de":
        return await german_dictionary_service.lookup(word)
    if language == "tr":
        return await _fetch_turkish(word)
    return _empty_payload(word, language, source_key, label)


async def _fetch_turkish(word: str) -> Dict:
    """TDK, retrying through spelling candidates within one overall budget."""
    payload = await tdk_service.lookup(word)
    if _has_meaning(payload):
        return payload

    candidates = word_service.suggest(
        "tr", word, limit=TURKISH_MAX_CANDIDATES, same_length_only=False
    )
    if not candidates:
        return payload

    async def try_all() -> Optional[Dict]:
        # Concurrently, not one after another: the old chain was sequential and
        # unbounded, and the candidates are independent lookups.
        results = await asyncio.gather(
            *(tdk_service.lookup(candidate) for candidate in candidates),
            return_exceptions=True,
        )
        for result in results:
            if isinstance(result, dict) and _has_meaning(result):
                return result
        return None

    try:
        better = await asyncio.wait_for(try_all(), timeout=TURKISH_RETRY_BUDGET)
    except asyncio.TimeoutError:
        log.info("turkish retry budget exhausted for %r", word)
        return payload
    return better or payload


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
    for entry in payload.get("entries") or []:
        if entry.get("definition"):
            return entry["definition"][:280]
    similar = (payload.get("extras") or {}).get("similar")
    if similar:
        # No English prefix: this string is shown to a player who may be
        # reading the interface in Turkish or German.
        return ", ".join(similar[:5])
    return None


def _merge(primary: Dict, fallback: Dict, primary_label: str) -> Dict:
    """Wiktionary's definitions, keeping the primary source's synonyms and extras."""
    merged = dict(fallback)
    synonyms = [
        word
        for entry in primary.get("entries") or []
        for word in entry.get("synonyms") or []
    ]
    if synonyms and merged["entries"]:
        merged["entries"][0] = {**merged["entries"][0], "synonyms": synonyms[:8]}
    extras = {k: v for k, v in (primary.get("extras") or {}).items() if k != "error"}
    merged["extras"] = {**extras, **{k: v for k, v in (fallback.get("extras") or {}).items()
                                     if k != "error"}}
    merged["also_from"] = primary_label
    return merged


def _has_definition(payload: Dict) -> bool:
    """A real definition, not merely a list of related words."""
    return any((entry.get("definition") or "").strip() for entry in payload.get("entries") or [])


def _has_meaning(payload: Dict) -> bool:
    for entry in payload.get("entries") or []:
        if entry.get("definition"):
            return True
    extras = payload.get("extras") or {}
    return any(extras.get(key) for key in ("compounds", "proverbs", "similar"))
