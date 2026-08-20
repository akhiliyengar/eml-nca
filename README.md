# eml-nca

**Can the EML operator family do anything useful for Neural Cellular Automata?**

A comparative study. The working hypothesis is deliberately falsifiable, and the
repository is built so that a negative result is a publishable outcome rather
than a wasted month.

---

## Background

Odrzywołek ([arXiv:2603.21852](https://arxiv.org/abs/2603.21852)) showed that a
single binary operator

$$\mathrm{eml}(x, y) = e^{x} - \ln(y)$$

together with the constant `1` generates every standard elementary function — a
continuous analogue of the NAND gate. Seven papers have since cited it.

Reading all seven in full produced a sceptical summary:

| Claim | Evidence |
|---|---|
| EML gives symbolic interpretability | ✗ Germany et al. report **0/42** parameters snapping to symbolic form at depth 3 |
| EML is uniquely expressive | ✗ Erez shows a Hill grammar **ties** at depth 2 |
| EML is practical as-is | ✗ every adopter added parameters, gates, clipping, or a second primitive |
| EML wins as a reusable hardware gate | ✓ Günlü — one analog gate type per tree node |
| EML wins on depth-1 parsimony | ✓ Erez — 3-parameter non-monotone block, ΔAIC 277–373 |

This repo tests whether the two genuine wins transfer to NCA.

## Hypotheses

**H1 — parameter efficiency.** An EML forest matches Growing-NCA morphogenesis
with ≤300 parameters versus ~8,000 in the standard MLP update rule.

**H2 — long-horizon stability.** A symbolic rule is more stable over 10,000+
steps than an MLP, which is known to be fragile beyond its trained step count.

**H3 — analytic stability prediction.** Because an EML tree yields an exact
closed-form Jacobian, the spectral radius ρ(J) *predicts* which patterns
persist. This is not available from a ReLU MLP, whose function is
non-identifiable from its weights.

**H4 — symbolic recovery.** Prior probability low, per the evidence above.
Reported as a negative result if it fails.

## The central hazard

NCA applies its update rule thousands of times recursively. EML contains `exp`.
Günlü's error analysis gives per-node sensitivity `e^b`, compounding along the
path to the root.

At gain 1.05 over 100 steps: **131×**. At 0.95: **0.006**. There is almost no
middle ground.

Every experiment therefore instruments `GainTrace` from the first run, and only
`eml_stable` (softplus-guarded) is permitted inside an iterated loop.

## Experiment ladder

| Rung | Target | Why | Ground truth |
|---|---|---|---|
| 1 | Gray–Scott reaction–diffusion | tests cross-variable interaction `uv²`, EML's known weakness | exact |
| 2 | **Lenia growth function** | univariate, non-monotone — Erez's gate maps directly onto it | Gaussian baseline |
| 3 | Full NCA update rule | the real target | none |
| 4 | Jacobian spectral analysis | H3 | — |

Rung 2 is the highest-probability win.

## Quick start

```bash
git clone https://github.com/akhiliyengar/eml-nca.git
cd eml-nca
python -m venv .venv && . .venv/Scripts/activate   # or .venv/bin/activate
pip install -e ".[dev]"
python scripts/setup_hooks.py      # REQUIRED: activates security hooks
pytest -q
```

## Layout

```
src/emlnca/       ops (eml / eml_admissible / eml_stable, SOL, Erez gate)
                  stability (GainTrace, spectral radius, Jacobians)
                  identities (published claims as executable spec)
tests/            identities, invariants, security
security/         zero-dependency secret + identifier scanner
.githooks/        pre-commit, commit-msg, pre-push
experiments/      rung1_grayscott, rung2_lenia, rung3_nca
viz/three/        interactive WebGL viewer
viz/manim/        concept explainers
results/          metrics.json per run (artifacts are NOT committed)
```

## Automation policy

Three tiers, on different triggers. Time-based ML runs are cargo-culted from web
CI: re-running identical code on a schedule produces notifications that get
filtered to a folder nobody opens.

| Tier | Trigger | Budget | Blocking |
|---|---|---|---|
| **Guard** | push / PR | < 60 s | yes |
| **Sweep** | manual + weekly | ~20 min | no |
| **Deep** | manual, local/Colab GPU | hours | no |

The weekly run exists to catch **dependency** drift (a numpy release changing a
reduction order), not code drift.

### Invariants hard-fail; metrics never do

The single most important policy here.

| | Invariants — **BLOCK** | Metrics — **report only** |
|---|---|---|
| Examples | NaN/inf; non-determinism under a fixed seed; gain outside [0.5, 1.5]; a published identity breaking; a security finding | Orbium lifetime; accuracy; parameter count; recovery rate |
| Rationale | always a bug — no legitimate research reason to break them | *should* move; movement is the finding |

In software a falling metric is a regression. **In research it is often the
result.** Hard-failing CI on metric movement teaches you to add
`continue-on-error: true`, and then the safety net is gone. Metrics are posted
as a delta table on the PR; a human decides.

## Security

This repo is public and developed on a corporate machine. Five layers guard
against accidental disclosure — commit identity, message, staged content, push
range, and CI. See [SECURITY.md](SECURITY.md).

Hooks are not transferred by `git clone`. **Run `python scripts/setup_hooks.py`
after cloning.**

## References

| | |
|---|---|
| Odrzywołek 2026 | [2603.21852](https://arxiv.org/abs/2603.21852) — the EML operator |
| Stachowiak 2026 | [2604.23893](https://arxiv.org/abs/2604.23893) — algebraic structure |
| Belaiche 2026 | [2605.08130](https://arxiv.org/abs/2605.08130) — SOL, additive forests |
| Erez 2026 | [2605.02972](https://arxiv.org/abs/2605.02972) — non-monotone gate |
| Asanuma 2026 | [2606.05942](https://arxiv.org/abs/2606.05942) — causal mechanisms |
| Germany et al. 2026 | [2606.23179](https://arxiv.org/abs/2606.23179) — universal approximation |
| Günlü 2026 | [2607.16360](https://arxiv.org/abs/2607.16360) — AirComp gate |
| Mordvintsev et al. 2020 | [Growing NCA](https://distill.pub/2020/growing-ca/) |
| Chan 2019 | [Lenia](https://github.com/Chakazul/Lenia) |

## Licence

MIT
