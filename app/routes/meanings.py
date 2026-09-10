"""Dictionary lookups."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app import config, models, schemas
from app.database import get_db
from app.errors import UNSUPPORTED_LANGUAGE, Unprocessable
from app.services import dictionary_service, stats_service, word_service

router = APIRouter(prefix="/api/meaning", tags=["meaning"])


@router.get("/{language}/{word}", response_model=schemas.MeaningOut)
async def meaning(
    language: str,
    word: str,
    profile_id: int | None = Query(default=None),
    db: Session = Depends(get_db),
):
    if language not in config.LANGUAGES:
        raise Unprocessable(
            UNSUPPORTED_LANGUAGE, f"unsupported language: {language}", language=language
        )

    word_norm = word_service.fold(language, word)
    payload = await dictionary_service.get_meaning(db, language, word_norm)

    # Only credit progress for a profile that exists. Foreign keys are enforced
    # now, but an invented id would raise mid-request rather than being ignored,
    # and this endpoint should not fail because of a stale localStorage value.
    if profile_id is not None and db.get(models.Profile, profile_id) is not None:
        stats_service.increment_meaning_opened(db, profile_id, word_norm, language)
        db.commit()

    return payload
