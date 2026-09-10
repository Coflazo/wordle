"""Dictionary meaning routes."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.services import dictionary_service, stats_service

router = APIRouter(prefix="/api/meaning", tags=["meanings"])


SUPPORTED_LANGS = {"en", "tr", "de"}


@router.get("/{language}/{word}")
async def meaning(
    language: str,
    word: str,
    profile_id: int | None = Query(default=None),
    db: Session = Depends(get_db),
):
    if language not in SUPPORTED_LANGS:
        raise HTTPException(
            status_code=400, detail=f"unsupported language: {language}"
        )
    payload = await dictionary_service.get_meaning(db, language, word)
    if profile_id is not None:
        stats_service.increment_meaning_opened(db, profile_id, word.lower(), language)
        db.commit()
    return payload
