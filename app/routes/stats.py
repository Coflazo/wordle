"""Profile dashboard."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app import config, models, schemas
from app.database import get_db
from app.errors import PROFILE_NOT_FOUND, NotFound
from app.services import solverd_client, stats_service, word_service

router = APIRouter(prefix="/api/stats", tags=["stats"])


@router.get("/{profile_id}", response_model=schemas.DashboardOut)
def dashboard(
    profile_id: int,
    # Typed as the Language literal, not a bare str: `?language=zz` used to
    # return an all-zero payload instead of a 422.
    language: schemas.Language | None = Query(default=None),
    db: Session = Depends(get_db),
):
    if db.get(models.Profile, profile_id) is None:
        raise NotFound(PROFILE_NOT_FOUND, "profile not found", profile_id=profile_id)
    return stats_service.dashboard(db, profile_id, language)


@router.get("/_debug/banks", include_in_schema=False)
def banks_debug():
    """Bank counts. Opening every bank costs real memory, so this is gated
    behind WORDLE_DEBUG=1 rather than being an open endpoint."""
    if not config.DEBUG_ENDPOINTS:
        raise NotFound("not_found", "not found")
    return {"banks": word_service.bank_summary(), "solverd": solverd_client.stats()}
