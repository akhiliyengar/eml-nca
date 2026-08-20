# Rung 1: EML/SOL cannot recover the Gray-Scott cross term

thread: `t1-grayscott`
status: **hypothesis falsified** — as predicted
run: `results/t1-grayscott/29f0ef806f8c.metrics.json`

## Expected

That it would fail. Asanuma (arXiv:2606.05942) reports the univariate-additive
EML form "cannot represent cross-variable interactions", and the target
`-u·v² + F(1-u)` contains exactly that. Rung 1 was chosen *because* it was the
least likely to succeed: it costs a day, provides a real control, and
calibrates what failure looks like here before a month is spent elsewhere.

## Observed

Fit on `v ∈ [0, 0.35]`, extrapolate to `v ∈ [0.35, 0.5]`, n=3000, seed=0.

| arm | atoms | fit relMSE | extrap relMSE | ratio |
|---|---:|---:|---:|---:|
| poly_control | 10 | **9.96e-31** | **2.03e-31** | 0.2× |
| eml_only | 61 | 1.25e-02 | 3.97e-02 | 3.2× |
| sol_only | 67 | 1.34e-02 | 5.41e-02 | 4.0× |
| eml_sol | 120 | 1.09e-02 | 4.61e-02 | 4.2× |
| eml_sol_poly | 126 | 5.61e-06 | 6.20e-07 | 0.1× |

**Falsifier fired**: EML/SOL is **2.27e+29×** worse than the exact basis.

Three details matter more than the headline:

1. **Adding EML to SOL barely moved anything** — 1.34e-02 → 1.09e-02. In an
   earlier run on the un-split domain the two were *identical to the last
   digit*, meaning EML atoms contributed literally nothing.
2. **Given a mixed basis, the search chose the polynomial.** `eml_sol_poly`
   selected `u^1v^2` with coefficient −0.9999 over all 120 EML/SOL
   alternatives. Offered the exact term, it takes it.
3. **EML/SOL degrades gracefully, it does not explode.** The extrapolation
   ratio is 3–4×, comfortably inside the 10× guard. This is a *smooth
   approximation that is uniformly mediocre*, not an overfit that blows up —
   a meaningfully different failure, and a milder one than I expected.

## Interpretation

EML/SOL **approximates** the reaction term (relMSE ~1e-2) but does not
**recover** it. Those are different claims and the distinction is the whole
finding.

**This nearly went the other way.** My original falsifier was "relMSE > 0.01 on
the fitted domain". The first run scored 8.2e-03 and printed
*"HYPOTHESIS SUPPORTED"* — a result I would have been entitled to report. It was
wrong, because on a smooth bounded target almost any rich basis clears 1e-2. The
threshold measured basis richness, not recovery.

Two changes fixed it, and both should be defaults from now on:

- **Extrapolate.** Fit on one band, evaluate on another. A recovered *form*
  holds; an approximation drifts.
- **Ratio against a control that contains the answer.** "Small error" means
  nothing absolute. 1e-2 sounds fine until the exact basis reaches 1e-31.

**What this does NOT mean.** It says nothing about Rung 2. Lenia's growth
function is *univariate* and non-monotone — precisely the shape Erez's gate
produces natively, and precisely not the shape that failed here. Rung 1 tested
cross-variable interaction; Rung 2 does not involve any.

It also does not show EML is useless. It confirms one documented limitation, in
the one place it was predicted to appear.

## Bugs found

Three, all caught by controls rather than by the experiment:

- **The intercept was silently deleted.** The constant atom has zero variance
  by definition, so the generic "reject near-constant atoms" filter removed it,
  and every fit then had to approximate `F` with slope terms. Caught by the
  polynomial control failing at 1.8e-02 when it should have been exact.
- **`inf` extrapolation was a harness artifact.** Rebuilding the library on the
  held-out band produced *different atoms* — dedup is data-dependent — so
  fitted names were absent. The true error was 3.99e-04, finite and
  unremarkable. Atoms now carry their generating function and are re-evaluated.
- **`WARN` was rendered as `INVARIANT FAILURE`.** A dirty tree is a recorded
  gap, not a violation; conflating them trains people to ignore the header.

## Next

**Rung 2, `t2-lenia-gate`** — highest prior in the spec.

Carry forward, as defaults rather than options:
1. extrapolation split on every fit
2. control ratio, never absolute error
3. a null model in every arm table (Gaussian growth is Rung 2's control)

Before that, the three.js viewer: Rung 2's outcome is *"does Orbium survive"*,
which is far easier to judge by watching than by reading a scalar.
