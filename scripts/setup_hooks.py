#!/usr/bin/env python3
"""One-time repository setup: activate hooks and verify commit identity.

Git hooks are NOT transferred by `git clone`, and `.git/hooks/` is not version
controlled. Pointing `core.hooksPath` at the tracked `.githooks/` directory is
what makes these guards shareable and reviewable.

Usage:
    python scripts/setup_hooks.py
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
BAD_DOMAINS = ("@microsoft.com", ".microsoft.com")


def git(*args: str, check: bool = True) -> str:
    r = subprocess.run(["git", *args], capture_output=True, text=True,
                       cwd=REPO, check=False)
    if check and r.returncode != 0:
        raise SystemExit(f"git {' '.join(args)} failed: {r.stderr.strip()}")
    return r.stdout.strip()


def main() -> int:
    print("=" * 66)
    print(" eml-nca repository setup")
    print("=" * 66)

    git("config", "core.hooksPath", ".githooks")
    print(f"  hooks       : core.hooksPath -> {git('config', 'core.hooksPath')}")

    for hook in ("pre-commit", "pre-push", "commit-msg"):
        p = REPO / ".githooks" / hook
        print(f"                {'ok  ' if p.exists() else 'MISS'}  {hook}")

    email = git("config", "user.email", check=False)
    name = git("config", "user.name", check=False)
    print(f"  identity    : {name or '<unset>'} <{email or '<unset>'}>")

    problems = []
    if not email:
        problems.append("user.email is unset")
    elif any(d in email.lower() for d in BAD_DOMAINS):
        problems.append(f"user.email is a corporate address: {email}")

    if problems:
        print("\n" + "-" * 66)
        print("  ACTION REQUIRED")
        for p in problems:
            print(f"    - {p}")
        print("\n  This repository is PUBLIC. Commit metadata is permanent and")
        print("  is scraped within hours of a push. Set a repo-local identity:")
        print("\n    git config user.name  'your-github-handle'")
        print("    git config user.email '<id>+<handle>@users.noreply.github.com'")
        print("\n  Find your id at:  https://api.github.com/users/<handle>")
        print("-" * 66)
        return 1

    print("\n  running scanner over tree + history ...")
    r = subprocess.run([sys.executable, str(REPO / "security" / "scan.py"),
                        "--mode", "all"], cwd=REPO, check=False)
    if r.returncode != 0:
        print("\n  scanner reported blocking findings; resolve before committing.")
        return 1

    print("\n  setup complete. Hooks are active for this clone.")
    print("=" * 66)
    return 0


if __name__ == "__main__":
    sys.exit(main())
