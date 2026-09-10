"""Build the wordle_core native extension.

setuptools rather than CMake on purpose: cmake is not on PATH on the reference
machine, and a plain Extension needs nothing but a C++20 compiler.

    pip install -e .          # editable install, puts wordle_core on sys.path
    python setup.py build_ext --inplace   # or just drop the .so next to the sources
"""

from __future__ import annotations

import platform
import sys
from pathlib import Path

from setuptools import Extension, setup

try:
    import pybind11
except ImportError:  # pragma: no cover - a build-time guard, not runtime code
    sys.exit(
        "pybind11 is required to build wordle_core.\n"
        "    pip install pybind11\n"
        "or install this package with its build requirements:\n"
        "    pip install -e ."
    )

ROOT = Path(__file__).resolve().parent
NATIVE = ROOT / "native"

SOURCES = [str(NATIVE / "bindings" / "module.cpp")] + sorted(
    str(p) for p in (NATIVE / "src").glob("*.cpp")
)

if sys.platform == "win32":
    # MSVC. /EHsc because pybind11 translates C++ exceptions at the boundary,
    # /bigobj because the binding translation unit exceeds the default section
    # limit once pybind11's templates are instantiated.
    compile_args = ["/std:c++20", "/O2", "/EHsc", "/bigobj", "/W3"]
    link_args: list[str] = []
else:
    compile_args = ["-std=c++20", "-O3", "-fvisibility=hidden", "-Wall", "-Wextra"]
    link_args = []

    if sys.platform == "darwin":
        # 10.15 is the first macOS with a complete libc++ <filesystem>.
        compile_args.append("-mmacosx-version-min=10.15")
        link_args.append("-mmacosx-version-min=10.15")

    # Deliberately no -march=native: a binary built on one machine and copied to
    # another would SIGILL rather than just run a little slower.
    if platform.machine() in {"x86_64", "AMD64", "i686"}:
        compile_args.append("-mpopcnt")  # std::popcount in the suggest prefilter

ext = Extension(
    "wordle_core",
    sources=SOURCES,
    include_dirs=[str(NATIVE / "include"), pybind11.get_include()],
    language="c++",
    extra_compile_args=compile_args,
    extra_link_args=link_args,
)

setup(
    name="oflaz-wordle-core",
    version="1.0.0",
    description="Native core for Oflaz Wordle: normalization, word banks, scoring, solver",
    ext_modules=[ext],
    zip_safe=False,
    python_requires=">=3.11",
)
