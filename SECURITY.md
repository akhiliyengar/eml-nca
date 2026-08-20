# Security & Privacy

This repository is **public** and is developed on a corporate machine. The
controls below exist to keep those two facts compatible.

## Threat model

The realistic risk here is not a targeted attacker. It is **accidental
disclosure** through routine developer actions:

| Risk | How it happens | Control |
|---|---|---|
| Corporate email in commit metadata | default `git config user.email` on a work machine | `pre-commit` identity guard + repo-local config |
| Credentials in source | pasted token, connection string, `.env` copied in | `pre-commit` + `pre-push` content scan |
| Internal URLs | a link pasted into a docstring or commit message | pattern rules for ADO / SharePoint / eng.ms / Teams |
| Local path leakage | a notebook or config capturing an absolute path — exposes OS username, and the OneDrive folder name exposes the tenant | `windows-userpath`, `onedrive-tenant` rules |
| Tenant / Service Tree GUIDs | copied from an internal portal | `bare-guid` warning |
| Secret echoed into CI logs | a scanner that prints what it found | all findings are redacted before printing |

## Layers

Defence in depth, because any single layer can be bypassed.

```
1. git config          repo-local privacy-safe identity
2. .githooks/commit-msg   scans the commit message
3. .githooks/pre-commit   identity guard + scans staged content
4. .githooks/pre-push     re-scans the pushed range + full history identity
5. CI (GitHub Actions)    scans the whole tree + history on every push/PR
```

Layers 2–4 are local and can be skipped with `--no-verify`. **Layer 5 cannot.**
That is deliberate: local hooks are for fast feedback, CI is the actual gate.

## Setup (required after clone)

Git hooks are **not** transferred by `git clone`. Activate them once:

```bash
python scripts/setup_hooks.py
```

This sets `core.hooksPath` to the version-controlled `.githooks/` directory and
verifies your commit identity is not a corporate address.

## Running the scanner manually

```bash
python security/scan.py --mode staged   # staged changes (what pre-commit uses)
python security/scan.py --mode tree     # every tracked file
python security/scan.py --mode all      # tree + commit-identity history
python security/scan.py --mode range --range main..HEAD
```

## Suppressing a false positive

In order of preference:

1. **Inline** — keeps the exemption next to the code, visible in review:
   ```python
   EXAMPLE = "AKIAIOSFODNN7EXAMPLE"  # allow-secret: AWS public documentation sample
   ```
2. **Path allowlist** — `security/allowlist.txt`, for generated or vendored files only.
3. **`--no-verify`** — don't. CI will reject it anyway, and now it is in your
   local history.

## If something leaks anyway

Speed matters more than tidiness. Assume anything pushed to a public repo was
scraped within minutes.

1. **Revoke the credential first.** Do not start with git. A rotated secret is
   harmless; a scrubbed-but-live secret is not.
2. Rewrite history (`git filter-repo`, or `git commit --amend --reset-author`
   for the most recent commit) and force-push.
3. GitHub caches unreachable objects — open a support request to purge them,
   or delete and recreate the repository.
4. Add a rule to `security/scan.py` so the same class cannot recur, and a test
   in `tests/test_security_scan.py`.

## Design notes

**Why zero dependencies.** The scanner is standard library only. A hook that can
break because a package upgraded will eventually break at the worst possible
moment, and the reflex is to disable it.

**Why added lines only.** The diff scan looks at `+` lines. Redacting a secret
should unblock the commit; the removal itself must not be flagged forever.

**Why GUIDs only warn.** GUIDs appear legitimately all over test fixtures. A
scanner that blocks on every GUID trains people to reach for `--no-verify`,
which converts a false-positive problem into a false-negative problem.

**Why identity is checked separately from content.** File contents can be fixed
by a later commit. Author and committer metadata cannot — only by rewriting
history. It therefore gets its own check, across all commits, on every push.
