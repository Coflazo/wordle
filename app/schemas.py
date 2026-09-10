"""Pydantic request and response models.

Every route declares a response_model. The dashboard and meaning endpoints used
to declare none, so the schemas describing them were dead code and the contract
was whatever the handler happened to return that day.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field, field_validator

from app import config

Language = Literal["en", "tr", "de"]
Difficulty = Literal["chill", "classic", "scholar"]
LetterMask = Literal["green", "yellow", "gray"]
Tier = Literal["common", "standard", "rare"]
Theme = Literal["system", "dark", "light", "contrast", "colorblind"]


# ------------------------------------------------------------------- profiles

def _bounded_avatar(value: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """The column is untyped JSON and SQLite does not enforce VARCHAR length, so
    without this an unbounded blob goes straight to disk."""
    if value is None:
        return None
    import json

    if len(json.dumps(value)) > config.MAX_AVATAR_CONFIG_BYTES:
        raise ValueError(
            f"avatar_config must serialize to under {config.MAX_AVATAR_CONFIG_BYTES} bytes"
        )
    return value


class ProfileCreate(BaseModel):
    name: str = Field(min_length=1, max_length=config.MAX_PROFILE_NAME)
    avatar_type: str = Field(default="default", max_length=32)
    avatar_config: Dict[str, Any] = Field(default_factory=dict)
    preferred_language: Language = "en"
    theme: Theme = "system"

    _check_avatar = field_validator("avatar_config")(_bounded_avatar)


class ProfileUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=config.MAX_PROFILE_NAME)
    avatar_type: Optional[str] = Field(default=None, max_length=32)
    avatar_config: Optional[Dict[str, Any]] = None
    preferred_language: Optional[Language] = None
    theme: Optional[Theme] = None

    _check_avatar = field_validator("avatar_config")(_bounded_avatar)


class ProfileOut(BaseModel):
    id: int
    name: str
    avatar_type: str
    avatar_config: Dict[str, Any]
    preferred_language: Language
    theme: Theme
    created_at: datetime


# ---------------------------------------------------------------------- games

class GameStart(BaseModel):
    profile_id: int
    language: Language
    difficulty: Difficulty = "classic"
    word_length: Optional[int] = Field(
        default=None,
        ge=min(config.ATTEMPTS_BY_LENGTH),
        le=max(config.ATTEMPTS_BY_LENGTH),
        description="Omit for a weighted random length ('Mix' in the UI).",
    )


class GuessEntry(BaseModel):
    guess: str
    turn: int
    result: List[LetterMask]


class GameOut(BaseModel):
    game_id: str
    profile_id: int
    language: Language
    difficulty: Difficulty
    word_length: int
    attempts_allowed: int
    attempts_used: int
    status: Literal["active", "won", "lost"]
    resigned: bool = False
    guesses: List[GuessEntry] = Field(default_factory=list)
    answer: Optional[str] = None
    answer_display: Optional[str] = None
    tiers: List[Tier] = Field(default_factory=list)


class GuessIn(BaseModel):
    # Bounded at the schema layer so an oversized body is rejected before it
    # reaches the normalizer. Ten letters is the longest word; a decomposed
    # umlaut costs two codepoints, hence the headroom.
    guess: str = Field(min_length=1, max_length=64)


class GuessOut(BaseModel):
    guess: Optional[str]
    result: List[LetterMask]
    turn: int
    attempts_used: int
    attempts_allowed: int
    status: Literal["active", "won", "lost"]
    answer: Optional[str] = None
    answer_display: Optional[str] = None


# ---------------------------------------------------------------------- hints

class HintSuggestion(BaseModel):
    word: str
    bits: float
    expected_remaining: float
    is_candidate: bool


class HintOut(BaseModel):
    candidates_remaining: int
    candidates: List[str]
    suggestions: List[HintSuggestion]
    source: Literal["solverd", "in-process"]
    hints_used: int


# -------------------------------------------------------------------- meaning

class MeaningEntry(BaseModel):
    part_of_speech: Optional[str] = None
    definition: str
    example: Optional[str] = None
    synonyms: List[str] = Field(default_factory=list)
    antonyms: List[str] = Field(default_factory=list)


class MeaningOut(BaseModel):
    word: str
    display: str
    language: Language
    source: str
    source_label: str
    entries: List[MeaningEntry] = Field(default_factory=list)
    extras: Dict[str, Any] = Field(default_factory=dict)
    from_cache: bool = False


# ----------------------------------------------------------------- dashboard

class CoreMetrics(BaseModel):
    games_played: int
    wins: int
    win_rate: float
    avg_attempts: float
    avg_word_length: float
    longest_word_solved: int
    fastest_solve_seconds: Optional[float] = None
    best_streak: int
    current_streak: int
    delta_last_7_games: float
    delta_is_meaningful: bool
    favorite_language: Optional[Language] = None


class WordStat(BaseModel):
    word: str
    display: str
    language: Language
    mastery: float
    seen: int
    solved: int
    failed: int
    meaning_opened: int
    last_seen_at: Optional[datetime] = None


class VocabMetrics(BaseModel):
    total_words_seen: int
    mastered_count: int
    known_count: int
    struggling_count: int
    mastered: List[WordStat]
    known: List[WordStat]
    struggling: List[WordStat]


class LanguageSplit(BaseModel):
    language: Language
    games: int
    wins: int
    win_rate: float


class TimelineEntry(BaseModel):
    game_id: str
    language: Language
    answer: str
    answer_display: str
    word_length: int
    difficulty: Difficulty
    attempts_used: int
    attempts_allowed: int
    status: Literal["won", "lost"]
    resigned: bool
    hints_used: int
    finished_at: Optional[datetime] = None


class ProfileSummary(BaseModel):
    id: int
    name: str
    preferred_language: Language
    created_at: Optional[datetime] = None


class DashboardOut(BaseModel):
    profile: ProfileSummary
    language: Optional[Language] = None
    core: CoreMetrics
    attempts_distribution: Dict[str, Dict[str, int]]
    language_split: List[LanguageSplit]
    vocabulary: VocabMetrics
    timeline: List[TimelineEntry]


# ------------------------------------------------------- flags & experiments

class FlagsOut(BaseModel):
    profile_id: Optional[int] = None
    assignments: Dict[str, str]


class EventIn(BaseModel):
    name: str = Field(min_length=1, max_length=48)
    game_id: Optional[str] = Field(default=None, max_length=36)
    props: Dict[str, Any] = Field(default_factory=dict)


class EventBatch(BaseModel):
    profile_id: Optional[int] = None
    events: List[EventIn] = Field(min_length=1, max_length=config.MAX_EVENTS_PER_BATCH)


class ArmResult(BaseModel):
    arm: str
    profiles: int
    games: int
    wins: int
    win_rate: float
    ci_low: float
    ci_high: float
    avg_attempts: Optional[float] = None


class ExperimentResult(BaseModel):
    experiment: str
    description: str
    metric: str
    arms: List[ArmResult]


class ExperimentsOut(BaseModel):
    experiments: List[ExperimentResult]
