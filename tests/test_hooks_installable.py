"""Tests that the security controls are actually *installable and runnable*.

These exist because CI caught two stacked bugs that made every hook silently
inert on Linux and macOS, while Windows showed green:

  1. hooks were committed mode 100644. Git refuses to execute a non-executable
     hook -- and then CONTINUES, with no warning. The commit succeeds unscanned.
  2. hooks were committed with CRLF. The shebang becomes "#!/bin/sh\\r", which
     Linux reports as "bad interpreter". Same outcome: silently no protection.

Neither produced an error message. A security control that fails open, quietly,
on the two platforms most likely to run CI is worse than having no control at
all, because it manufactures false confidence.

A correct scanner that never executes is worth exactly nothing, so these
properties are pinned as hard invariants.
"""

import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
HOOKS = ("pre-commit", "pre-push", "commit-msg")


def git(*args: str) -> str:
    return subprocess.run(["git", *args], capture_output=True,
                          encoding="utf-8", errors="replace",
                          cwd=REPO, check=False).stdout


@pytest.mark.parametrize("hook", HOOKS)
def test_hook_exists(hook):
    assert (REPO / ".githooks" / hook).is_file(), f"missing hook: {hook}"


@pytest.mark.parametrize("hook", HOOKS)
def test_hook_is_executable_in_git_index(hook):
    """Mode must be 100755, not 100644.

    The check is against the git INDEX rather than the filesystem, because the
    filesystem bit does not survive a clone -- the index mode is what every
    other machine receives.
    """
    entry = git("ls-files", "-s", f".githooks/{hook}").strip()
    assert entry, f".githooks/{hook} is not tracked by git"
    mode = entry.split()[0]
    assert mode == "100755", (
        f".githooks/{hook} has mode {mode}, expected 100755. Git will refuse "
        f"to run it on Linux/macOS and will continue silently, so commits go "
        f"unscanned. Fix: git update-index --chmod=+x .githooks/{hook}"
    )


@pytest.mark.parametrize("hook", HOOKS)
def test_hook_has_lf_endings_in_git_index(hook):
    r"""No CRLF, or the shebang becomes '#!/bin/sh\r' and Linux cannot exec it."""
    blob = git("show", f":.githooks/{hook}")
    assert blob, f"could not read .githooks/{hook} from the index"
    assert "\r\n" not in blob, (
        f".githooks/{hook} contains CRLF in the git index. On Linux the "
        f"shebang resolves to '/bin/sh\\r' -> 'bad interpreter', git skips the "
        f"hook silently, and nothing is scanned. .gitattributes must pin "
        f"'.githooks/* text eol=lf'."
    )


@pytest.mark.parametrize("hook", HOOKS)
def test_hook_has_valid_shebang(hook):
    blob = git("show", f":.githooks/{hook}")
    first = blob.splitlines()[0] if blob else ""
    assert first.startswith("#!"), f".githooks/{hook} lacks a shebang"
    assert "\r" not in first, f".githooks/{hook} shebang carries a CR"


def test_gitattributes_pins_hook_line_endings():
    """The root cause fix must stay in place, not just the symptom."""
    ga = REPO / ".gitattributes"
    assert ga.is_file(), ".gitattributes is required to pin hook line endings"
    text = ga.read_text(encoding="utf-8")
    assert ".githooks/*" in text and "eol=lf" in text, (
        ".gitattributes must force LF for .githooks/* or the hooks will break "
        "again on the next Windows contributor."
    )


def test_no_tracked_python_file_has_crlf():
    """CRLF in Python sources produces noisy cross-platform diffs and was the
    proximate cause of the ruff failure on Linux while Windows passed."""
    offenders = []
    for rel in git("ls-files", "*.py").splitlines():
        if not rel.strip():
            continue
        if "\r\n" in git("show", f":{rel}"):
            offenders.append(rel)
    assert not offenders, f"CRLF found in git index for: {offenders}"


def test_ruff_is_pinned_exactly():
    """Unpinned linters are a scheduled outage.

    'ruff>=0.6' resolved to a newer release in CI than locally, which failed
    the build on rules that did not exist when the code was written. Lint
    versions must be exact so a CI run is reproducible from the repo alone.
    """
    text = (REPO / "pyproject.toml").read_text(encoding="utf-8")
    assert "ruff==" in text, (
        "ruff must be pinned with '==' in pyproject.toml. A floating linter "
        "turns every unrelated push into a coin flip."
    )


def test_setup_script_runs_clean():
    """scripts/setup_hooks.py is the documented first step after cloning; if it
    exits non-zero the onboarding instructions are wrong."""
    r = subprocess.run(
        [sys.executable, str(REPO / "scripts" / "setup_hooks.py")],
        capture_output=True, encoding="utf-8", errors="replace",
        cwd=REPO, check=False,
    )
    assert r.returncode == 0, f"setup_hooks.py failed:\n{r.stdout}\n{r.stderr}"
    assert "hooksPath" in r.stdout
