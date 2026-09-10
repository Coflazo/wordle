"""Feature flags, event intake, and experiment results."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app import models, schemas
from app.database import get_db
from app.errors import PROFILE_NOT_FOUND, NotFound
from app.services import experiment_service

router = APIRouter(prefix="/api", tags=["experiments"])


@router.get("/flags", response_model=schemas.FlagsOut)
def flags(
    profile_id: int | None = Query(default=None),
    db: Session = Depends(get_db),
):
    """Arm assignment for this profile. Safe to call before a profile exists."""
    if profile_id is not None and db.get(models.Profile, profile_id) is None:
        raise NotFound(PROFILE_NOT_FOUND, "profile not found", profile_id=profile_id)
    return schemas.FlagsOut(
        profile_id=profile_id,
        assignments=experiment_service.flags_for(db, profile_id),
    )


@router.post("/events", status_code=202)
def events(body: schemas.EventBatch, db: Session = Depends(get_db)):
    """Batched client telemetry. Local only — this never leaves the machine."""
    profile_id = body.profile_id
    if profile_id is not None and db.get(models.Profile, profile_id) is None:
        # Drop rather than reject: a stale profile id in localStorage should not
        # turn a fire-and-forget beacon into a visible error.
        profile_id = None
    written = experiment_service.record_events(
        db, profile_id, [event.model_dump() for event in body.events]
    )
    return {"accepted": written}


@router.get("/experiments/results", response_model=schemas.ExperimentsOut)
def results(db: Session = Depends(get_db)):
    return schemas.ExperimentsOut(experiments=experiment_service.results(db))
