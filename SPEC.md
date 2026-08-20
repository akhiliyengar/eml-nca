# SPEC

What this repository is trying to find out, and what would count as an answer.

Status legend: ○ proposed · ● active · ◌ parked · ◆ converged · ✗ abandoned

---

## 1. Question

> Does the EML operator family (`eml(x,y) = eˣ − ln y`, arXiv:2603.21852)
> provide any measurable advantage for Neural Cellular Automata over the
> standard MLP update rule?

**Default answer: no.** The burden of evidence is on the affirmative. This is
deliberate — seven papers cite EML and most of their claims weaken under
inspection.

## 2. Prior evidence

From reading all seven citing papers in full:

| Claim | Verdict | Evidence |
|---|---|---|
| EML gives symbolic interpretability | **contradicted** | Germany et al. §3.4: 0/42 parameters snap; 0 fully-discrete atoms across 5 targets |
| EML is uniquely expressive | **contradicted** | Erez: Hill grammar ties at depth 2 with fewer static params |
| EML is practical unmodified | **contradicted** | every adopter added parameters, gates, clipping, or a second primitive |
| Universal approximation holds | **narrower** | proved for the 6-param generalized atom; vanilla is stated open |
| EML wins as a reusable hardware gate | **supported** | Günlü: exactly nomographic, ψ = identity, one gate type per node |
| EML wins on depth-1 parsimony | **supported** | Erez: 3-param non-monotone block, ΔAIC 277–373 vs Hill at depth 1 |

**Only the last two transfer to NCA.** This spec tests those.

## 3. Hypotheses

Each has a falsifier. A hypothesis without one is not in this spec.

### H1 — parameter efficiency ○
> An EML forest matches Growing-NCA morphogenesis using ≤ 300 parameters,
> versus ~8,000 in the standard `Dense(48→128) → ReLU → Dense(128→16)` rule.

**Falsifier:** no configuration under 300 params reaches comparable
morphogenesis across 3 seeds.
**Thread:** `t3-nca-forest` · **Prior:** moderate

### H2 — long-horizon stability ○
> A symbolic EML rule drifts less than an MLP over 10,000+ steps.

**Falsifier:** EML drift ≥ MLP drift at 10k steps across 3 seeds.
**Thread:** `t3-nca-forest` · **Prior:** moderate — NCA fragility beyond its
trained step count is documented but rarely measured, so this is undertested
rather than unlikely.

### H3 — analytic stability prediction ○
> ρ(J) computed from the exact closed-form Jacobian predicts which patterns
> persist.

**Falsifier:** no correlation between ρ(J) and observed survival.
**Thread:** `t4-spectral` · **Prior:** moderate. **Most novel** — currently
unanswerable for MLP-based NCA because the function is non-identifiable from
the weights (Waxman et al.).

### H4 — symbolic recovery ○
> Trained EML weights snap to exact symbolic values, yielding a readable rule.

**Falsifier:** < 10% of parameters snap within 30% loss tolerance.
**Thread:** `t5-symbolic-recovery` · **Prior:** **low.** Registered because it
is EML's headline claim and a second independent negative is publishable.

### H5 — non-monotone parsimony in Lenia ○
> Erez's 3-param gate replaces Lenia's Gaussian growth function and sustains
> Orbium.

**Falsifier:** Orbium dies before 1,000 steps for all (a,b,c) swept.
**Thread:** `t2-lenia-gate` · **Prior:** **highest.** Lenia's growth function is
univariate and non-monotone, exactly the shape Erez's gate produces natively.

## 4. The central hazard

NCA applies its rule thousands of times recursively. EML contains `exp`.
Günlü's per-node sensitivity is `e^b`, compounding along the path to the root.

| per-step gain | after 100 steps |
|---|---|
| 1.05 | **131×** |
| 0.95 | **0.006** |

There is almost no middle ground. Consequences, binding on all experiments:

- only `eml_stable` (softplus-guarded) may appear inside an iterated loop
- `GainTrace` is instrumented from run one, never retrofitted after a failure
- gain outside 10⁻³–10³ is a **catastrophe guard** — structural breakage, not a
  finding

## 5. Experiment ladder

| Rung | Target | Tests | Ground truth | Thread |
|---|---|---|---|---|
| 1 | Gray–Scott reaction–diffusion | cross-variable `uv²`, EML's known weakness | exact closed form | `t1-grayscott` |
| 2 | **Lenia growth function** | H5 | Gaussian baseline | `t2-lenia-gate` |
| 3 | Full NCA update rule | H1, H2, H4 | none | `t3-nca-forest` |
| 4 | Spectral analysis | H3 | — | `t4-spectral` |

Climb in order. Rung 1 is a **control** — it targets EML's documented weakness,
so a clean negative there is informative and cheap.

## 6. Success criteria

The project succeeds if it produces a **defensible answer**, not a positive one.

| Outcome | Counts as success |
|---|---|
| H1/H2/H3 supported with provenance and baselines | ✅ |
| All hypotheses falsified, documented, reproducible | ✅ |
| Positive result that does not reproduce across seeds | ❌ |
| Positive result with no baseline comparison | ❌ |

## 7. Explicit non-goals

See `docs/SCOPE.md`.

## 8. Reproducibility contract

Every reported number carries: **seed · git SHA · config SHA-256 · environment
versions**. `harness/provenance.py` refuses to record a run it cannot fully
describe, and reports "dirty tree" as a reproducibility gap rather than
silently implying rigour.

---

## Current threads

<!-- BEGIN:THREADS -->
| id | status | hypothesis | parent | verdict |
|---|---|---|---|---|
| `t0-foundation` | ● active | EML primitives can be implemented safely enough to iterate thousands of times | - | supported: eml_stable survives 5k steps x 256 starts |
| `t1-grayscott` | ○ proposed | An EML/SOL forest can recover the uv^2 cross term of Gray-Scott | t0-foundation | _open_ |
| `t2-lenia-gate` | ○ proposed | Erez's 3-param gate can replace Lenia's Gaussian growth function and sustain Orbium | t0-foundation | _open_ |
| `t3-nca-forest` | ○ proposed | An EML forest with a linear perception projection matches Growing-NCA at <= 300 params vs ~8000 | t2-lenia-gate | _open_ |
| `t4-spectral` | ○ proposed | rho(J) from the analytic Jacobian predicts which NCA patterns persist | t3-nca-forest | _open_ |
| `t5-symbolic-recovery` | ○ proposed | Trained EML weights snap to exact symbolic values, recovering a readable rule | t3-nca-forest | _open_ |
<!-- END:THREADS -->

## Corpus

<!-- BEGIN:LITERATURE -->
| # | date | paper | role |
|---|---|---|---|
| 0 | 2026-03 | [All elementary functions from a single operator](https://arxiv.org/abs/2603.21852) | SOURCE. Defines eml(x,y)=exp(x)-ln(y). Reports blind symbolic recovery collapsing to 0/448 at depth 6. |
| 1 | 2026-04 | [Algebraic structure behind Odrzywolek's EML operator](https://arxiv.org/abs/2604.23893) | Shows EML is one member of a classifiable family; the depth-7 ln tree is structural, not logarithmic. Missed by Semantic Scholar; found via Belaiche's reference list. |
| 2 | 2026-04 | [Auto-Relational Reasoning](https://arxiv.org/abs/2604.26507) | Weakest link: cites EML in one sentence as justification, implements none of it. No code. |
| 3 | 2026-05 | [Additive Atomic Forests for Symbolic Function and Antiderivative Discovery](https://arxiv.org/abs/2605.08130) | Adds SOL = sin(u)-cos(v) because trig costs depth ~8 in EML. Strong empirical claims, no code released. |
| 4 | 2026-05 | [Non-Monotone Response Modules and Cascades from the EML Operator](https://arxiv.org/abs/2605.02972) | MOST DIRECTLY USEFUL. 3-parameter non-monotone gate; ran the fair Hill comparison and reported the tie at depth 2. Ships code. |
| 5 | 2026-06 | [EML-CD: Causal Mechanism Recovery via EML Symbolic Trees](https://arxiv.org/abs/2606.05942) | Analytic Jacobians as the selling point. Documents that exp clipping is 'load-bearing rather than cosmetic'. |
| 6 | 2026-06 | [EML Trees Are Universal Approximators](https://arxiv.org/abs/2606.23179) | CRITICAL NEGATIVE RESULT: 0/42 parameters snap to symbolic form. Theorem covers the 6-param generalized atom, not vanilla EML. |
| 7 | 2026-07 | [EML-AirComp: Layered Over-the-Air Computation from a Single Nomographic Gate](https://arxiv.org/abs/2607.16360) | The clean win. EML is exactly nomographic, so one analog gate type serves every tree node. Sidesteps complex domain via real-admissible trees. |
| 8 | 2020-02 | [Growing Neural Cellular Automata](https://arxiv.org/abs/None) | TARGET SYSTEM. ~8k-parameter MLP update rule; the thing an EML forest would replace. |
<!-- END:LITERATURE -->
