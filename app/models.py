"""SQLAlchemy models."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import (
    CheckConstraint,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    TypeDecorator,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship

from app.database import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class UtcDateTime(TypeDecorator):
    """Timezone-aware datetimes that survive SQLite.

    `DateTime(timezone=True)` is a no-op on SQLite: an aware datetime is written
    without its offset and read back naive. The API then serialized
    "2026-09-08T12:33:17" with no Z, and `new Date(...)` in the browser parsed it
    as local time — three hours off in Turkey. Normalize to UTC on the way in and
    re-attach UTC on the way out.
    """

    impl = DateTime
    cache_ok = True

    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        if value.tzinfo is None:
            return value
        return value.astimezone(timezone.utc).replace(tzinfo=None)

    def process_result_value(self, value, dialect):
        if value is None:
            return None
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)


class Profile(Base):
    __tablename__ = "profiles"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(64), nullable=False)
    avatar_type = Column(String(32), nullable=False, default="default")
    avatar_config_json = Column(Text, nullable=False, default="{}")
    preferred_language = Column(String(8), nullable=False, default="en")
    theme = Column(String(24), nullable=False, default="system")
    created_at = Column(UtcDateTime, default=utcnow, nullable=False)

    games = relationship(
        "Game", back_populates="profile", cascade="all, delete-orphan", passive_deletes=True
    )
    # Without this relationship, deleting a profile left its word_progress rows
    # behind forever, and the next profile to reuse the autoincrement id
    # inherited a stranger's vocabulary.
    progress = relationship(
        "WordProgress",
        back_populates="profile",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    events = relationship(
        "Event", back_populates="profile", cascade="all, delete-orphan", passive_deletes=True
    )
    assignments = relationship(
        "ExperimentAssignment",
        back_populates="profile",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )


class Game(Base):
    __tablename__ = "games"
    __table_args__ = (
        CheckConstraint("status in ('active','won','lost')", name="ck_games_status"),
        Index("ix_games_profile_status", "profile_id", "status"),
        UniqueConstraint("profile_id", "language", "daily_number", name="uq_daily_game"),
        Index("ix_games_profile_finished", "profile_id", "finished_at"),
    )

    id = Column(String(36), primary_key=True)
    profile_id = Column(
        Integer, ForeignKey("profiles.id", ondelete="CASCADE"), nullable=False, index=True
    )
    language = Column(String(8), nullable=False)
    word_length = Column(Integer, nullable=False)
    difficulty = Column(String(16), nullable=False, default="classic")
    answer = Column(String(32), nullable=False)
    attempts_allowed = Column(Integer, nullable=False)
    attempts_used = Column(Integer, nullable=False, default=0)
    status = Column(String(16), nullable=False, default="active")
    resigned = Column(Integer, nullable=False, default=0)
    hints_used = Column(Integer, nullable=False, default=0)
    # Set for the daily puzzle. Unique per profile and language, so a second
    # request the same day resumes rather than dealing a fresh board.
    daily_number = Column(Integer, nullable=True)
    started_at = Column(UtcDateTime, default=utcnow, nullable=False)
    finished_at = Column(UtcDateTime, nullable=True)

    profile = relationship("Profile", back_populates="games")
    guesses = relationship(
        "Guess", back_populates="game", cascade="all, delete-orphan", passive_deletes=True
    )


class Guess(Base):
    __tablename__ = "guesses"
    __table_args__ = (
        # One row per turn. This is the constraint that makes a duplicate
        # submission fail loudly instead of silently doubling a turn.
        UniqueConstraint("game_id", "turn", name="uq_guess_turn"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    game_id = Column(
        String(36), ForeignKey("games.id", ondelete="CASCADE"), nullable=False, index=True
    )
    turn = Column(Integer, nullable=False)
    guess = Column(String(32), nullable=False)
    # One digit per position: 0 gray, 1 yellow, 2 green. Queryable in SQL, and
    # the same encoding solverd speaks.
    result = Column(String(16), nullable=False)
    created_at = Column(UtcDateTime, default=utcnow, nullable=False)

    game = relationship("Game", back_populates="guesses")


class WordProgress(Base):
    __tablename__ = "word_progress"
    __table_args__ = (
        UniqueConstraint("profile_id", "word", "language", name="uq_word_progress"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    profile_id = Column(
        Integer, ForeignKey("profiles.id", ondelete="CASCADE"), nullable=False
    )
    word = Column(String(32), nullable=False)
    language = Column(String(8), nullable=False)
    seen_count = Column(Integer, nullable=False, default=0)
    solved_count = Column(Integer, nullable=False, default=0)
    failed_count = Column(Integer, nullable=False, default=0)
    meaning_opened_count = Column(Integer, nullable=False, default=0)
    mastery_score = Column(Float, nullable=False, default=0.0)
    last_seen_at = Column(UtcDateTime, default=utcnow, nullable=False)

    profile = relationship("Profile", back_populates="progress")


class DictionaryCache(Base):
    __tablename__ = "dictionary_cache"
    __table_args__ = (UniqueConstraint("language", "word", "source", name="uq_dict_cache"),)

    id = Column(Integer, primary_key=True, autoincrement=True)
    language = Column(String(8), nullable=False)
    word = Column(String(64), nullable=False)
    source = Column(String(32), nullable=False)
    response_json = Column(Text, nullable=False)
    simplified_definition = Column(Text, nullable=True)
    # A lookup that found nothing expires quickly, so one upstream outage does
    # not poison a word permanently. Hits are kept for a year.
    found = Column(Integer, nullable=False, default=1)
    created_at = Column(UtcDateTime, default=utcnow, nullable=False)


class Event(Base):
    """Client and server telemetry, local to this machine."""

    __tablename__ = "events"
    __table_args__ = (Index("ix_events_name_created", "name", "created_at"),)

    id = Column(Integer, primary_key=True, autoincrement=True)
    profile_id = Column(
        Integer, ForeignKey("profiles.id", ondelete="CASCADE"), nullable=True, index=True
    )
    name = Column(String(48), nullable=False)
    game_id = Column(String(36), nullable=True)
    props_json = Column(Text, nullable=False, default="{}")
    created_at = Column(UtcDateTime, default=utcnow, nullable=False, index=True)

    profile = relationship("Profile", back_populates="events")


class ExperimentAssignment(Base):
    """Which arm of which experiment a profile is in. Sticky once written."""

    __tablename__ = "experiment_assignments"
    __table_args__ = (
        UniqueConstraint("profile_id", "experiment", name="uq_experiment_assignment"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    profile_id = Column(
        Integer, ForeignKey("profiles.id", ondelete="CASCADE"), nullable=False, index=True
    )
    experiment = Column(String(48), nullable=False)
    arm = Column(String(32), nullable=False)
    assigned_at = Column(UtcDateTime, default=utcnow, nullable=False)

    profile = relationship("Profile", back_populates="assignments")
