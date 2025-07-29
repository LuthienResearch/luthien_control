#!/usr/bin/env python3
"""Custom formatter that runs ruff with unsafe fixes."""

import subprocess
import sys


def main():
    """Run ruff format and check with unsafe fixes on the given file."""
    if len(sys.argv) < 2:
        print("Usage: format_with_unsafe.py <file>")
        sys.exit(1)

    file_path = sys.argv[1]

    # Run ruff format
    subprocess.run(["poetry", "run", "ruff", "format", file_path], check=True)

    # Run ruff check with unsafe fixes
    subprocess.run(["poetry", "run", "ruff", "check", file_path, "--fix", "--unsafe-fixes"], check=True)


if __name__ == "__main__":
    main()
