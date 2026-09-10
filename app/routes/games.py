"""Game lifecycle: start, read, guess, resign, hint."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app import config, models, schemas
from app.database import get_db
from app.errors import GAME_NOT_FOUND, SOLVER_UNAVAILABLE, NotFound, Unavailable
from app.services import experiment_service, game_service, solverd_client, word_service

router = APIRouter(prefix="/api/games", tags=["games"])


def _load(db: Session, game_id: str) -> models.Game:
    game = db.get(models.Game, game_id)
    if game is None:
        raise NotFound(GAME_NOT_FOUND, "game not found", game_id=game_id)
    return game


@router.post("/start", response_model=schemas.GameOut, status_code=201)
def start(body: schemas.GameStart, db: Session = Depends(get_db)):
    word_length = body.word_length
    if word_length is None:
        # The "Mix" default is one arm of a live experiment; the other pins 5.
        arms = experiment_service.flags_for(db, body.profile_id)
        forced = experiment_service.arm_value("default_length", arms.get("default_length", ""))
        if isinstance(forced, int):
            word_length = forced

    game = game_service.start_game(
        db,
        profile_id=body.profile_id,
        language=body.language,
        difficulty=body.difficulty,
        word_length=word_length,
    )
    return game_service.game_to_dict(game)


@router.get("/{game_id}", response_model=schemas.GameOut)
def get_game(game_id: str, db: Session = Depends(get_db)):
    return game_service.game_to_dict(_load(db, game_id))


@router.post("/{game_id}/guess", response_model=schemas.GuessOut)
def guess(game_id: str, body: schemas.GuessIn, db: Session = Depends(get_db)):
    # Service-level errors are already ApiError subclasses carrying a code, so
    # there is nothing to translate here. The previous version funnelled every
    # failure into a 400 with a prose message the frontend matched by regex.
    return game_service.submit_guess(db, game_id, body.guess)


@router.post("/{game_id}/give-up", response_model=schemas.GuessOut)
def give_up(game_id: str, db: Session = Depends(get_db)):
    return game_service.give_up(db, game_id)


@router.get("/{game_id}/hint", response_model=schemas.HintOut)
def hint(
    game_id: str,
    top_k: int = Query(default=3, ge=1, le=10),
    db: Session = Depends(get_db),
):
    """Best next guesses by expected information gain.

    Counted on the game so the profile dashboard can separate assisted wins from
    unassisted ones — a hint feature that silently inflates the win rate would
    make every other statistic on that page a lie.
    """
    game = _load(db, game_id)
    if game.status != "active":
        return schemas.HintOut(
            candidates_remaining=0,
            candidates=[],
            suggestions=[],
            source="in-process",
            hints_used=game.hints_used,
        )

    try:
        payload = solverd_client.hint(
            language=game.language,
            word_length=game.word_length,
            history=game_service.history_for_solver(game),
            top_k=top_k,
            tiers=word_service.tiers_for(game.difficulty),
        )
    except solverd_client.SolverUnavailable as exc:
        raise Unavailable(SOLVER_UNAVAILABLE, f"hints are unavailable: {exc}") from exc

    game.hints_used += 1
    db.commit()

    return schemas.HintOut(
        candidates_remaining=payload.get("candidates_remaining", 0),
        candidates=payload.get("candidates", []),
        suggestions=payload.get("suggestions", []),
        source=payload.get("source", "in-process"),
        hints_used=game.hints_used,
    )
