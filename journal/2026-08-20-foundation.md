# Repository foundation: harness, invariants, and living documentation

thread: `t0-foundation`
status: hypothesis supported — the primitives can be made safe enough to iterate

## Expected

Before writing anything I expected the hard part to be the EML mathematics —
branch cuts, the complex domain, getting the published identities to reproduce.
I expected the infrastructure around it to be routine.

## Observed

The mathematics was the easy part. All published identities reproduced to
1e-12 on the first attempt, and `eml_stable` survived 5,000 iterations across
256 random starts without a single non-finite value.

**Everything that actually broke was infrastructure, and three of the four
failures were silent.**

| bug | how it failed | how it was found |
|---|---|---|
| corporate email in commit metadata | permanent once public | pre-flight audit |
| scanner read `stdout=None` | would report **clean** on unread content | dogfooding the scanner on its own commit |
| hooks inert on Linux (mode + CRLF) | git skips broken hooks **without warning** | CI job that commits a synthetic secret |
| unpinned `ruff` | CI failed on rules that did not exist when written | CI matrix |

Two findings worth keeping:

**1. The `ln(−1)` identity is knife-edge.** It agrees with the principal branch
— but the intermediate `e^e/z` lands ~1.9e-15 (about 8 ULPs) *below* the cut,
and the double negation cancels back to correct. Verified identical on glibc
and msvcrt, so it is stable across the two platforms tested, but it is 8 ULPs
from silently inverting every constant derived from `ln(−1)`. The paper reports
this as an outright sign error; the truth is more interesting — it is
platform-dependent luck.

**2. Ruff's `EXE001` and my hand-written hook test encode the same invariant.**
Arrived at independently, hours apart. That convergence is mild evidence the
invariant is real rather than an idiosyncratic worry, and it prompted
generalising the test from `.githooks/*` to every tracked file with a shebang.

## Interpretation

The dominant failure mode in this project is **failing open and quiet** — a
control that stops working without announcing it. That is worse than no
control, because it manufactures confidence. Three of four bugs had exactly
this shape, and the one class of test that caught them was *adversarial*: CI
that deliberately tries to commit a secret and asserts the attempt is refused.

Testing that a guard *works* is not the same as testing that it *fires*.

**What this does NOT mean:** nothing here says anything about whether EML helps
NCA. Zero evidence has been gathered on the actual research question. `t0` only
establishes that the primitives are safe enough to build on.

A process note, recorded because it is the same error this repo criticises in
the literature: **I described seed determinism as an implemented invariant when
no such test existed.** It was caught by a direct question, not by CI. The
correction is `tests/test_determinism.py`, and "never claim a test exists
without checking" is now the second non-negotiable in `AGENTS.md`.

## Next

**Rung 1, `t1-grayscott`** — deliberately the least likely to succeed.

It targets cross-variable interaction (`uv²`), which Asanuma documents as
EML's known weakness in the univariate-additive form. Running the experiment
most likely to fail first is cheap, is a real control, and if it *does* fail it
costs a day rather than discovering the same limitation three rungs up with a
month invested.

The alternative — jumping straight to `t2-lenia-gate` because it has the
highest prior — would mean the first result is a success with no calibration
for what failure looks like in this codebase.
