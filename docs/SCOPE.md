# SCOPE — what this repository does and does not do

Scope creep is how research projects die. This file is the boundary, and it is
enforced in review: a change that pulls the repo across one of these lines
should be rejected or should first move the line here, deliberately.

---

## ✅ Does

**Investigates**
- Whether EML-family primitives offer measurable advantage in Neural Cellular
  Automata — parameter count, long-horizon stability, analytic stability
  prediction
- Whether Erez's non-monotone gate can replace Lenia's Gaussian growth function
- Whether ρ(J) from an exact closed-form Jacobian predicts pattern survival

**Verifies**
- Published claims from the EML corpus, against their own primary evidence
- Its own claims, with tests that must exist before they are asserted

**Provides**
- A zero-dependency EML implementation with three explicitly-scoped variants
  (vanilla, real-admissible, softplus-stable)
- Stability instrumentation: `GainTrace`, spectral radius, analytic vs numeric
  Jacobians
- A reproducibility harness that refuses to record an undescribable run
- A research journal and a thread registry that keep the *argument*, not just
  the code
- Security controls appropriate to a public repo built on a corporate machine

**Records**
- Negative results, permanently, with equal care to positive ones
- Abandoned threads with their verdicts

---

## ❌ Does not

**Not a library.** No stable API, no semantic versioning, no deprecation
policy. Pin a commit if you depend on it. Optimising for downstream consumers
would trade away the freedom to restructure, which at this stage is worth more.

**Not a general EML implementation.** Only what the experiments need. It does
not implement the EML compiler, RPN machine, or the full 36-primitive
calculator basis from the source paper — the reference implementation already
exists at `VA00/SymbolicRegressionPackage`.

**Not a Lenia or NCA reimplementation.** It interoperates with
`Chakazul/Lenia` (MIT) and `google-research/self-organising-systems`
(Apache-2.0). Reimplementing them would introduce differences that confound
exactly the comparison being made.

**Not a training platform.** GitHub Actions has no GPU, 16 GB RAM and a 6-hour
cap. Rungs 1–2 fit on CPU; Rung 3 does not. Heavy training happens locally or
on Colab, and the repo is the **ledger of results**, not the compute substrate.

**Not an artifact store.** `metrics.json`, configs, seeds and manifests are
committed. Videos, weights, frame dumps and PDFs are not — they are
regenerable, and diffing a `metrics.json` across 200 commits is a research
superpower while diffing an MP4 is meaningless.

**Not a claim that EML works.** The default position is that it does not,
except in the two places the corpus actually supports. If that changes it will
be because a falsifier failed to fire, with provenance attached.

**Not a benchmark suite.** No leaderboards. Comparisons are made against a
stated null model, per experiment, and reported as deltas with seed counts.

**Not Microsoft work.** This is personal research on public arXiv papers and
open-source code. No corporate identifiers, internal URLs, tenant GUIDs or
proprietary data — enforced by `security/scan.py` and five layers of hooks and
CI.

---

## Deliberately deferred

Not out of scope forever, just not now. Listed so they are not silently
forgotten:

| Item | Why deferred |
|---|---|
| EDL and −EML variants | one operator at a time; EML is the documented one |
| Stachowiak's generalized `M(u,w) = φ⁻¹(φ(u) − φ(w))` family search | needs Rung 2 to show the approach works at all first |
| Ternary Sheffer operator | Odrzywołek's follow-up is unpublished |
| GPU acceleration | premature until an experiment is compute-bound |
| Multi-agent parallel threads | the registry supports it; no need yet |

---

## How to change this file

Widening scope requires: a thread with a falsifier, an entry in `CHANGELOG.md`,
and a reason recorded in the journal. Scope that widens silently is scope creep
by another name.
