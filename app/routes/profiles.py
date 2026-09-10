"""Profile CRUD."""

from __future__ import annotations

import json

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import models, schemas
from app.database import get_db

router = APIRouter(prefix="/api/profiles", tags=["profiles"])


def _to_out(p: models.Profile) -> dict:
    return {
        "id": p.id,
        "name": p.name,
        "avatar_type": p.avatar_type,
        "avatar_config": json.loads(p.avatar_config_json or "{}"),
        "preferred_language": p.preferred_language,
        "created_at": p.created_at,
    }


@router.get("", response_model=list[schemas.ProfileOut])
def list_profiles(db: Session = Depends(get_db)):
    rows = db.execute(select(models.Profile).order_by(models.Profile.id)).scalars().all()
    return [_to_out(p) for p in rows]


@router.post("", response_model=schemas.ProfileOut)
def create_profile(body: schemas.ProfileCreate, db: Session = Depends(get_db)):
    p = models.Profile(
        name=body.name,
        avatar_type=body.avatar_type,
        avatar_config_json=json.dumps(body.avatar_config),
        preferred_language=body.preferred_language,
    )
    db.add(p)
    db.commit()
    db.refresh(p)
    return _to_out(p)


@router.get("/{profile_id}", response_model=schemas.ProfileOut)
def get_profile(profile_id: int, db: Session = Depends(get_db)):
    p = db.get(models.Profile, profile_id)
    if p is None:
        raise HTTPException(status_code=404, detail="profile not found")
    return _to_out(p)


@router.put("/{profile_id}", response_model=schemas.ProfileOut)
def update_profile(
    profile_id: int, body: schemas.ProfileUpdate, db: Session = Depends(get_db)
):
    p = db.get(models.Profile, profile_id)
    if p is None:
        raise HTTPException(status_code=404, detail="profile not found")
    if body.name is not None:
        p.name = body.name
    if body.avatar_type is not None:
        p.avatar_type = body.avatar_type
    if body.avatar_config is not None:
        p.avatar_config_json = json.dumps(body.avatar_config)
    if body.preferred_language is not None:
        p.preferred_language = body.preferred_language
    db.commit()
    db.refresh(p)
    return _to_out(p)


@router.delete("/{profile_id}")
def delete_profile(profile_id: int, db: Session = Depends(get_db)):
    p = db.get(models.Profile, profile_id)
    if p is None:
        raise HTTPException(status_code=404, detail="profile not found")
    db.delete(p)
    db.commit()
    return {"deleted": profile_id}
