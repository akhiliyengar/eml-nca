# CHANGELOG

Format: [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).
This project is pre-release; there is no compatibility promise.

**Bugs get their failure mode recorded, not just their fix.** Three of the four
real bugs found so far failed *open and quiet* — they stopped protecting
without saying so — and that pattern is more useful to remember than any
individual patch.

---

## [Unreleased]

### Added
- **Research harness** — `harness/provenance.py` captures run_id, git SHA and
  cleanliness, seed, config hash, and environment versions;
  `reproducibility_problems()` returns gaps rather than raising, so an
  exploratory run can proceed while its record states plainly that it is not
  reproducible. `harness/record.py` implements the invariant/metric split and
  the `metrics.json` contract.
- **Determinism invariants** — `tests/test_determinism.py`: bitwise (not
  `allclose`) reproduction under fixed seed, a control proving different seeds
  actually differ, an interleaving test for global mutable state, and purity
  checks on the primitives.
- **Frozen/experimental config split** — `configs/frozen/` never changes, so
  assertions against it are invariants; `configs/experimental/` is where work
  happens, so the same assertions are metrics. Resolves the golden-test
  ambiguity structurally instead of by judgement call.
- **Living documentation** — `scripts/gen_docs.py` generates the repo map,
  test catalog, thread catalog and literature index into marker-delimited
  regions. `--check` fails CI when committed docs drift from the code.
- **Research thread registry** — `threads/registry.json`. Threads carry a
  hypothesis and an explicit falsifier, may fork via `parent`, and may
  converge. Abandoned threads keep their verdicts.
- **Literature fetcher** — `scripts/fetch_literature.py` downloads the 9-source
  corpus and records *why each paper matters*, which a bare citation list loses.
- **Agent instructions** — `AGENTS.md` as single source of truth, with thin
  pointers from `CLAUDE.md`, `.github/copilot-instructions.md` and
  `.cursor/rules/`. Five provider-agnostic skills in `skills/`.
- **SPEC.md** — five falsifiable hypotheses with stated priors, including two
  registered with an explicitly *low* prior because a negative result is
  publishable.
- **docs/SCOPE.md** — explicit does / does not, plus deliberately deferred
  items so they are not silently forgotten.

### Changed
- `ruff` pinned to `==0.16.3`.

---

## [0.1.0] — 2026-08-20

### Added
- EML primitives: vanilla (complex, principal branch), real-admissible
  (Günlü — raises rather than returning NaN), softplus-stable (Germany et al. —
  the only variant safe to iterate). Plus SOL, the 6-parameter generalized
  atom, and Erez's centered gate.
- Stability instrumentation: `GainTrace`, `spectral_radius`, analytic vs
  numeric Jacobian comparison, `check_finite`.
- Published identities as executable specification.
- Zero-dependency security scanner and five-layer guard chain.
- CI: security gate → 2-OS × 2-Python guard matrix → hook-effectiveness job.

### Fixed

Four real bugs. Noting how each was found, since three would have shipped
silently.

- **Corporate email in commit metadata.** The initial commit carried
  `@microsoft.com` in both author and committer fields. Caught by a pre-flight
  audit before the repo went public; history rewritten to a GitHub noreply
  identity. Would have been permanent and scraped within hours.

- **Scanner could report "clean" on content it never read.**
  `subprocess.run(text=True)` decodes using the *locale* codec (cp1252 on
  Windows). A non-ASCII byte raised `UnicodeDecodeError` inside subprocess's
  reader thread; the exception was swallowed and `.stdout` returned `None`. Had
  it returned `""` the scan would have passed vacuously — a **silent false
  negative**, the one unrecoverable failure for a secret scanner. Now forces
  UTF-8 and raises if stdout is undecodable. Mirror-image bug on output
  (`UnicodeEncodeError` killed the run *after* a finding) fixed the same way.

- **All git hooks inert on Linux and macOS.** Two stacked causes: mode `100644`
  (git refuses to exec) and CRLF line endings (`#!/bin/sh\r` → "bad
  interpreter"). Git skips a broken hook and **continues without warning**.
  Windows showed green throughout. Found only by the CI job that deliberately
  commits a synthetic secret. Fixed via `.gitattributes` + index mode `100755`;
  pinned by `tests/test_hooks_installable.py`.

- **`EXE001` — shebang without exec bit** on `scripts/setup_hooks.py` and
  `security/scan.py`. Same class as the hooks. Notable that ruff's lint rule
  and the hand-written hook test encode the *same invariant*, arrived at
  independently; the test was generalised from `.githooks/*` to every tracked
  file carrying a shebang.

- **Unpinned linter.** `ruff>=0.6` resolved to a newer release in CI than
  locally and failed on rules that did not exist when the code was written —
  dependency drift, within an hour of writing a README section warning about
  dependency drift.

### Documented
- **Branch-cut fragility.** The EML `ln` identity agrees with the principal
  branch on negative reals, but the intermediate `e^e/z` lands ~1.9e-15 (about
  8 ULPs) *below* the cut, and the double negation cancels back to correct. A
  different libm, rounding mode or FMA contraction could flip it, silently
  inverting every constant derived from `ln(−1)`. Pinned per-platform; the CI
  OS matrix exists for this. Verified identical on glibc and msvcrt.

### Process
- **Asserted a control that did not exist.** Seed determinism was described as
  an implemented invariant while no such test was in the repository. Caught by
  a direct question. Recorded here because it is precisely the failure this
  project criticises in the literature it studies, and the correction —
  `tests/test_determinism.py` — is now the first invariant listed in
  `AGENTS.md`.
