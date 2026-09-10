"""Machine-readable API errors.

The frontend used to branch on the text of Python exceptions:

    if (e.status === 400 && /not in dictionary/i.test(e.message))

which meant rewording a message silently broke a UX path, and made translating
error text impossible — the string had to stay English for the regex to match.

Every error now carries a stable `code`. The client switches on the code and
renders its own localized text; `message` is a developer-facing fallback.
"""

from __future__ import annotations

from typing import Any

from fastapi import HTTPException


class ApiError(HTTPException):
    def __init__(
        self,
        status_code: int,
        code: str,
        message: str,
        **params: Any,
    ) -> None:
        super().__init__(
            status_code=status_code,
            detail={"code": code, "message": message, "params": params},
        )
        self.code = code


class NotFound(ApiError):
    def __init__(self, code: str, message: str, **params: Any) -> None:
        super().__init__(404, code, message, **params)


class Conflict(ApiError):
    """The request is well-formed but the resource is in the wrong state."""

    def __init__(self, code: str, message: str, **params: Any) -> None:
        super().__init__(409, code, message, **params)


class Unprocessable(ApiError):
    """Well-formed request, semantically rejected — a word not in the bank."""

    def __init__(self, code: str, message: str, **params: Any) -> None:
        super().__init__(422, code, message, **params)


class Unavailable(ApiError):
    def __init__(self, code: str, message: str, **params: Any) -> None:
        super().__init__(503, code, message, **params)


# Codes the frontend knows how to render. Keep in sync with
# frontend/js/i18n.js -> errors.*
PROFILE_NOT_FOUND = "profile_not_found"
GAME_NOT_FOUND = "game_not_found"
GAME_FINISHED = "game_finished"
WRONG_LENGTH = "wrong_length"
NOT_A_WORD = "not_a_word"
NO_WORDS = "no_words_for_length"
UNSUPPORTED_LANGUAGE = "unsupported_language"
BANK_UNAVAILABLE = "bank_unavailable"
SOLVER_UNAVAILABLE = "solver_unavailable"
RATE_LIMITED = "rate_limited"
PAYLOAD_TOO_LARGE = "payload_too_large"
