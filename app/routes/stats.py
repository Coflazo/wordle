"""Dashboard stats route."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app import models
from app.database import get_db
from app.services import stats_service, word_service

router = APIRouter(prefix="/api/stats", tags=["stats"])


@router.get("/{profile_id}")
def dashboard(
    profile_id: int,
    language: str | None = Query(default=None),
    db: Session = Depends(get_db),
):
    p = db.get(models.Profile, profile_id)
    if p is None:
        raise HTTPException(status_code=404, detail="profile not found")
    return stats_service.dashboard(db, profile_id, language)


@router.get("/_debug/banks")
def banks_debug():
    return word_service.bank_summary()
