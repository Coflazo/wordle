"""Dictionary source chain, offline behaviour, and HTML stripping.

No test here touches the network: every adapter is stubbed. The point is the
fallback logic, which is what broke when dictionaryapi.dev went quiet.
"""

from __future__ import annotations

import pytest

from app.database import SessionLocal
from app.services import dictionary_service, wiktionary_service


def payload(entries=None, extras=None, source="primary", label="Primary"):
    return {
        "word": "test",
        "phonetic": None,
        "audio_url": None,
        "entries": entries or [],
        "extras": extras or {},
        "source": source,
        "source_label": label,
    }


def entry(definition=None, synonyms=None):
    return {
        "part_of_speech": None,
        "definition": definition,
        "example": None,
        "synonyms": synonyms or [],
        "antonyms": [],
    }


# ------------------------------------------------------------ HTML stripping

def test_strip_html_removes_markup():
    raw = 'The <a rel="mw:WikiLink" href="/wiki/color">color</a> of grass.'
    assert wiktionary_service.strip_html(raw) == "The color of grass."


def test_strip_html_decodes_entities():
    assert wiktionary_service.strip_html("caf&eacute; &amp; bar") == "café & bar"


def test_strip_html_handles_empty():
    assert wiktionary_service.strip_html(None) == ""
    assert wiktionary_service.strip_html("") == ""


def test_strip_html_collapses_whitespace():
    assert wiktionary_service.strip_html("a\n\n  b   c") == "a b c"


# --------------------------------------------------------------- fallbacks

@pytest.mark.asyncio
async def test_falls_back_when_the_primary_is_empty(monkeypatch):
    async def dead_primary(word):
        return payload(extras={"error": "source_unreachable"})

    async def good_fallback(word, language, display=None):
        return payload([entry("a colour")], source="wiktionary", label="Wiktionary")

    monkeypatch.setattr(dictionary_service.english_dictionary_service, "lookup", dead_primary)
    monkeypatch.setattr(wiktionary_service, "lookup", good_fallback)

    with SessionLocal() as session:
        result = await dictionary_service.get_meaning(session, "en", "green")
    assert result["source_label"] == "Wiktionary"
    assert result["entries"][0]["definition"] == "a colour"


@pytest.mark.asyncio
async def test_merges_definitions_into_thesaurus_synonyms(monkeypatch):
    """OpenThesaurus answers German with synonyms and no definition at all."""

    async def thesaurus(word):
        return payload([entry(None, ["Apfelfrucht"])], source="openthesaurus")

    async def wiktionary(word, language, display=None):
        return payload([entry("apple")], source="wiktionary", label="Wiktionary")

    monkeypatch.setattr(dictionary_service.german_dictionary_service, "lookup", thesaurus)
    monkeypatch.setattr(wiktionary_service, "lookup", wiktionary)

    with SessionLocal() as session:
        result = await dictionary_service.get_meaning(session, "de", "apfel")
    assert result["entries"][0]["definition"] == "apple"
    assert result["entries"][0]["synonyms"] == ["Apfelfrucht"]
    assert result["also_from"] == "OpenThesaurus"


@pytest.mark.asyncio
async def test_primary_wins_when_it_has_a_definition(monkeypatch):
    async def primary(word):
        return payload([entry("the primary definition")])

    called = False

    async def fallback(word, language, display=None):
        nonlocal called
        called = True
        return payload([entry("the fallback")], source="wiktionary")

    monkeypatch.setattr(dictionary_service.english_dictionary_service, "lookup", primary)
    monkeypatch.setattr(wiktionary_service, "lookup", fallback)

    with SessionLocal() as session:
        result = await dictionary_service.get_meaning(session, "en", "unique1")
    assert result["entries"][0]["definition"] == "the primary definition"
    assert not called, "the fallback should not be consulted"


@pytest.mark.asyncio
async def test_both_sources_failing_reports_unreachable(monkeypatch):
    async def dead(word):
        return payload(extras={"error": "source_unreachable"})

    async def dead_fallback(word, language, display=None):
        return payload(extras={"error": "source_unreachable"}, source="wiktionary")

    monkeypatch.setattr(dictionary_service.english_dictionary_service, "lookup", dead)
    monkeypatch.setattr(wiktionary_service, "lookup", dead_fallback)

    with SessionLocal() as session:
        result = await dictionary_service.get_meaning(session, "en", "unique2")
    # The client renders "could not reach the dictionary", not "no definition".
    assert result["extras"]["error"] == "source_unreachable"
    assert result["entries"] == []


@pytest.mark.asyncio
async def test_a_miss_is_cached_but_expires(monkeypatch):
    """A single upstream outage used to poison a word permanently."""
    from datetime import datetime, timedelta, timezone

    from app import models

    calls = 0

    async def flaky(word):
        nonlocal calls
        calls += 1
        return payload(extras={"error": "source_unreachable"})

    async def dead_fallback(word, language, display=None):
        return payload(extras={"error": "source_unreachable"}, source="wiktionary")

    monkeypatch.setattr(dictionary_service.english_dictionary_service, "lookup", flaky)
    monkeypatch.setattr(wiktionary_service, "lookup", dead_fallback)

    with SessionLocal() as session:
        await dictionary_service.get_meaning(session, "en", "unique3")
        await dictionary_service.get_meaning(session, "en", "unique3")
        assert calls == 1, "the miss should be served from cache while fresh"

        row = session.query(models.DictionaryCache).filter_by(word="unique3").one()
        assert row.found == 0
        row.created_at = datetime.now(timezone.utc) - timedelta(days=1)
        session.commit()

        await dictionary_service.get_meaning(session, "en", "unique3")
    assert calls == 2, "an expired miss should be retried"
