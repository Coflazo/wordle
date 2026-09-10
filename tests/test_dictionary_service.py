"""Dictionary lookup edge cases."""

from __future__ import annotations

import asyncio
import json

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app import models
from app.database import Base
from app.services import dictionary_service, word_service


def _session():
    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(bind=engine)
    return sessionmaker(bind=engine, future=True)()


def _tdk_payload(word: str, definition: str | None = None) -> dict:
    return {
        "word": word,
        "phonetic": None,
        "audio_url": None,
        "entries": (
            [
                {
                    "part_of_speech": "sıfat",
                    "definition": definition,
                    "example": None,
                    "synonyms": [],
                    "antonyms": [],
                }
            ]
            if definition
            else []
        ),
        "extras": {} if definition else {"error": "TDK'da bulunamadı"},
        "source": "tdk-all-api",
        "source_label": "TDK",
    }


def test_turkish_spelling_candidates_include_diacritic_form():
    assert "sebatlı" in word_service.turkish_spelling_candidates("sebatli")


def test_turkish_meaning_refreshes_empty_cache_with_diacritic_retry(monkeypatch):
    db = _session()
    db.add(
        models.DictionaryCache(
            language="tr",
            word="sebatli",
            source="tdk-all-api",
            response_json=json.dumps(_tdk_payload("sebatli"), ensure_ascii=False),
            simplified_definition=None,
        )
    )
    db.commit()

    calls = []

    async def fake_lookup(word: str):
        calls.append(word)
        if word == "sebatlı":
            return _tdk_payload(
                word,
                "Bir işi yılmadan sonuna kadar götüren; direşken, sebatkâr",
            )
        return _tdk_payload(word)

    monkeypatch.setattr(dictionary_service.tdk_service, "lookup", fake_lookup)

    payload = asyncio.run(dictionary_service.get_meaning(db, "tr", "sebatli"))

    assert calls == ["sebatli", "sebatlı"]
    assert payload["word"] == "sebatlı"
    assert payload["entries"][0]["definition"].startswith("Bir işi")
    assert payload["from_cache"] is False

    cached = db.query(models.DictionaryCache).filter_by(word="sebatli").one()
    assert cached.simplified_definition.startswith("Bir işi")
