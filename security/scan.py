#!/usr/bin/env python3
"""Pre-commit / pre-push / CI secret and identifier scanner.

Design constraints, in priority order:

1. ZERO third-party dependencies. This runs in a git hook. If it can break
   because a package upgraded, it will eventually break at the worst moment
   and someone will disable it. Standard library only.
2. Scans ADDED lines only. Redacting a secret should let the commit through;
   the removal itself must not be flagged forever.
3. Every finding is suppressible, with a visible audit trail. A scanner that
   cannot be overridden gets bypassed wholesale with --no-verify, which is
   strictly worse than a scanner that is overridden line by line.
4. Fast. Under ~1s on a normal diff, or people will bypass it.

Suppression:
    inline           append  # allow-secret: <reason>   to the line
    file-level       add the path to security/allowlist.txt
    emergency        git commit --no-verify   (use never; CI still catches it)

Severity:
    BLOCK  refuses the commit. Credentials and corporate identifiers.
    WARN   prints, allows. Things that are usually fine but worth a glance.
"""

from __future__ import annotations

import argparse
import pathlib
import re
import subprocess
import sys

REPO = pathlib.Path(__file__).resolve().parent.parent
ALLOWLIST = REPO / "security" / "allowlist.txt"
PRAGMA = re.compile(r"#\s*allow-secret\s*:", re.IGNORECASE)

BLOCK = "BLOCK"
WARN = "WARN"


class Rule:
    __slots__ = ("name", "pattern", "severity", "why")

    def __init__(self, name: str, pattern: str, severity: str, why: str):
        self.name = name
        self.pattern = re.compile(pattern)
        self.severity = severity
        self.why = why


# --------------------------------------------------------------------------
# Credentials. Universal, unambiguous, always BLOCK.
# --------------------------------------------------------------------------
CREDENTIAL_RULES = [
    Rule("aws-access-key", r"\b(?:AKIA|ASIA)[0-9A-Z]{16}\b", BLOCK,
         "AWS access key id"),
    Rule("github-token", r"\bgh[pousr]_[A-Za-z0-9]{36,}\b", BLOCK,
         "GitHub personal access / OAuth token"),
    Rule("github-fine-grained", r"\bgithub_pat_[A-Za-z0-9_]{50,}\b", BLOCK,
         "GitHub fine-grained PAT"),
    Rule("slack-token", r"\bxox[baprs]-[A-Za-z0-9-]{10,}\b", BLOCK,
         "Slack token"),
    Rule("private-key",
         r"-----BEGIN (?:RSA |EC |DSA |OPENSSH |PGP )?PRIVATE KEY-----",
         BLOCK, "private key block"),
    Rule("azure-storage-conn",
         r"DefaultEndpointsProtocol=https?;.*AccountKey=[A-Za-z0-9+/=]{20,}",
         BLOCK, "Azure storage connection string"),
    Rule("azure-sas", r"[?&]sig=[A-Za-z0-9%+/=]{20,}", BLOCK,
         "Azure SAS signature"),
    Rule("jwt",
         r"\beyJ[A-Za-z0-9_-]{10,}\.eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\b",
         BLOCK, "JSON Web Token"),
    Rule("bearer", r"\b[Bb]earer\s+[A-Za-z0-9\-._~+/]{24,}=*", BLOCK,
         "bearer token"),
    Rule("generic-assignment",
         r"(?i)\b(?:api[_-]?key|apikey|secret|passwd|password|client[_-]?secret|"
         r"access[_-]?token|auth[_-]?token|conn(?:ection)?[_-]?string)\b"
         r"\s*[:=]\s*[\"'][^\"'\s]{8,}[\"']",
         BLOCK, "hardcoded credential assignment"),
]

# --------------------------------------------------------------------------
# Corporate / tenant identifiers. The specific risk of a personal public repo
# authored on a corporate machine.
#
# NOTE: these are PATTERNS, never literal internal values. Nothing sensitive is
# encoded in this file -- that would defeat the purpose.
# --------------------------------------------------------------------------
CORPORATE_RULES = [
    Rule("corp-email", r"\b[A-Za-z0-9._%+-]+@microsoft\.com\b", BLOCK,
         "corporate email address"),
    Rule("corp-domain",
         r"\b(?:[A-Za-z0-9-]+\.)*(?:corp|redmond|northamerica)\.microsoft\.com\b",
         BLOCK, "internal corporate hostname"),
    Rule("internal-eng-portal", r"\bhttps?://eng\.ms/\S*", BLOCK,
         "internal engineering portal URL"),
    Rule("internal-ado",
         r"\bhttps?://(?:[A-Za-z0-9-]+\.)?(?:visualstudio\.com|dev\.azure\.com)/\S*",
         BLOCK, "internal Azure DevOps URL"),
    Rule("internal-sharepoint",
         r"\bhttps?://[A-Za-z0-9-]+\.sharepoint\.com/\S*", BLOCK,
         "SharePoint URL (embeds tenant and document identity)"),
    Rule("internal-teams", r"\bhttps?://teams\.microsoft\.com/l/\S*", BLOCK,
         "Teams deep link"),
    Rule("bare-guid",
         r"\b[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-"
         r"[0-9a-fA-F]{4}-[0-9a-fA-F]{12}\b",
         WARN, "bare GUID (Service Tree / tenant / subscription ids look like this)"),
]

# --------------------------------------------------------------------------
# Local environment leakage. Absolute paths quietly expose the OS username and
# often the corporate tenant via the OneDrive folder name.
# --------------------------------------------------------------------------
ENVIRONMENT_RULES = [
    Rule("windows-userpath", r"[A-Za-z]:\\+Users\\+[^\\\s\"']+", BLOCK,
         "absolute Windows path containing a username"),
    Rule("unix-homepath", r"/(?:home|Users)/[A-Za-z0-9._-]+/", BLOCK,
         "absolute home path containing a username"),
    Rule("onedrive-tenant", r"OneDrive\s*-\s*[A-Za-z][A-Za-z0-9 ]+", BLOCK,
         "OneDrive folder name reveals the tenant"),
    Rule("unc-share", r"\\\\[A-Za-z0-9._-]+\\[A-Za-z0-9$._-]+", WARN,
         "UNC network share path"),
]

ALL_RULES = CREDENTIAL_RULES + CORPORATE_RULES + ENVIRONMENT_RULES

SKIP_DIRS = {".git", ".venv", "node_modules", "__pycache__", "dist", "build",
             ".pytest_cache", ".ruff_cache", "media", ".mypy_cache"}
SKIP_SUFFIXES = {".png", ".jpg", ".jpeg", ".gif", ".mp4", ".webm", ".pdf",
                 ".zip", ".gz", ".npz", ".npy", ".woff", ".woff2", ".ico",
                 ".pyc", ".so", ".dll", ".onnx", ".pt", ".pth", ".safetensors"}


class Finding:
    __slots__ = ("excerpt", "line_no", "path", "rule")

    def __init__(self, path: str, line_no: int, rule: Rule, excerpt: str):
        self.path = path
        self.line_no = line_no
        self.rule = rule
        self.excerpt = excerpt

    def render(self) -> str:
        tag = "BLOCK" if self.rule.severity == BLOCK else "warn "
        return (f"  [{tag}] {self.path}:{self.line_no}\n"
                f"          rule : {self.rule.name} ({self.rule.why})\n"
                f"          text : {self.excerpt}")


def redact(text: str, span: tuple[int, int]) -> str:
    """Show context without reprinting the secret into logs or CI output."""
    s, e = span
    hit = text[s:e]
    keep = 4 if len(hit) > 12 else 1
    masked = hit[:keep] + "*" * max(len(hit) - keep * 2, 3) + hit[len(hit) - keep:]
    return (text[:s] + masked + text[e:]).strip()[:160]


def load_allowlist() -> set[str]:
    if not ALLOWLIST.exists():
        return set()
    out = set()
    for raw in ALLOWLIST.read_text(encoding="utf-8").splitlines():
        s = raw.strip()
        if s and not s.startswith("#"):
            out.add(s)
    return out


def should_skip(path: str, allow: set[str]) -> bool:
    p = pathlib.PurePosixPath(path.replace("\\", "/"))
    if any(part in SKIP_DIRS for part in p.parts):
        return True
    if p.suffix.lower() in SKIP_SUFFIXES:
        return True
    return str(p) in allow


def scan_line(path: str, line_no: int, line: str) -> list[Finding]:
    if PRAGMA.search(line):
        return []
    found = []
    for rule in ALL_RULES:
        m = rule.pattern.search(line)
        if m:
            found.append(Finding(path, line_no, rule, redact(line, m.span())))
    return found


def _git(*args: str) -> str:
    """Run git and return stdout as UTF-8 text.

    encoding= is NOT optional here. subprocess(text=True) decodes using the
    LOCALE codec, which on Windows is typically cp1252. Any non-ASCII byte in a
    diff then raises UnicodeDecodeError inside subprocess's reader thread, the
    exception is swallowed, and .stdout comes back as None.

    That failure mode is uniquely bad for a scanner: had it yielded "" instead
    of None, every scan would have reported CLEAN on content it never read --
    a silent false negative. The explicit None check below exists so this can
    only ever fail loudly.
    """
    r = subprocess.run(
        ["git", *args],
        capture_output=True,
        encoding="utf-8",
        errors="replace",
        cwd=REPO,
        check=False,
    )
    if r.stdout is None:
        raise RuntimeError(
            f"git {' '.join(args)} produced no decodable stdout. Refusing to "
            f"continue: a scanner that reads nothing would report 'clean'."
        )
    return r.stdout


def scan_diff(rev_range: str | None) -> list[Finding]:
    """Scan only ADDED lines, so redacting a secret unblocks the commit."""
    allow = load_allowlist()
    diff = (_git("diff", "--unified=0", rev_range) if rev_range
            else _git("diff", "--cached", "--unified=0"))

    findings: list[Finding] = []
    path, line_no, skip = "", 0, False
    for raw in diff.splitlines():
        if raw.startswith("+++ b/"):
            path = raw[6:]
            skip = should_skip(path, allow)
        elif raw.startswith("@@"):
            m = re.search(r"\+(\d+)", raw)
            line_no = int(m.group(1)) if m else 0
        elif raw.startswith("+") and not raw.startswith("+++"):
            if not skip:
                findings.extend(scan_line(path, line_no, raw[1:]))
            line_no += 1
    return findings


def scan_tree() -> list[Finding]:
    """Full working-tree scan of tracked files. Used in CI."""
    allow = load_allowlist()
    findings: list[Finding] = []
    for rel in _git("ls-files").splitlines():
        if not rel or should_skip(rel, allow):
            continue
        try:
            text = (REPO / rel).read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        for i, line in enumerate(text.splitlines(), start=1):
            findings.extend(scan_line(rel, i, line))
    return findings


def scan_history() -> list[Finding]:
    """Author/committer identity across all commits.

    File contents can be cleaned by a later commit; identity metadata cannot.
    A corporate email in an old commit stays exposed forever on a public repo.
    """
    findings: list[Finding] = []
    ident_rules = [r for r in CORPORATE_RULES
                   if r.name in {"corp-email", "corp-domain"}]
    for ln in _git("log", "--format=%H%x1f%an <%ae>%x1f%cn <%ce>").splitlines():
        parts = ln.split("\x1f")
        if len(parts) != 3:
            continue
        sha, author, committer = parts
        for who, val in (("author", author), ("committer", committer)):
            for rule in ident_rules:
                m = rule.pattern.search(val)
                if m:
                    findings.append(
                        Finding(f"commit {sha[:9]} ({who})", 0, rule,
                                redact(val, m.span())))
    return findings


def main() -> int:
    # Console encoding, mirror image of the _git decode problem. Windows
    # consoles default to cp1252, so printing a redacted line containing any
    # non-ASCII character raises UnicodeEncodeError and the scan dies AFTER
    # finding something -- the report is lost precisely when it matters.
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass

    ap = argparse.ArgumentParser(description="Secret / identifier scanner")
    ap.add_argument("--mode", choices=["staged", "range", "tree", "all"],
                    default="staged")
    ap.add_argument("--range", dest="rev_range", default=None)
    args = ap.parse_args()

    if args.mode == "staged":
        findings = scan_diff(None)
    elif args.mode == "range":
        findings = scan_diff(args.rev_range)
    elif args.mode == "tree":
        findings = scan_tree()
    else:
        findings = scan_tree() + scan_history()

    if not findings:
        print("security scan: clean")
        return 0

    blocking = [f for f in findings if f.rule.severity == BLOCK]
    warning = [f for f in findings if f.rule.severity == WARN]

    print("\n" + "=" * 72)
    print(" SECURITY SCAN")
    print("=" * 72)
    if blocking:
        print(f"\n{len(blocking)} BLOCKING finding(s):\n")
        for f in blocking:
            print(f.render())
    if warning:
        print(f"\n{len(warning)} warning(s):\n")
        for f in warning:
            print(f.render())

    if blocking:
        print("\n" + "-" * 72)
        print(" Commit refused. To resolve:")
        print("   1. remove the value, or move it to an untracked .env, or")
        print("   2. append   # allow-secret: <reason>   if it is a false positive, or")
        print("   3. add the path to security/allowlist.txt for generated files")
        print(" Do NOT reach for --no-verify. This repo is PUBLIC.")
        print("-" * 72 + "\n")
        return 1

    print("\nwarnings only; commit allowed\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
