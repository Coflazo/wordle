"""Local A/B experiment harness.

Everything stays on this machine: assignment is a hash of (experiment, profile),
events land in the local SQLite file, and results are computed on read. No
network, no third party, consistent with the app's local-first promise.

Assignment is deterministic and sticky. Hashing rather than a coin flip means a
profile lands in the same arm on every request even before the assignment row is
written, so a page that reads flags twice cannot see two different UIs.

Results report a Wilson 95% interval rather than a bare percentage. With one
player the sample is small enough that a raw win rate is noise, and showing the
interval makes that visible instead of hiding it.
"""

from __future__ import annotations

import hashlib
import json
from typing import Dict, List, Optional

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app import models
from app.services.stats_service import _wilson_interval


class Experiment:
    def __init__(
        self,
        key: str,
        description: str,
        arms: Dict[str, object],
        metric: str = "win_rate",
        default: Optional[str] = None,
    ) -> None:
        self.key = key
        self.description = description
        self.arms = arms
        self.metric = metric
        self.default = default or next(iter(arms))

    def arm_names(self) -> List[str]:
        return list(self.arms)


# The registry. Adding an experiment here is the only step needed: flags, event
# annotation, and the results view all read from this list.
REGISTRY: Dict[str, Experiment] = {
    exp.key: exp
    for exp in [
        Experiment(
            "default_length",
            "Does defaulting to a fixed 5-letter game retain better than 'Mix'?",
            {"mix": None, "five": 5},
            metric="games_started_per_profile",
        ),
        Experiment(
            "customize_open",
            "Does opening the character editor by default increase customization?",
            {"closed": False, "open": True},
            metric="customization_rate",
        ),
        Experiment(
            "meaning_on_loss",
            "Does auto-opening the meaning panel after a loss improve mastery?",
            {"manual": False, "auto": True},
            metric="meaning_open_rate",
        ),
        Experiment(
            "hint_affordance",
            "Is a visible hint button used more than one hidden behind a long-press?",
            {"hidden": "hidden", "visible": "visible"},
            metric="hint_use_rate",
        ),
    ]
}


def assign(experiment: Experiment, profile_id: Optional[int]) -> str:
    """Stable arm for a profile. Unassigned visitors get the control arm."""
    if profile_id is None:
        return experiment.default
    seed = f"{experiment.key}:{profile_id}".encode("utf-8")
    digest = hashlib.sha256(seed).digest()
    index = int.from_bytes(digest[:8], "big") % len(experiment.arms)
    return experiment.arm_names()[index]


def flags_for(db: Session, profile_id: Optional[int]) -> Dict[str, str]:
    """Arm per experiment, persisting the assignment the first time it is read."""
    assignments: Dict[str, str] = {}
    if profile_id is None:
        return {key: exp.default for key, exp in REGISTRY.items()}

    existing = {
        row.experiment: row.arm
        for row in db.execute(
            select(models.ExperimentAssignment).where(
                models.ExperimentAssignment.profile_id == profile_id
            )
        ).scalars()
    }

    new_rows = []
    for key, experiment in REGISTRY.items():
        arm = existing.get(key)
        if arm is None or arm not in experiment.arms:
            arm = assign(experiment, profile_id)
            new_rows.append(
                models.ExperimentAssignment(profile_id=profile_id, experiment=key, arm=arm)
            )
        assignments[key] = arm

    if new_rows:
        db.add_all(new_rows)
        db.commit()
    return assignments


def arm_value(key: str, arm: str):
    """The behavioural value an arm stands for, for the server to act on."""
    experiment = REGISTRY.get(key)
    if experiment is None:
        return None
    return experiment.arms.get(arm)


def record_events(
    db: Session, profile_id: Optional[int], events: List[dict]
) -> int:
    rows = [
        models.Event(
            profile_id=profile_id,
            name=event["name"][:48],
            game_id=event.get("game_id"),
            props_json=json.dumps(event.get("props") or {}, ensure_ascii=False)[:4096],
        )
        for event in events
    ]
    db.add_all(rows)
    db.commit()
    return len(rows)


def results(db: Session) -> List[dict]:
    """Per-arm outcomes for every registered experiment."""
    assignment_rows = db.execute(select(models.ExperimentAssignment)).scalars().all()
    by_experiment: Dict[str, Dict[int, str]] = {}
    for row in assignment_rows:
        by_experiment.setdefault(row.experiment, {})[row.profile_id] = row.arm

    game_rows = db.execute(
        select(
            models.Game.profile_id,
            func.count(models.Game.id),
            func.sum(func.iif(models.Game.status == "won", 1, 0)),
            func.avg(func.iif(models.Game.status == "won", models.Game.attempts_used, None)),
        )
        .where(models.Game.status.in_(("won", "lost")))
        .group_by(models.Game.profile_id)
    ).all()
    per_profile = {
        profile_id: {"games": games, "wins": wins or 0, "avg_attempts": avg}
        for profile_id, games, wins, avg in game_rows
    }

    out: List[dict] = []
    for key, experiment in REGISTRY.items():
        membership = by_experiment.get(key, {})
        arms: List[dict] = []
        for arm in experiment.arm_names():
            profiles = [pid for pid, value in membership.items() if value == arm]
            games = sum(per_profile.get(pid, {}).get("games", 0) for pid in profiles)
            wins = sum(per_profile.get(pid, {}).get("wins", 0) for pid in profiles)
            attempts = [
                per_profile[pid]["avg_attempts"]
                for pid in profiles
                if per_profile.get(pid, {}).get("avg_attempts") is not None
            ]
            low, high = _wilson_interval(wins, games)
            arms.append(
                {
                    "arm": arm,
                    "profiles": len(profiles),
                    "games": games,
                    "wins": wins,
                    "win_rate": round(wins / games, 4) if games else 0.0,
                    "ci_low": low,
                    "ci_high": high,
                    "avg_attempts": round(sum(attempts) / len(attempts), 2) if attempts else None,
                }
            )
        out.append(
            {
                "experiment": key,
                "description": experiment.description,
                "metric": experiment.metric,
                "arms": arms,
            }
        )
    return out
