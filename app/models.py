"""SQLAlchemy models for profiles, games, guesses, word progress, and dictionary cache."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import (
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship

from app.database import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Profile(Base):
    __tablename__ = "profiles"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(64), nullable=False)
    avatar_type = Column(String(32), nullable=False, default="default")
    avatar_config_json = Column(Text, nullable=False, default="{}")
    preferred_language = Column(String(8), default="en")
    created_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)

    games = relationship("Game", back_populates="profile", cascade="all, delete-orphan")


class Game(Base):
    __tablename__ = "games"

    id = Column(String(36), primary_key=True)
    profile_id = Column(Integer, ForeignKey("profiles.id"), nullable=False, index=True)
    language = Column(String(8), nullable=False)
    word_length = Column(Integer, nullable=False)
    difficulty = Column(String(16), nullable=False, default="classic")
    answer = Column(String(32), nullable=False)
    attempts_allowed = Column(Integer, nullable=False)
    attempts_used = Column(Integer, default=0, nullable=False)
    status = Column(String(16), default="active", nullable=False)  # active|won|lost
    meaning_opened = Column(Integer, default=0, nullable=False)
    started_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)
    finished_at = Column(DateTime(timezone=True), nullable=True)

    profile = relationship("Profile", back_populates="games")
    guesses = relationship("Guess", back_populates="game", cascade="all, delete-orphan")


class Guess(Base):
    __tablename__ = "guesses"

    id = Column(Integer, primary_key=True, autoincrement=True)
    game_id = Column(String(36), ForeignKey("games.id"), nullable=False, index=True)
    guess = Column(String(32), nullable=False)
    result_json = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)

    game = relationship("Game", back_populates="guesses")


class WordProgress(Base):
    __tablename__ = "word_progress"
    __table_args__ = (
        UniqueConstraint("profile_id", "word", "language", name="uq_word_progress"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    profile_id = Column(Integer, ForeignKey("profiles.id"), nullable=False, index=True)
    word = Column(String(32), nullable=False)
    language = Column(String(8), nullable=False)
    seen_count = Column(Integer, default=0, nullable=False)
    solved_count = Column(Integer, default=0, nullable=False)
    failed_count = Column(Integer, default=0, nullable=False)
    meaning_opened_count = Column(Integer, default=0, nullable=False)
    mastery_score = Column(Float, default=0.0, nullable=False)
    last_seen_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)


class DictionaryCache(Base):
    __tablename__ = "dictionary_cache"
    __table_args__ = (
        UniqueConstraint("language", "word", "source", name="uq_dict_cache"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    language = Column(String(8), nullable=False)
    word = Column(String(32), nullable=False)
    source = Column(String(32), nullable=False)
    response_json = Column(Text, nullable=False)
    simplified_definition = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)
