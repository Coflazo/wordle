"""Profile CRUD."""

from __future__ import annotations

import json
import logging

from fastapi import APIRouter, Depends, Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import models, schemas
from app.database import get_db
from app.errors import PROFILE_NOT_FOUND, NotFound

log = logging.getLogger("wordle.profiles")
router = APIRouter(prefix="/api/profiles", tags=["profiles"])


def _to_out(profile: models.Profile) -> dict:
    try:
        avatar_config = json.loads(profile.avatar_config_json or "{}")
    except ValueError:
        # One malformed row used to 500 the whole list endpoint.
        log.warning("profile %s has unparseable avatar_config; serving {}", profile.id)
        avatar_config = {}
    return {
        "id": profile.id,
        "name": profile.name,
        "avatar_type": profile.avatar_type,
        "avatar_config": avatar_config,
        "preferred_language": profile.preferred_language or "en",
        "theme": profile.theme or "system",
        "created_at": profile.created_at,
    }


def _load(db: Session, profile_id: int) -> models.Profile:
    profile = db.get(models.Profile, profile_id)
    if profile is None:
        raise NotFound(PROFILE_NOT_FOUND, "profile not found", profile_id=profile_id)
    return profile


@router.get("", response_model=list[schemas.ProfileOut])
def list_profiles(db: Session = Depends(get_db)):
    profiles = db.execute(select(models.Profile).order_by(models.Profile.id)).scalars().all()
    return [_to_out(profile) for profile in profiles]


@router.post("", response_model=schemas.ProfileOut, status_code=201)
def create_profile(body: schemas.ProfileCreate, db: Session = Depends(get_db)):
    profile = models.Profile(
        name=body.name.strip(),
        avatar_type=body.avatar_type,
        avatar_config_json=json.dumps(body.avatar_config, ensure_ascii=False),
        preferred_language=body.preferred_language,
        theme=body.theme,
    )
    db.add(profile)
    db.commit()
    db.refresh(profile)
    return _to_out(profile)


@router.get("/{profile_id}", response_model=schemas.ProfileOut)
def get_profile(profile_id: int, db: Session = Depends(get_db)):
    return _to_out(_load(db, profile_id))


@router.patch("/{profile_id}", response_model=schemas.ProfileOut)
@router.put("/{profile_id}", response_model=schemas.ProfileOut)
def update_profile(profile_id: int, body: schemas.ProfileUpdate, db: Session = Depends(get_db)):
    """PATCH is the honest verb for these all-optional fields; PUT stays as an
    alias so existing clients keep working."""
    profile = _load(db, profile_id)
    if body.name is not None:
        profile.name = body.name.strip()
    if body.avatar_type is not None:
        profile.avatar_type = body.avatar_type
    if body.avatar_config is not None:
        profile.avatar_config_json = json.dumps(body.avatar_config, ensure_ascii=False)
    if body.preferred_language is not None:
        profile.preferred_language = body.preferred_language
    if body.theme is not None:
        profile.theme = body.theme
    db.commit()
    db.refresh(profile)
    return _to_out(profile)


@router.delete("/{profile_id}", status_code=204, response_class=Response)
def delete_profile(profile_id: int, db: Session = Depends(get_db)):
    # Cascades now reach word_progress, events, and assignments as well as
    # games; those rows used to survive and be inherited by the next profile
    # that reused the autoincrement id.
    db.delete(_load(db, profile_id))
    db.commit()
    return Response(status_code=204)
