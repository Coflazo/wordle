#!/usr/bin/env python3
"""Start Oflaz Wordle.

    python run.py

One command on macOS, Windows and Linux. It checks what is missing, builds only
that, then starts the server and opens a browser. Safe to run repeatedly: a
second run skips straight to starting.

    python run.py --no-browser     don't open a browser
    python run.py --port 9000      use a different port
    python run.py --rebuild        force a rebuild of the native module and banks
    python run.py --setup-only     build everything, then stop
"""

from __future__ import annotations

import argparse
import os
import platform
import shutil
import signal
import subprocess
import sys
import threading
import time
import webbrowser
from pathlib import Path

ROOT = Path(__file__).resolve().parent
IS_WINDOWS = os.name == "nt"
VENV = ROOT / ".venv"
VENV_PY = VENV / ("Scripts/python.exe" if IS_WINDOWS else "bin/python")
BANKS = ROOT / "app" / "data" / "banks"
SOLVERD = ROOT / "solverd" / "build" / ("solverd.exe" if IS_WINDOWS else "solverd")
NATIVE_SRC = ROOT / "native"

MIN_PYTHON = (3, 11)


def say(message: str) -> None:
    print(f"  {message}", flush=True)


def step(message: str) -> None:
    print(f"\n\u2022 {message}", flush=True)


def die(message: str, hint: str = "") -> "NoReturn":  # type: ignore[valid-type]
    print(f"\nError: {message}", file=sys.stderr)
    if hint:
        print(hint, file=sys.stderr)
    sys.exit(1)


def run(cmd: list[str], **kwargs) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, cwd=kwargs.pop("cwd", ROOT), check=True, **kwargs)


def python_in_venv() -> Path:
    """Create the virtualenv if needed and return its interpreter."""
    if VENV_PY.exists():
        return VENV_PY
    step("Creating a virtual environment in .venv")
    run([sys.executable, "-m", "venv", str(VENV)])
    if not VENV_PY.exists():
        die(
            "the virtual environment was created but has no interpreter",
            "On Debian and Ubuntu you may need: sudo apt install python3-venv",
        )
    return VENV_PY


def pip_install(py: Path, args: list[str]) -> None:
    run([str(py), "-m", "pip", "install", "--quiet", "--disable-pip-version-check", *args])


def have_module(py: Path, name: str) -> bool:
    return subprocess.run(
        [str(py), "-c", f"import {name}"],
        cwd=ROOT,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    ).returncode == 0


def find_compiler() -> str | None:
    if IS_WINDOWS:
        # setuptools locates MSVC itself; just report whether it can.
        return "msvc" if shutil.which("cl") or Path(
            "C:/Program Files/Microsoft Visual Studio"
        ).exists() else None
    for name in ("c++", "clang++", "g++"):
        if shutil.which(name):
            return name
    return None


def native_is_stale(py: Path) -> bool:
    if not have_module(py, "wordle_core"):
        return True
    built = subprocess.run(
        [str(py), "-c", "import wordle_core, os; print(wordle_core.__file__)"],
        cwd=ROOT, capture_output=True, text=True,
    )
    if built.returncode != 0:
        return True
    so = Path(built.stdout.strip())
    if not so.exists():
        return True
    newest_source = max(
        (p.stat().st_mtime for p in NATIVE_SRC.rglob("*") if p.suffix in {".cpp", ".hpp"}),
        default=0,
    )
    return newest_source > so.stat().st_mtime


def ensure_python_deps(py: Path, rebuild: bool) -> None:
    needed = ["fastapi", "uvicorn", "sqlalchemy", "pydantic", "httpx"]
    missing = [name for name in needed if not have_module(py, name)]
    if missing or rebuild:
        step("Installing Python dependencies")
        pip_install(py, ["-r", str(ROOT / "requirements.txt")])
    else:
        say("Python dependencies are present")


def ensure_native(py: Path, rebuild: bool) -> None:
    if not rebuild and not native_is_stale(py):
        say("Native module wordle_core is up to date")
        return

    compiler = find_compiler()
    if compiler is None:
        die(
            "no C++ compiler found",
            _compiler_hint(),
        )
    step(f"Building the native module (compiler: {compiler})")
    if not have_module(py, "pybind11"):
        pip_install(py, ["pybind11", "setuptools", "wheel"])
    try:
        run([str(py), "setup.py", "build_ext", "--inplace"], stdout=subprocess.DEVNULL)
    except subprocess.CalledProcessError:
        die("the native build failed", "Re-run with the output visible:\n"
                                      f"    {py} setup.py build_ext --inplace")
    say("Built wordle_core")


def _compiler_hint() -> str:
    system = platform.system()
    if system == "Darwin":
        return "Install the Apple command line tools:\n    xcode-select --install"
    if system == "Windows":
        return (
            "Install the Microsoft C++ Build Tools:\n"
            "    winget install --id Microsoft.VisualStudio.2022.BuildTools\n"
            "then select 'Desktop development with C++' in the installer."
        )
    return (
        "Install a C++ toolchain, for example:\n"
        "    sudo apt install build-essential      # Debian, Ubuntu\n"
        "    sudo dnf install gcc-c++ make         # Fedora\n"
        "    sudo pacman -S base-devel             # Arch"
    )


def ensure_banks(py: Path, rebuild: bool) -> None:
    have = all((BANKS / f"{lang}.wbk").exists() for lang in ("en", "tr", "de"))
    if have and not rebuild:
        say("Word banks are present")
        return
    step("Building word banks (downloads a few word lists the first time)")
    try:
        run([str(py), "-m", "scripts.build_wordbanks"])
    except subprocess.CalledProcessError:
        die(
            "the word banks could not be built",
            "If you are offline, the raw sources cannot be downloaded. Re-run once "
            "you have a connection, or copy app/data/banks/*.wbk from another machine.",
        )


def ensure_solverd(rebuild: bool) -> bool:
    """Build the solver sidecar. Optional: hints work without it, just slower."""
    if SOLVERD.exists() and not rebuild:
        say("Solver sidecar is built")
        return True
    if IS_WINDOWS:
        # CPython does not expose AF_UNIX on Windows, so the daemon cannot be
        # reached from Python there. Hints run in-process instead.
        say("Skipping the solver sidecar on Windows; hints run in-process")
        return False
    if shutil.which("make") is None or find_compiler() is None:
        say("Skipping the solver sidecar (no make or compiler); hints run in-process")
        return False
    step("Building the solver sidecar")
    try:
        run(["make", "-s"], cwd=ROOT / "solverd", stdout=subprocess.DEVNULL)
        return True
    except subprocess.CalledProcessError:
        say("The sidecar failed to build; hints will run in-process")
        return False


def start_solverd() -> subprocess.Popen | None:
    if not SOLVERD.exists():
        return None
    run_dir = ROOT / "run"
    run_dir.mkdir(exist_ok=True)
    socket_path = run_dir / "solverd.sock"
    proc = subprocess.Popen(
        [str(SOLVERD), "--socket", str(socket_path), "--banks", str(BANKS)],
        cwd=ROOT,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.STDOUT,
    )
    # Give it a moment to bind before uvicorn probes it.
    for _ in range(20):
        if socket_path.exists():
            break
        if proc.poll() is not None:
            return None
        time.sleep(0.1)
    return proc


def open_browser_when_ready(url: str) -> None:
    def wait_and_open() -> None:
        import urllib.error
        import urllib.request

        for _ in range(100):
            try:
                with urllib.request.urlopen(f"{url}/api/ping", timeout=1):
                    webbrowser.open(url)
                    return
            except (urllib.error.URLError, OSError):
                time.sleep(0.2)

    threading.Thread(target=wait_and_open, daemon=True).start()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--no-browser", action="store_true")
    parser.add_argument("--rebuild", action="store_true")
    parser.add_argument("--setup-only", action="store_true")
    parser.add_argument("--reload", action="store_true", help="restart on file changes")
    args = parser.parse_args()

    if sys.version_info < MIN_PYTHON:
        die(
            f"Python {MIN_PYTHON[0]}.{MIN_PYTHON[1]} or newer is required, "
            f"this is {platform.python_version()}",
            "Install a newer Python from https://python.org and run this again.",
        )

    print("Oflaz Wordle")
    py = python_in_venv()
    ensure_python_deps(py, args.rebuild)
    ensure_native(py, args.rebuild)
    ensure_banks(py, args.rebuild)
    ensure_solverd(args.rebuild)

    if args.setup_only:
        print("\nSetup complete. Start it with:  python run.py")
        return 0

    solverd = start_solverd()
    if solverd is not None:
        say("Solver sidecar running")

    url = f"http://{'localhost' if args.host in ('127.0.0.1', '0.0.0.0') else args.host}:{args.port}"
    if not args.no_browser:
        open_browser_when_ready(url)

    print(f"\nPlaying at {url}   (Ctrl+C to stop)\n")
    cmd = [str(py), "-m", "uvicorn", "app.main:app",
           "--host", args.host, "--port", str(args.port)]
    if args.reload:
        cmd.append("--reload")

    server = subprocess.Popen(cmd, cwd=ROOT)
    try:
        server.wait()
    except KeyboardInterrupt:
        print("\nStopping…")
    finally:
        for proc in (server, solverd):
            if proc is None or proc.poll() is not None:
                continue
            proc.send_signal(signal.SIGTERM if not IS_WINDOWS else signal.SIGTERM)
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()
    return 0


if __name__ == "__main__":
    sys.exit(main())
