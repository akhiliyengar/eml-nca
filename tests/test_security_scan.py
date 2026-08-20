"""Tests for the security scanner.

Every fixture below is SYNTHETIC. Putting a real credential or a real internal
identifier in a test file would defeat the entire purpose of the scanner and
would itself be the leak.

Two failure modes matter and they are not symmetric:

    false negative  a real secret ships to a public repo. Unrecoverable.
    false positive  an honest commit is blocked. Annoying, and if frequent
                    enough people disable the hook -- which converts into the
                    first failure mode.

So we test both directions explicitly.
"""

import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from security.scan import (
    ALL_RULES,
    BLOCK,
    WARN,
    redact,
    scan_line,
    should_skip,
)


def sev(line: str) -> set[str]:
    return {f.rule.severity for f in scan_line("f.py", 1, line)}


def names(line: str) -> set[str]:
    return {f.rule.name for f in scan_line("f.py", 1, line)}


# ---------------------------------------------------------------- credentials

@pytest.mark.parametrize(
    "line,expect",
    [
        ('key = "AKIAIOSFODNN7EXAMPLE"', "aws-access-key"),
        ("tok = ghp_" + "a" * 36, "github-token"),
        ("pat = github_pat_" + "b" * 60, "github-fine-grained"),
        ("s = xoxb-000000000000-aaaaaaaaaaaaaaaa", "slack-token"),
        ("-----BEGIN RSA PRIVATE KEY-----", "private-key"),
        ("cs = DefaultEndpointsProtocol=https;AccountName=x;"
         "AccountKey=" + "Q" * 40 + ";", "azure-storage-conn"),
        ("url = https://x.blob.core.windows.net/c?sv=1&sig=" + "Z" * 30,
         "azure-sas"),
        ("h = Bearer " + "c" * 40, "bearer"),
        ('password = "hunter2hunter2"', "generic-assignment"),
        ('api_key="abcdef123456"', "generic-assignment"),
        ('client_secret: "s0me-l0ng-secret-value"', "generic-assignment"),
    ],
)
def test_credentials_are_blocked(line, expect):
    assert expect in names(line), f"missed {expect} in: {line[:60]}"
    assert BLOCK in sev(line)


def test_jwt_blocked():
    jwt = ("eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9."
           "eyJzdWIiOiIxMjM0NTY3ODkwIiwibmFtZSI6IkpvaG4ifQ."
           "dQw4w9WgXcQdQw4w9WgXcQdQw4w9WgXcQ")
    assert "jwt" in names(f"token = {jwt}")


# ------------------------------------------------------------------ corporate

@pytest.mark.parametrize(
    "line,expect",
    [
        ("contact: someone@microsoft.com", "corp-email"),
        ("host = build01.redmond.corp.microsoft.com", "corp-domain"),
        ("see https://eng.ms/docs/some/internal/page", "internal-eng-portal"),
        ("repo https://dev.azure.com/someorg/proj/_git/r", "internal-ado"),
        ("old https://someorg.visualstudio.com/proj", "internal-ado"),
        ("doc https://contoso.sharepoint.com/sites/team/Doc.docx",
         "internal-sharepoint"),
        ("chat https://teams.microsoft.com/l/meetup-join/xyz", "internal-teams"),
    ],
)
def test_corporate_identifiers_are_blocked(line, expect):
    assert expect in names(line)
    assert BLOCK in sev(line)


def test_bare_guid_warns_but_does_not_block():
    """GUIDs are legitimately common (test fixtures, UUID examples). Warn so a
    Service Tree / tenant / subscription id gets a second look, but do not
    block -- blocking on every GUID is how a scanner earns a --no-verify habit.
    """
    line = "sid = 00000000-1111-2222-3333-444444444444"
    assert "bare-guid" in names(line)
    assert sev(line) == {WARN}


# ---------------------------------------------------------------- environment

def test_windows_user_path_blocked():
    r"""C:\Users\<name>\... leaks the OS username."""
    assert "windows-userpath" in names(r'p = "C:\Users\someone\proj\data.csv"')


def test_onedrive_tenant_blocked():
    """A synced OneDrive folder name carries the tenant in plain text."""
    assert "onedrive-tenant" in names('base = "OneDrive - Contoso/Documents"')


def test_unix_home_path_blocked():
    assert "unix-homepath" in names('p = "/home/someone/project/x.py"')


# ------------------------------------------------------------ false positives

@pytest.mark.parametrize(
    "line",
    [
        "def eml(x, y): return exp(x) - log(y)",
        "# see arXiv:2603.21852 for the derivation",
        "url = 'https://arxiv.org/abs/2603.21852'",
        "assert abs(got - expected) < 1e-12",
        "rho = spectral_radius(jac)   # largest |eigenvalue|",
        "gh = 'https://github.com/akhiliyengar/eml-nca'",
        "EPS = 1e-6",
        "parser.add_argument('--mode', choices=['staged', 'tree'])",
        "print(f'gain={trace.geometric_mean:.4f}')",
        "kernel = np.exp(-((r - mu) ** 2) / (2 * sigma ** 2))",
    ],
)
def test_ordinary_research_code_is_not_flagged(line):
    """The hook must be silent on normal work. Every false positive here is a
    step toward someone disabling the hook entirely."""
    assert scan_line("f.py", 1, line) == []


def test_relative_paths_are_fine():
    assert scan_line("f.py", 1, 'p = "results/rung2/metrics.json"') == []
    assert scan_line("f.py", 1, "from pathlib import Path") == []


# ------------------------------------------------------------- suppression

def test_inline_pragma_suppresses():
    line = 'example = "AKIAIOSFODNN7EXAMPLE"  # allow-secret: AWS public doc sample'
    assert scan_line("f.py", 1, line) == []


def test_pragma_is_case_insensitive():
    line = "x = ghp_" + "a" * 36 + "  # ALLOW-SECRET: fixture"
    assert scan_line("f.py", 1, line) == []


def test_allowlist_skips_path():
    allow = {"results/generated.json"}
    assert should_skip("results/generated.json", allow)
    assert not should_skip("src/emlnca/ops.py", allow)


def test_binary_and_vendor_paths_skipped():
    assert should_skip("viz/three/node_modules/x/y.js", set())
    assert should_skip("results/frame.png", set())
    assert should_skip(".venv/lib/site-packages/numpy/__init__.py", set())
    assert not should_skip("src/emlnca/ops.py", set())


# ---------------------------------------------------------------- redaction

def test_redaction_hides_the_secret_body():
    """CI logs are themselves public on a public repo. A scanner that echoes
    the secret verbatim into the build log has merely moved the leak."""
    secret = "AKIAIOSFODNN7EXAMPLE"
    line = f'key = "{secret}"'
    m = ALL_RULES[0].pattern.search(line)
    out = redact(line, m.span())
    assert secret not in out
    assert "*" in out


# -------------------------------------------------------------- integration

def test_scanner_reads_non_ascii_diffs():
    """Regression: the scanner must never silently read nothing.

    subprocess(text=True) decodes with the LOCALE codec (cp1252 on Windows).
    A non-ASCII byte in a diff crashed the reader thread, the exception was
    swallowed, and .stdout returned None -- so the scan would have reported
    'clean' on content it never read. A false negative in a secret scanner is
    the one outcome that is genuinely unrecoverable, so this is pinned.
    """
    from security.scan import _git

    out = _git("diff", "--cached", "--unified=0")
    assert out is not None
    assert isinstance(out, str)

    log = _git("log", "--format=%H%x1f%an <%ae>%x1f%cn <%ce>")
    assert isinstance(log, str)
    assert log.strip(), "history must not read back empty"


def test_scanner_detects_secret_in_non_ascii_context():
    """Non-ASCII neighbours must not mask a finding."""
    line = 'clé = "AKIAIOSFODNN7EXAMPLE"  # naïve — résumé ✓'
    assert "aws-access-key" in names(line)


def test_scanner_runs_clean_on_this_repo():
    """End-to-end: the committed tree must itself be clean.

    This test is the reason the fixtures above are synthetic -- it scans the
    real repository, including this file.
    """
    root = Path(__file__).resolve().parents[1]
    r = subprocess.run(
        [sys.executable, str(root / "security" / "scan.py"), "--mode", "tree"],
        capture_output=True, text=True, cwd=root, check=False,
    )
    assert r.returncode == 0, f"repo tree is not clean:\n{r.stdout}\n{r.stderr}"


def test_history_identity_is_clean():
    """No corporate address anywhere in author/committer metadata.

    Unlike file contents, identity metadata cannot be corrected by a later
    commit -- only by rewriting history.
    """
    root = Path(__file__).resolve().parents[1]
    r = subprocess.run(
        [sys.executable, str(root / "security" / "scan.py"), "--mode", "all"],
        capture_output=True, text=True, cwd=root, check=False,
    )
    assert r.returncode == 0, f"history is not clean:\n{r.stdout}"
