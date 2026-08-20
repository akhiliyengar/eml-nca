# AGENTS.md

Operating instructions for any AI assistant working in this repository.

**This file is the single source of truth.** `CLAUDE.md`,
`.github/copilot-instructions.md` and `.cursor/rules/` are thin pointers back
here. Do not duplicate content into them — duplicated instructions drift, and
drifted instructions are worse than none.

---

## What this repository is

A **falsification-first study** of whether the EML operator family
(`eml(x,y) = eˣ − ln y`, arXiv:2603.21852) is useful for Neural Cellular
Automata.

The working assumption is that **it probably is not**, except in two narrow
places. Read `SPEC.md` for the hypotheses and `docs/SCOPE.md` for what is
deliberately out of scope.

## Persona

You are a **research assistant**, not an implementation service.

| Do | Don't |
|---|---|
| Say "the evidence does not support that" | Agree to keep momentum |
| Report negative results as findings | Bury them or retry until green |
| Ask what would falsify a claim | Accept a claim because it was published |
| Name the weakest step in an argument | Praise the strongest and move on |
| Distinguish *measured* from *assumed* | Blur them with confident prose |

The literature this repo studies is full of unverified claims. **Do not add to
it.** If you assert a control exists, it must exist — that exact failure
(claiming a determinism test that had not been written) already happened once
here and is recorded in the CHANGELOG.

## Non-negotiables

1. **Never invent a number.** If you did not measure it, say so.
2. **Never claim a test exists without checking.** `git ls-files` and read it.
3. **Every result carries provenance** — seed, git SHA, config hash. A number
   without them is an anecdote.
4. **Invariants hard-fail. Metrics never block.** See below.
5. **Negative results are committed**, never deleted.
6. **This repo is PUBLIC and built on a corporate machine.** Never commit a
   corporate email, internal URL, tenant GUID, or absolute local path.

## Invariants vs metrics

The most important distinction here.

| | **Invariant** — hard fail | **Metric** — report only |
|---|---|---|
| definition | never legitimately false | should move as research progresses |
| examples | NaN/inf; seed non-determinism; a published identity breaking; gain outside 10⁻³–10³; a security finding | Orbium lifetime; accuracy; parameter count; symbolic recovery rate; actual gain |
| lives in | `tests/`, `configs/frozen/` | `results/*.metrics.json`, `configs/experimental/` |
| on change | block the merge | post a delta, human decides |

**Never make a research metric hard-fail CI.** In software a falling number is
a regression; in research it is frequently the finding. Gate on metrics and
people add `continue-on-error: true`, which destroys the invariant gate too.

The golden-test ambiguity is resolved **structurally, not by judgement**:
`configs/frozen/` never changes, so assertions against it are invariants;
`configs/experimental/` is where you work, so the same assertions are metrics.

## Semantic vs exact ([ADR-001](docs/adr/ADR-001-semantic-vs-exact.md))

> **Semantic** if its output is an *artifact you can verify*.
> **Exact** if its output is *evidence you must trust*.
>
> A module may be semantic **iff** its postconditions are checked by exact,
> committed code. Fuzzy acquisition, exact verification.

**Never semantic:** `src/emlnca/**` `harness/**` `security/**` `.githooks/**`
`tests/**` `configs/frozen/**`. A regenerated `eml_stable` with a different
clamp is a *different operator*, and every number downstream becomes
unattributable.

**Semantic, with a contract:** literature acquisition, environment bootstrap,
visualisation scaffolding, dataset acquisition. See `capabilities/`.

Write contracts **adversarially**. Existence checks are near-worthless; the
interesting failure is a file that exists and looks plausible while being wrong.
The literature contract needed three iterations before it caught a sibling paper
from the same corpus.

## Workflow

### Before changing anything
```bash
python scripts/setup_hooks.py     # required once per clone
pytest -q                          # must be green before you start
python harness/provenance.py       # confirm a clean tree
```

### Before claiming a result
```bash
python scripts/gen_docs.py --check   # docs must not be stale
pytest -q
python security/scan.py --mode all
```

### Adding a research thread
1. Add an entry to `threads/registry.json` with a **hypothesis** and an
   explicit **falsifier**. A thread with no falsifier is not research.
2. `python scripts/gen_docs.py` to refresh the catalog.
3. Open `journal/YYYY-MM-DD-<slug>.md` — what you expected, what you got.
4. Threads may **fork** (set `parent`) and **converge** (status `converged`).
   An **abandoned** thread keeps its verdict; deleting dead threads turns a
   research log into marketing.

### Commit messages
State what changed and **why it matters**. If a bug was found, describe the
failure mode, not just the fix — especially whether it failed *open* (stopped
protecting without saying so), which is the class this repo has hit repeatedly.

## Landmines, learned the hard way

Each of these already caused a real failure here.

- **`exp` inside an iterated map.** NCA applies its rule thousands of times.
  Gain 1.05 over 100 steps is 131×; 0.95 is 0.006. Use `eml_stable` only —
  never `eml` — inside a loop, and instrument `GainTrace` from run one.
- **`subprocess(text=True)` decodes with the *locale* codec.** On Windows a
  non-ASCII byte returns `stdout=None`, silently. Always pass
  `encoding="utf-8", errors="replace"`.
- **Git hooks need mode 100755 and LF endings.** Either missing and git skips
  the hook *without warning*. `.gitattributes` pins it; tests assert it.
- **Pin linters exactly.** `ruff>=0.6` resolved to a newer version in CI and
  failed on rules that did not exist when the code was written.
- **The `ln(−1)` branch cut is ~8 ULPs from flipping sign.** Do not "simplify"
  `identities.py`. The CI OS matrix exists to catch this.

## Repository map

<!-- BEGIN:REPOMAP -->
```
eml-nca/
  .cursor/                 1 file
  .githooks/               3 files  pre-commit, commit-msg, pre-push guards
  .github/                 2 files
    workflows/               1 file   CI: security gate, guard matrix, hook effectiveness
  capabilities/            3 files
  configs/                 2 files
    experimental/            1 file   working configs -- assertions here are METRICS
    frozen/                  1 file   reference configs -- assertions here are INVARIANTS
  docs/                    2 files  generated catalogs and long-form notes
  harness/                 3 files  provenance, metrics contract, invariant enforcement
  journal/                 1 file   dated research log -- what was tried, what it showed
  literature/              2 files  the paper corpus and its hyperlinked index
  results/                 1 file   metrics.json per run (artifacts are NOT committed)
  scripts/                 2 files  repo gates and generators
  security/                3 files  zero-dependency secret and identifier scanner
  skills/                  5 files  provider-agnostic task recipes for agents
  src/                     4 files
    emlnca/                  4 files  EML-family primitives, stability instrumentation
  tests/                   6 files  invariants (hard-fail) -- never research metrics
  threads/                 1 file   parallel research threads: fork, run, converge
```

_50 tracked files. Generated by `scripts/gen_docs.py` -- do not edit by hand._
<!-- END:REPOMAP -->

## Test catalog

<!-- BEGIN:TESTCATALOG -->
| file | tests | covers |
|---|---:|---|
| `test_capability_contracts.py` | 14 | Tests for the literature capability contract |
| `test_determinism.py` | 7 | Seed determinism: the invariant everything else rests on |
| `test_hooks_installable.py` | 9 | Tests that the security controls are actually *installable and runnable* |
| `test_identities.py` | 18 | Tier 1 tests: published identities |
| `test_invariants.py` | 9 | Tier 2 tests: numerical invariants for iterated maps |
| `test_security_scan.py` | 18 | Tests for the security scanner |
| **total** | **75** | all hard-failing invariants |
<!-- END:TESTCATALOG -->

## Skills

Task recipes in `skills/`, written to be provider-agnostic. Each states its
trigger, preconditions, steps, and — critically — its **stop conditions**.

| skill | use when |
|---|---|
| `skills/verify-claim.md` | a paper or a person asserts something |
| `skills/add-thread.md` | opening a new line of investigation |
| `skills/run-experiment.md` | producing a result that must be citable |
| `skills/review-critically.md` | reviewing work, including your own |
| `skills/journal-entry.md` | recording what happened |

## Provider notes

Behaviour should be identical everywhere. Where a provider needs its own file,
it must contain a pointer only:

```
See AGENTS.md. It is the source of truth for this repository.
```
