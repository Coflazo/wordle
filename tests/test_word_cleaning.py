"""Validator + processed-JSON sanity."""

import json
from pathlib import Path

from scripts._common import bucket_summary, is_valid, PROCESSED


def test_is_valid_english():
    assert is_valid("apple", "en") is True
    assert is_valid("stringy", "en") is True
    assert is_valid("a", "en") is False
    assert is_valid("apple pie", "en") is False
    assert is_valid("café", "en") is False


def test_is_valid_turkish():
    assert is_valid("kalem", "tr") is True
    assert is_valid("üniversite", "tr") is True  # 10 letters, in range
    assert is_valid("üniversiteler", "tr") is False  # 13 letters, too long
    assert is_valid("çiçek", "tr") is True
    # Turkish alphabet excludes q/w/x, so English-only strings using those fail.
    assert is_valid("query", "tr") is False
    # Letters h/e/l/o all live in the TR alphabet — this is intentional.
    assert is_valid("hello", "tr") is True


def test_is_valid_german():
    assert is_valid("apfel", "de") is True
    assert is_valid("straße", "de") is True
    assert is_valid("küche", "de") is True
    assert is_valid("a", "de") is False


def test_processed_banks_exist():
    for lang in ("en", "tr", "de"):
        targets_path = PROCESSED / f"{lang}_targets.json"
        allowed_path = PROCESSED / f"{lang}_allowed.json"
        assert targets_path.exists(), f"missing {targets_path}"
        assert allowed_path.exists(), f"missing {allowed_path}"

        targets = json.loads(targets_path.read_text(encoding="utf-8"))
        allowed = json.loads(allowed_path.read_text(encoding="utf-8"))
        assert len(targets) >= 200, f"{lang}: targets too small ({len(targets)})"
        assert set(targets).issubset(set(allowed))

        # Every length bucket should have at least a handful of words.
        dist = bucket_summary(targets)
        for length, count in dist.items():
            assert count >= 20, f"{lang}: length {length} has only {count} targets"


def test_turkish_targets_prefer_dictionary_spellings():
    targets = json.loads((PROCESSED / "tr_targets.json").read_text(encoding="utf-8"))
    allowed = json.loads((PROCESSED / "tr_allowed.json").read_text(encoding="utf-8"))

    assert "sebatlı" in targets
    assert "sebatli" not in targets
    assert "sebatli" in allowed
