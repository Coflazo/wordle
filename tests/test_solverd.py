"""The solver sidecar: both transports, the token guard, and the wire protocol.

Skipped when the daemon has not been built, so a clone that only ran the Python
setup still gets a green suite.
"""

from __future__ import annotations

import json
import secrets
import socket
import subprocess
import time
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
BINARY = ROOT / "solverd" / "build" / "solverd"
BANKS = ROOT / "app" / "data" / "banks"

pytestmark = pytest.mark.skipif(
    not BINARY.exists(), reason="solverd is not built (cd solverd && make)"
)


def free_port() -> int:
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        return probe.getsockname()[1]


@pytest.fixture(scope="module")
def daemon():
    port = free_port()
    token = secrets.token_urlsafe(16)
    proc = subprocess.Popen(
        [str(BINARY), "--tcp", str(port), "--token", token, "--banks", str(BANKS)],
        cwd=ROOT, stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT,
    )
    for _ in range(50):
        with socket.socket() as probe:
            probe.settimeout(0.2)
            if probe.connect_ex(("127.0.0.1", port)) == 0:
                break
        if proc.poll() is not None:
            pytest.fail("solverd exited during startup")
        time.sleep(0.1)
    else:
        proc.kill()
        pytest.fail("solverd did not start")

    yield port, token
    proc.terminate()
    proc.wait(timeout=5)


def call(port: int, line: str) -> dict:
    with socket.create_connection(("127.0.0.1", port), timeout=20) as sock:
        sock.sendall((line + "\n").encode("utf-8"))
        buffer = bytearray()
        while not buffer.endswith(b"\n"):
            chunk = sock.recv(65536)
            if not chunk:
                break
            buffer.extend(chunk)
    return json.loads(buffer.decode("utf-8"))


def test_ping(daemon):
    port, token = daemon
    assert call(port, f"ping token={token}")["ok"] is True


def test_tcp_requires_the_token(daemon):
    """A loopback port is reachable by every account on the machine."""
    port, token = daemon
    assert call(port, "ping")["error"] == "unauthorized"
    assert call(port, "ping token=wrong")["error"] == "unauthorized"


def test_refuses_tcp_without_a_token():
    result = subprocess.run(
        [str(BINARY), "--tcp", str(free_port()), "--banks", str(BANKS)],
        cwd=ROOT, capture_output=True, text=True, timeout=20,
    )
    assert result.returncode != 0
    assert "without --token" in result.stderr


def test_hint_narrows_with_history(daemon):
    port, token = daemon
    opening = call(port, f"hint lang=en len=5 top_k=3 token={token}")
    assert opening["ok"]
    assert opening["candidates_remaining"] > 100
    assert len(opening["suggestions"]) == 3
    # Information gain must be positive while the answer is still open.
    assert opening["suggestions"][0]["bits"] > 0
    # And sorted best-first.
    bits = [s["bits"] for s in opening["suggestions"]]
    assert bits == sorted(bits, reverse=True)

    narrowed = call(port, f"hint lang=en len=5 history=crane:00000 top_k=2 token={token}")
    assert narrowed["candidates_remaining"] < opening["candidates_remaining"]


def test_hint_rejects_a_malformed_mask(daemon):
    port, token = daemon
    assert "mask digits" in call(port, f"hint lang=en len=5 history=crane:00009 token={token}")["error"]
    assert "does not match len" in call(
        port, f"hint lang=en len=5 history=craned:000000 token={token}"
    )["error"]


def test_hint_validates_language_and_length(daemon):
    port, token = daemon
    assert "lang" in call(port, f"hint lang=zz len=5 token={token}")["error"]
    assert "5..10" in call(port, f"hint lang=en len=99 token={token}")["error"]


def test_suggest_finds_the_diacritic_spelling(daemon):
    port, token = daemon
    result = call(port, f"suggest lang=tr word=sebatli limit=5 token={token}")
    assert result["ok"]
    assert any(s["word"] == "sebatlı" for s in result["suggestions"])


def test_unknown_op(daemon):
    port, token = daemon
    assert "unknown op" in call(port, f"frobnicate token={token}")["error"]


def test_cache_is_used_for_a_repeated_query(daemon):
    port, token = daemon
    query = f"hint lang=tr len=5 history=kalem:00201 top_k=1 token={token}"
    before = call(port, f"stats token={token}")["cache_hits"]
    call(port, query)
    call(port, query)
    after = call(port, f"stats token={token}")["cache_hits"]
    assert after > before


def test_client_falls_back_when_the_daemon_is_absent(monkeypatch):
    """A stopped sidecar must degrade to in-process, never fail the request."""
    from app import config
    from app.services import solverd_client

    monkeypatch.setattr(config, "SOLVERD_TCP", "127.0.0.1:1")  # nothing listens here
    monkeypatch.setattr(config, "SOLVERD_TOKEN", "")
    payload = solverd_client.hint("en", 5, [], top_k=2)
    assert payload["source"] == "in-process"
    assert payload["suggestions"]
