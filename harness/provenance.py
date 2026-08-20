"""Run provenance: the machinery that makes a number count as evidence.

A recorded metric without its exact production conditions is an anecdote. This
module captures everything needed to re-run a result and get the same answer,
and refuses to record anything it cannot fully describe.

Borrowed from deepseek-harness's `--dump-config` principle: you must always be
able to print the exact tree your machine actually booted. The research analogue
is that every metrics.json states precisely what produced it.
"""

from __future__ import annotations

import hashlib
import json
import platform
import subprocess
import sys
import time
import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[1]
SCHEMA_VERSION = 1


def _git(*args: str) -> str:
    r = subprocess.run(["git", *args], capture_output=True, encoding="utf-8",
                       errors="replace", cwd=REPO, check=False)
    return (r.stdout or "").strip()


def git_state() -> dict[str, Any]:
    """Commit and cleanliness.

    `dirty` is not cosmetic. A result produced from an uncommitted working tree
    cannot be reproduced by anyone else, including you next week, because the
    code that made it exists nowhere but your disk.
    """
    sha = _git("rev-parse", "HEAD")
    dirty = bool(_git("status", "--porcelain").strip())
    return {
        "sha": sha or "unknown",
        "short": sha[:9] if sha else "unknown",
        "branch": _git("rev-parse", "--abbrev-ref", "HEAD") or "unknown",
        "dirty": dirty,
    }


def env_state() -> dict[str, Any]:
    """Interpreter and numeric-stack versions.

    numpy is recorded explicitly because a change in reduction order across
    releases can move a float result -- exactly the drift the weekly CI run
    exists to catch.
    """
    env: dict[str, Any] = {
        "python": sys.version.split()[0],
        "platform": platform.platform(),
        "machine": platform.machine(),
    }
    try:
        import numpy
        env["numpy"] = numpy.__version__
    except ImportError:
        env["numpy"] = None
    return env


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    h.update(path.read_bytes())
    return h.hexdigest()


def sha256_obj(obj: Any) -> str:
    """Content hash of a config object, key order independent."""
    blob = json.dumps(obj, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(blob).hexdigest()


@dataclass
class Provenance:
    """Everything required to re-run a result."""

    run_id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    schema: int = SCHEMA_VERSION
    thread: str = "unassigned"
    config_path: str | None = None
    config_sha256: str | None = None
    seed: int | None = None
    git: dict[str, Any] = field(default_factory=git_state)
    env: dict[str, Any] = field(default_factory=env_state)
    started_utc: str = field(
        default_factory=lambda: time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    )
    duration_s: float | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def reproducibility_problems(self) -> list[str]:
        """Reasons this run is not independently reproducible.

        Returned rather than raised so a caller can decide: an exploratory run
        may legitimately be dirty, but the record must say so out loud instead
        of quietly implying rigour it does not have.
        """
        problems = []
        if self.seed is None:
            problems.append("no seed recorded: the run cannot be repeated")
        if self.git.get("dirty"):
            problems.append(
                "working tree was dirty: the exact code is not committed "
                "anywhere, so no one else can reproduce this"
            )
        if self.git.get("sha") == "unknown":
            problems.append("no git commit: the code version is unknown")
        if self.config_sha256 is None:
            problems.append("no config hash: inputs are unverifiable")
        return problems


def dump_provenance() -> str:
    """Human-readable provenance for the current checkout.

    The research analogue of `dsh --dump-config`: before trusting any number,
    you should be able to see exactly what would produce it.
    """
    p = Provenance()
    dirty = "  [DIRTY]" if p.git["dirty"] else ""
    lines = [
        "provenance",
        f"  git      {p.git['short']} on {p.git['branch']}{dirty}",
        f"  python   {p.env['python']}",
        f"  numpy    {p.env['numpy']}",
        f"  platform {p.env['platform']}",
    ]
    problems = p.reproducibility_problems()
    if problems:
        lines.append("  reproducibility gaps:")
        lines.extend(f"    - {x}" for x in problems)
    return "\n".join(lines)


if __name__ == "__main__":
    print(dump_provenance())
