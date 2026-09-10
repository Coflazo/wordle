"""Client for the solverd sidecar, with an in-process fallback.

solverd holds every bank mapped and caches narrowed candidate sets, so repeated
hints during one game are answered from RAM. When it is not running the same
work is done in-process through wordle_core: slower on the opening turn and
without the cache, but a hint never fails just because a daemon is down.

Two transports. A Unix domain socket by default, so file permissions decide who
can ask. On Windows CPython does not expose `socket.AF_UNIX`, so the daemon is
started on loopback TCP instead and both ends share a token — a loopback port is
reachable by every account on the machine, a mode-0600 socket file is not.
"""

from __future__ import annotations

import json
import logging
import socket
import threading
from typing import Dict, List, Optional, Sequence, Tuple

from app import config
from app.services import word_service

log = logging.getLogger("wordle.solverd")

_lock = threading.Lock()
_last_failure_logged = False


class SolverUnavailable(RuntimeError):
    pass


def _tcp_endpoint():
    if not config.SOLVERD_TCP:
        return None
    host, _, port = config.SOLVERD_TCP.rpartition(":")
    try:
        return (host or "127.0.0.1", int(port))
    except ValueError:
        return None


def available() -> bool:
    """Is there any transport that could reach the daemon?"""
    return _tcp_endpoint() is not None or hasattr(socket, "AF_UNIX")


def _connect(timeout: float) -> socket.socket:
    endpoint = _tcp_endpoint()
    if endpoint is not None:
        sock = socket.create_connection(endpoint, timeout=timeout)
        sock.settimeout(timeout)
        return sock
    sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    sock.settimeout(timeout)
    sock.connect(str(config.SOLVERD_SOCKET))
    return sock


def _request(line: str, timeout: float) -> dict:
    if config.SOLVERD_TOKEN:
        line = f"{line} token={config.SOLVERD_TOKEN}"
    try:
        sock = _connect(timeout)
    except (OSError, socket.timeout) as exc:
        raise SolverUnavailable(str(exc)) from exc
    try:
        sock.sendall((line + "\n").encode("utf-8"))
        buffer = bytearray()
        while not buffer.endswith(b"\n"):
            chunk = sock.recv(65536)
            if not chunk:
                break
            buffer.extend(chunk)
    except (OSError, socket.timeout) as exc:
        raise SolverUnavailable(str(exc)) from exc
    finally:
        sock.close()

    if not buffer:
        raise SolverUnavailable("solverd closed the connection without replying")
    try:
        payload = json.loads(buffer.decode("utf-8"))
    except ValueError as exc:
        raise SolverUnavailable(f"malformed reply: {exc}") from exc
    if not payload.get("ok"):
        raise SolverUnavailable(payload.get("error", "unknown solverd error"))
    return payload


def ping(timeout: float = 0.5) -> bool:
    if not available():
        return False
    try:
        _request("ping", timeout)
        return True
    except SolverUnavailable:
        return False


def stats() -> Optional[dict]:
    try:
        return _request("stats", config.SOLVERD_TIMEOUT)
    except SolverUnavailable:
        return None


def _encode_history(history: Sequence[Tuple[str, str]]) -> str:
    return "|".join(f"{guess}:{mask}" for guess, mask in history)


def hint(
    language: str,
    word_length: int,
    history: Sequence[Tuple[str, str]],
    top_k: int = 5,
    tiers: Sequence[str] = (),
    guess_pool: str = "targets",
    candidate_sample: int = 12,
) -> Dict:
    """Ask for the best next guesses. Returns the payload plus its source."""
    parts = [
        "hint",
        f"lang={language}",
        f"len={word_length}",
        f"top_k={top_k}",
        f"pool={guess_pool}",
        f"sample={candidate_sample}",
    ]
    if tiers:
        parts.append("tiers=" + ",".join(tiers))
    if history:
        parts.append("history=" + _encode_history(history))

    global _last_failure_logged
    if available():
        try:
            payload = _request(" ".join(parts), config.SOLVERD_TIMEOUT)
            _last_failure_logged = False
            payload["source"] = "solverd"
            return payload
        except SolverUnavailable as exc:
            if not config.SOLVERD_FALLBACK:
                raise
            # Log the first failure of a run, not every request: a stopped
            # daemon would otherwise write a line per hint.
            with _lock:
                if not _last_failure_logged:
                    log.warning("solverd unavailable (%s); answering hints in-process", exc)
                    _last_failure_logged = True

    return _in_process(language, word_length, history, top_k, tiers, guess_pool, candidate_sample)


def _in_process(
    language: str,
    word_length: int,
    history: Sequence[Tuple[str, str]],
    top_k: int,
    tiers: Sequence[str],
    guess_pool: str,
    candidate_sample: int,
) -> Dict:
    digits = {"0": "gray", "1": "yellow", "2": "green"}
    decoded: List[Tuple[str, List[str]]] = [
        (guess, [digits[ch] for ch in mask]) for guess, mask in history
    ]
    payload = word_service.bank(language).hint(
        word_length,
        decoded,
        top_k=top_k,
        guess_pool=guess_pool,
        tiers=tuple(tiers) or None,
        candidate_sample=candidate_sample,
    )
    payload["source"] = "in-process"
    return payload
