#!/usr/bin/env python
"""
LicenseIQ automated test runner.

Usage:
    python tests/run_tests.py              # run core pytest suites
    python tests/run_tests.py -v           # verbose
    python tests/run_tests.py -k scoping   # filter by name
    python tests/run_tests.py --all        # entire tests/ tree (except manual, scripts)
    python tests/run_tests.py --no-header  # skip ASCII header

Requires: pip install pytest
"""
import os
import subprocess
import sys

_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

HEADER = """
╔══════════════════════════════════════════════════════════════════╗
║              LicenseIQ  –  Automated Test Suite                  ║
║  unit · auth · dashboard · scoping · phases                      ║
╚══════════════════════════════════════════════════════════════════╝
"""

# Default “core” CI-style subset
CORE_PATHS = [
    "tests/unit",
    "tests/auth",
    "tests/scoping",
    "tests/dashboard",
]


def main():
    args = sys.argv[1:]

    show_header = "--no-header" not in args
    extra = [a for a in args if a not in ("--no-header", "--all")]

    paths = ["tests"] if "--all" in sys.argv[1:] else CORE_PATHS

    if show_header:
        print(HEADER)

    cmd = [
        sys.executable,
        "-m",
        "pytest",
        *paths,
        "-p",
        "no:warnings",
        *extra,
    ]

    print("Running:", " ".join(cmd[2:]))
    print()

    result = subprocess.run(cmd, cwd=_ROOT)
    sys.exit(result.returncode)


if __name__ == "__main__":
    main()
