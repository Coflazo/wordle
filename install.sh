#!/usr/bin/env bash
# Oflaz Wordle installer for macOS and Linux.
#
#   curl -fsSL https://raw.githubusercontent.com/Coflazo/wordle/main/install.sh | bash
#
# Clones the repo, installs Python and a C++ compiler if they are missing, builds
# everything, and starts the game. Safe to re-run: it updates in place.

set -euo pipefail

REPO="https://github.com/Coflazo/wordle.git"
DIR="${WORDLE_DIR:-$HOME/oflaz-wordle}"

say()  { printf '\n\033[1m• %s\033[0m\n' "$*"; }
info() { printf '  %s\n' "$*"; }
die()  { printf '\n\033[31mError: %s\033[0m\n' "$*" >&2; exit 1; }

have() { command -v "$1" >/dev/null 2>&1; }

# --- package manager ---------------------------------------------------------

detect_installer() {
  if [[ "$(uname -s)" == "Darwin" ]]; then
    have brew && echo "brew" || echo "none"
  elif have apt-get; then echo "apt"
  elif have dnf;     then echo "dnf"
  elif have pacman;  then echo "pacman"
  elif have zypper;  then echo "zypper"
  elif have apk;     then echo "apk"
  else echo "none"
  fi
}

INSTALLER="$(detect_installer)"

install_pkgs() {
  case "$INSTALLER" in
    brew)   brew install "$@" ;;
    apt)    sudo apt-get update -qq && sudo apt-get install -y "$@" ;;
    dnf)    sudo dnf install -y "$@" ;;
    pacman) sudo pacman -Sy --noconfirm "$@" ;;
    zypper) sudo zypper install -y "$@" ;;
    apk)    sudo apk add "$@" ;;
    *)      return 1 ;;
  esac
}

# --- prerequisites -----------------------------------------------------------

say "Checking prerequisites"

if ! have git; then
  info "git is missing, installing"
  install_pkgs git || die "could not install git. Install it, then re-run this."
fi

PYTHON=""
for candidate in python3.13 python3.12 python3.11 python3; do
  if have "$candidate"; then
    version="$("$candidate" -c 'import sys; print("%d%02d" % sys.version_info[:2])' 2>/dev/null || echo 0)"
    if [[ "$version" -ge 311 ]]; then PYTHON="$candidate"; break; fi
  fi
done

if [[ -z "$PYTHON" ]]; then
  info "Python 3.11+ is missing, installing"
  case "$INSTALLER" in
    brew)   install_pkgs python@3.12 ;;
    apt)    install_pkgs python3 python3-venv python3-dev ;;
    dnf)    install_pkgs python3 python3-devel ;;
    pacman) install_pkgs python ;;
    zypper) install_pkgs python3 python3-devel ;;
    apk)    install_pkgs python3 python3-dev ;;
    *)      die "install Python 3.11 or newer from https://python.org, then re-run this." ;;
  esac
  PYTHON="python3"
fi
info "Python: $("$PYTHON" --version)"

if ! have c++ && ! have g++ && ! have clang++; then
  info "a C++ compiler is missing, installing"
  case "$INSTALLER" in
    brew)   xcode-select --install 2>/dev/null || true
            die "accept the Apple command line tools prompt, then re-run this." ;;
    apt)    install_pkgs build-essential ;;
    dnf)    install_pkgs gcc-c++ make ;;
    pacman) install_pkgs base-devel ;;
    zypper) install_pkgs gcc-c++ make ;;
    apk)    install_pkgs g++ make ;;
    *)      die "install a C++ compiler, then re-run this." ;;
  esac
fi
info "Compiler: $( (c++ --version || g++ --version) 2>/dev/null | head -1)"

# --- fetch -------------------------------------------------------------------

if [[ -d "$DIR/.git" ]]; then
  say "Updating $DIR"
  git -C "$DIR" pull --ff-only --quiet || info "could not fast-forward; keeping your local copy"
else
  say "Cloning into $DIR"
  git clone --depth 1 --quiet "$REPO" "$DIR"
fi

# --- build and run -----------------------------------------------------------

say "Building"
cd "$DIR"
"$PYTHON" run.py --setup-only

printf '\n\033[32mReady.\033[0m Starting the game.\n'
printf 'Next time, just run:  cd %s && python3 run.py\n\n' "$DIR"
exec "$PYTHON" run.py
