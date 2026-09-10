"""Game routes."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app import schemas
from app.database import get_db
from app.services import game_service

router = APIRouter(prefix="/api/games", tags=["games"])


@router.post("/start", response_model=schemas.GameOut)
def start(body: schemas.GameStart, db: Session = Depends(get_db)):
    try:
        game = game_service.start_game(
            db,
            profile_id=body.profile_id,
            language=body.language,
            difficulty=body.difficulty,
            word_length=body.word_length,
        )
    except game_service.GameError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return game_service.game_to_dict(game, reveal_answer=False)


@router.get("/{game_id}", response_model=schemas.GameOut)
def get_game(game_id: str, db: Session = Depends(get_db)):
    from app import models

    game = db.get(models.Game, game_id)
    if game is None:
        raise HTTPException(status_code=404, detail="game not found")
    return game_service.game_to_dict(game, reveal_answer=False)


@router.post("/{game_id}/guess", response_model=schemas.GuessOut)
def guess(game_id: str, body: schemas.GuessIn, db: Session = Depends(get_db)):
    try:
        return game_service.submit_guess(db, game_id, body.guess)
    except game_service.GameError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/{game_id}/give-up", response_model=schemas.GuessOut)
def give_up(game_id: str, db: Session = Depends(get_db)):
    try:
        return game_service.give_up(db, game_id)
    except game_service.GameError as e:
        raise HTTPException(status_code=400, detail=str(e))
