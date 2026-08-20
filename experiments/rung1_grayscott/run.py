#!/usr/bin/env python3
"""Rung 1: can an EML/SOL forest recover the Gray-Scott reaction term?

    target = -u*v^2 + F*(1 - u)

Thread    : t1-grayscott
Hypothesis: an EML/SOL forest can recover the u*v^2 cross term
Falsifier : (revised -- see below)

Deliberately the experiment least likely to succeed. Asanuma
(arXiv:2606.05942) documents that the univariate-additive EML form "cannot
represent cross-variable interactions", and u*v^2 is exactly that.

FALSIFIER REVISION
------------------
The original falsifier was "relMSE > 0.01 on the fitted domain". A first run
passed it at 8.2e-03 and would have been recorded as SUPPORTED. That reading
was wrong, and the criterion was the problem:

  * the polynomial control reached 2.4e-31 -- the EML/SOL result was ~28 orders
    of magnitude worse yet still under the threshold
  * eml_sol scored IDENTICALLY to sol_only, to the last digit, so EML atoms
    contributed nothing at all
  * given a mixed basis, the search selected -0.9999*u^1v^2, the polynomial atom

Any sufficiently rich smooth basis fits a smooth target on a bounded domain.
That is approximation, not recovery. The revised criterion has two parts:

  1. EXTRAPOLATION. Fit on v in [0, 0.35], evaluate on v in [0.35, 0.5]. A
     recovered form holds; an approximation diverges.
  2. CONTROL RATIO. Error must stay within 1e6 of the control, which contains
     u*v^2 exactly.

Recorded rather than silently rewritten. A falsifier relaxed after seeing the
data is worthless, and one tightened after seeing the data is no better unless
the reason is on the record.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from harness.provenance import Provenance, sha256_obj
from harness.record import RunRecord

from emlnca.forest import build_library, search
from emlnca.grayscott import GrayScott, split_domain

EXTRAP_BLOWUP = 10.0      # test/fit error ratio above which a fit is local only
CONTROL_RATIO = 1e6       # allowed slack against the exact-basis control
THREAD = "t1-grayscott"

ARMS: dict[str, tuple[str, ...]] = {
    "poly_control": ("poly",),
    "eml_only": ("eml",),
    "sol_only": ("sol",),
    "eml_sol": ("eml", "sol"),
    "eml_sol_poly": ("eml", "sol", "poly"),
}


def rel_mse(pred: np.ndarray, target: np.ndarray) -> float:
    return float(np.mean((pred - target) ** 2) / (np.mean(target**2) or 1.0))


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--samples", type=int, default=3000)
    ap.add_argument("--max-terms", type=int, default=3)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--no-write", action="store_true")
    args = ap.parse_args()

    config = {
        "experiment": "rung1_grayscott", "samples": args.samples,
        "max_terms": args.max_terms, "seed": args.seed,
        "F": 0.035, "k": 0.065, "v_cut": 0.35,
        "arms": {k: list(v) for k, v in ARMS.items()},
        "criterion": "extrapolation + control ratio",
    }
    prov = Provenance(thread=THREAD, seed=args.seed, config_path="inline",
                      config_sha256=sha256_obj(config))
    rec = RunRecord(provenance=prov)

    gs = GrayScott(F=config["F"], k=config["k"])
    (uf, vf), (ut, vt) = split_domain(n=args.samples, seed=args.seed,
                                      v_cut=config["v_cut"])
    y_fit, y_test = gs.reaction_u(uf, vf), gs.reaction_u(ut, vt)

    rec.check_finite("target", [float(np.max(np.abs(y_fit)))])
    rec.check_reproducible(strict=False)

    print(f"Rung 1 -- target: -u*v^2 + {gs.F}*(1 - u)")
    print(f"fit on v<{config['v_cut']}, extrapolate to v>{config['v_cut']}  "
          f"n={args.samples} terms<={args.max_terms} seed={args.seed}\n")
    print(f"{'arm':<15} {'atoms':>5} {'fit relMSE':>12} {'extrap relMSE':>14} "
          f"{'ratio':>10}  verdict")
    print("-" * 90)

    results: dict[str, dict] = {}
    for arm, families in ARMS.items():
        atoms = build_library(uf, vf, families=families)
        fit = search(atoms, y_fit, max_terms=args.max_terms)

        # Re-evaluate the FITTED atoms on the held-out band.
        #
        # Rebuilding the library there is NOT equivalent: dedup is
        # data-dependent, so a different set of atoms survives and a fitted
        # name can be absent entirely. An earlier version did that and reported
        # extrapolation as `inf`, overstating a real failure with a harness
        # artifact -- the true error was 3.99e-04, finite and unremarkable.
        by_name = {a.name: a for a in atoms}
        pred = sum(c * by_name[n].evaluate(ut, vt)
                   for c, n in zip(fit.coeffs, fit.atoms))
        extrap = rel_mse(pred, y_test)

        ratio = extrap / max(fit.rel_mse, 1e-300)
        results[arm] = {"n_atoms": len(atoms), "fit": fit.rel_mse,
                        "extrap": extrap, "ratio": ratio,
                        "formula": fit.formula(), "terms": fit.atoms}
        for key, val in (("fit_rel_mse", fit.rel_mse),
                         ("extrap_rel_mse", extrap),
                         ("extrap_ratio", ratio),
                         ("n_atoms", len(atoms))):
            rec.record(f"{arm}.{key}", val)

        verdict = "local fit" if ratio > EXTRAP_BLOWUP else "generalises"
        print(f"{arm:<15} {len(atoms):>5} {fit.rel_mse:>12.3e} "
              f"{extrap:>14.3e} {ratio:>9.1f}x  {verdict}")

    ctrl = results["poly_control"]
    both = results["eml_sol"]
    eml = results["eml_only"]
    print()
    if ctrl["extrap"] > 1e-10:
        print(f"CONTROL FAILED (extrap={ctrl['extrap']:.2e}). The polynomial "
              f"basis contains u*v^2 exactly and must extrapolate perfectly.")
        print("The harness is broken; no conclusion about EML follows.")
        return 1
    print(f"control OK: fit={ctrl['fit']:.2e} extrap={ctrl['extrap']:.2e} "
          f"-- an exact basis extrapolates without degrading")

    control_ratio = both["extrap"] / max(ctrl["extrap"], 1e-300)
    recovered = (both["ratio"] <= EXTRAP_BLOWUP
                 and control_ratio <= CONTROL_RATIO)
    rec.record("verdict.recovered", recovered)
    rec.record("verdict.control_ratio", control_ratio)

    print()
    if recovered:
        print(f"HYPOTHESIS SUPPORTED: EML/SOL extrapolates "
              f"({both['ratio']:.1f}x) and is within {control_ratio:.1e} of "
              f"the control")
    else:
        print("FALSIFIER FIRED -- the hypothesis is rejected.")
        print(f"  eml_sol extrapolation blow-up : {both['ratio']:.1f}x "
              f"(limit {EXTRAP_BLOWUP})")
        print(f"  worse than exact control by   : {control_ratio:.2e}x "
              f"(limit {CONTROL_RATIO:.0e})")
        print(f"  eml alone extrapolates at     : {eml['ratio']:.1f}x")
        if abs(both["fit"] - results["sol_only"]["fit"]) < 1e-15:
            print("  NOTE: eml_sol == sol_only to machine precision, so EML "
                  "atoms contributed nothing.")
        if any("v^2" in t for t in results["eml_sol_poly"]["terms"]):
            print("  NOTE: given a mixed basis the search chose the POLYNOMIAL "
                  "u*v^2 atom over every EML/SOL alternative.")
        print()
        print("  This is the predicted outcome. Asanuma reports the "
              "univariate-additive")
        print("  EML form cannot represent cross-variable interactions, and "
              "u*v^2 is exactly that.")

    if not args.no_write:
        path = rec.write()
        print(f"\nwrote {path.relative_to(Path(__file__).resolve().parents[2])}")
    print()
    print(rec.summary())
    return 0


if __name__ == "__main__":
    sys.exit(main())
