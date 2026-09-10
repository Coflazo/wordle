"""Pydantic schemas for request/response bodies."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field


Language = Literal["en", "tr", "de"]
Difficulty = Literal["chill", "classic", "scholar"]
LetterMask = Literal["green", "yellow", "gray"]


# ----- Profiles -----


class ProfileCreate(BaseModel):
    name: str = Field(min_length=1, max_length=64)
    avatar_type: str = Field(default="default")
    avatar_config: Dict[str, Any] = Field(default_factory=dict)
    preferred_language: Language = "en"


class ProfileUpdate(BaseModel):
    name: Optional[str] = None
    avatar_type: Optional[str] = None
    avatar_config: Optional[Dict[str, Any]] = None
    preferred_language: Optional[Language] = None


class ProfileOut(BaseModel):
    id: int
    name: str
    avatar_type: str
    avatar_config: Dict[str, Any]
    preferred_language: Language
    created_at: datetime


# ----- Games -----


class GameStart(BaseModel):
    profile_id: int
    language: Language
    difficulty: Difficulty = "classic"
    word_length: Optional[int] = Field(default=None, ge=5, le=10)


class GameOut(BaseModel):
    game_id: str
    profile_id: int
    language: Language
    difficulty: Difficulty
    word_length: int
    attempts_allowed: int
    attempts_used: int
    status: str
    guesses: List[Dict[str, Any]]
    answer: Optional[str] = None


class GuessIn(BaseModel):
    guess: str


class GuessOut(BaseModel):
    guess: Optional[str] = None
    result: List[LetterMask]
    attempts_used: int
    attempts_allowed: int
    status: str
    answer: Optional[str] = None


# ----- Meaning -----


class MeaningEntry(BaseModel):
    part_of_speech: Optional[str] = None
    definition: Optional[str] = None
    example: Optional[str] = None
    synonyms: List[str] = Field(default_factory=list)
    antonyms: List[str] = Field(default_factory=list)


class Meaning(BaseModel):
    word: str
    language: Language
    source: str
    source_label: str
    phonetic: Optional[str] = None
    audio_url: Optional[str] = None
    entries: List[MeaningEntry] = Field(default_factory=list)
    extras: Dict[str, Any] = Field(default_factory=dict)
    fetched_at: datetime
    from_cache: bool = False


# ----- Stats -----


class CoreMetrics(BaseModel):
    games_played: int
    wins: int
    losses: int
    win_rate: float
    current_streak: int
    best_streak: int
    avg_guesses_per_win: float
    avg_word_length_solved: float
    longest_word_solved: int
    fastest_solve_seconds: Optional[float]


class VocabMetrics(BaseModel):
    known_count: int
    mastered_count: int
    struggling_count: int
    solved_without_help_count: int
    meaning_opened_count: int
    repeated_failed_words: List[Dict[str, Any]]
    favorite_language: Optional[str]
    delta_last_7_games: float


class DashboardPayload(BaseModel):
    core: CoreMetrics
    vocab: VocabMetrics
    attempts_distribution: Dict[str, Dict[str, int]]
    language_split: Dict[str, int]
    timeline: List[Dict[str, Any]]
    mastered_words: List[Dict[str, Any]]
    known_words: List[Dict[str, Any]]
    struggling_words: List[Dict[str, Any]]
