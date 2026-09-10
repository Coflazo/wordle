"""Wordle scoring — duplicate-letter edge cases."""

from app.services.game_service import score_guess


def test_all_correct():
    assert score_guess("apple", "apple") == ["green"] * 5


def test_all_wrong():
    assert score_guess("apple", "zzzzz") == ["gray"] * 5


def test_speed_erase():
    # SPEED / ERASE:
    # positions 0..4 answer=S P E E D, guess=E R A S E
    # Pass 1: index 3 (S vs E) no; index 3 answer=E vs guess=S no; recompute:
    # Position by position:
    #   0: S vs E -> not green, remaining[S]=1
    #   1: P vs R -> not green, remaining[P]=1
    #   2: E vs A -> not green, remaining[E]=1
    #   3: E vs S -> not green, remaining[E]=2
    #   4: D vs E -> not green, remaining[D]=1
    # Pass 2:
    #   0 E: remaining[E]=2 -> yellow, remaining[E]=1
    #   1 R: not in remaining -> gray
    #   2 A: not in remaining -> gray
    #   3 S: remaining[S]=1 -> yellow, remaining[S]=0
    #   4 E: remaining[E]=1 -> yellow, remaining[E]=0
    assert score_guess("speed", "erase") == [
        "yellow",
        "gray",
        "gray",
        "yellow",
        "yellow",
    ]


def test_kayak_aaaaa():
    # KAYAK / AAAAA
    # Pass 1: greens where guess=A and answer=A → positions 1 and 3.
    # After greens, remaining letters in answer for gray/yellow eval: K, Y, K (positions 0, 2, 4).
    # Pass 2 for non-green positions:
    #   0 A: not in remaining -> gray
    #   2 A: not in remaining -> gray
    #   4 A: not in remaining -> gray
    assert score_guess("kayak", "aaaaa") == [
        "gray",
        "green",
        "gray",
        "green",
        "gray",
    ]


def test_level_hello():
    # LEVEL / HELLO
    # Pass 1: L E V E L vs H E L L O
    #   0: L vs H -> not green
    #   1: E vs E -> GREEN
    #   2: V vs L -> not green
    #   3: E vs L -> not green
    #   4: L vs O -> not green
    # remaining (excluding greens): L(x2 at pos 0,4), V, E
    # Pass 2:
    #   0 H: not in remaining -> gray
    #   2 L: remaining[L]=2 -> yellow, remaining[L]=1
    #   3 L: remaining[L]=1 -> yellow, remaining[L]=0
    #   4 O: not in remaining -> gray
    assert score_guess("level", "hello") == [
        "gray",
        "green",
        "yellow",
        "yellow",
        "gray",
    ]


def test_case_insensitive():
    assert score_guess("Apple", "APPLE") == ["green"] * 5
