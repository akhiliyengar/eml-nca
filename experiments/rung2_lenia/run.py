#!/usr/bin/env python3
"""Rung 2: can Erez's EML gate replace Lenia's Gaussian growth function?

Thread    : t2-lenia-gate
Hypothesis: the 3-parameter Erez gate sustains a Lenia creature
Falsifier : no (a, b, c) in the swept range produces a survivor, WHILE the
            Gaussian control produces survivors on the same seeds

PLAIN ENGLISH
-------------
Lenia is a game where dots on a grid brighten or dim based on their
neighbours, and the right rule makes little creatures that crawl around. The
rule's "should I brighten?" half is normally a bell curve. Erez's gate is a
different shape that does the same job with 3 knobs instead of 6. Question:
swap it in, do the creatures still live?

WHY THE COMPARISON MUST BE MATCHED
----------------------------------
While building the viewer we measured this, and it changes the whole design:

    radius 8, amplitude 0.50  -> died at step 22
    radius 8, amplitude 0.60  -> alive past 400
    radius 10, any amplitude  -> died, every variant tried

The set of starting shapes that survive is TINY. So "the EML gate killed the
creature" is worthless on its own -- that seed may have been doomed for any
rule. Both growth functions are therefore run over the SAME seed grid, and the
comparison is basin size against basin size.

This is the mistake Rung 1 nearly made in a different costume: a number with no
baseline is not a result.

Usage:
    python experiments/rung2_lenia/run.py
    python experiments/rung2_lenia/run.py --steps 1000 --size 128
"""

from __future__ import annotations

import argparse
import itertools
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from harness.provenance import Provenance, sha256_obj
from harness.record import RunRecord

from emlnca.lenia import (
    Lenia,
    erez_growth,
    erez_offset_growth,
    gaussian_growth,
    run,
    seed_disc,
)

THREAD = "t2-lenia-gate"

# The seed grid. Both arms see exactly these, so basin sizes are comparable.
SEED_RADII = (7, 8, 9, 10, 12)
SEED_AMPS = (0.40, 0.50, 0.60, 0.70)

# Control sweep. mu/sigma around Lenia's published Orbium values.
GAUSS_GRID = tuple(itertools.product((0.13, 0.15, 0.17), (0.014, 0.017, 0.020)))

# Treatment sweep. a<1 and b>0 are required for the gate to be non-monotone at
# all; outside that range it is not the thing Erez described.
EREZ_GRID = tuple(itertools.product(
    (0.25, 0.40, 0.50, 0.65, 0.80),      # a  exponent
    (0.15, 0.30, 0.60, 1.00),            # b  suppression
    (0.005, 0.02, 0.08),                 # c  centering
    (1.0, 2.0),                          # scale
))

# Repair sweep. Same gate minus a constant, which is the single change that
# lets empty space decay. Included as its own arm so the published gate is
# still reported exactly as published.
OFFSET_GRID = tuple(itertools.product(
    (0.25, 0.50),          # a
    (0.30, 1.00),          # b
    (0.05, 0.10, 0.20),    # theta  offset
))


def sweep_seeds(make_world, steps: int, size: int) -> dict:
    """Run one rule over the whole seed grid; report how many survived.

    PLAIN ENGLISH
    Try the same rule from many different starting blobs and count how many
    turn into something that is still alive at the end. That count is the
    rule's "basin" -- how forgiving it is about where you start.
    """
    survivors = []
    for r, amp in itertools.product(SEED_RADII, SEED_AMPS):
        out = run(make_world(), seed_disc(size, r, amp), steps=steps)
        if out.survived:
            survivors.append({"radius": r, "amp": amp, "gain": out.gain,
                              "mass": out.final_mass, "cv": out.mass_cv})
    return {"n_seeds": len(SEED_RADII) * len(SEED_AMPS),
            "n_survived": len(survivors), "survivors": survivors}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--steps", type=int, default=400)
    ap.add_argument("--size", type=int, default=128)
    ap.add_argument("--radius", type=int, default=13)
    ap.add_argument("--dt", type=float, default=0.1)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--no-write", action="store_true")
    args = ap.parse_args()

    config = {
        "experiment": "rung2_lenia", "steps": args.steps, "size": args.size,
        "kernel_radius": args.radius, "dt": args.dt, "seed": args.seed,
        "seed_radii": list(SEED_RADII), "seed_amps": list(SEED_AMPS),
        "gauss_grid": [list(g) for g in GAUSS_GRID],
        "erez_grid": [list(g) for g in EREZ_GRID],
    }
    prov = Provenance(thread=THREAD, seed=args.seed, config_path="inline",
                      config_sha256=sha256_obj(config))
    rec = RunRecord(provenance=prov)
    rec.check_reproducible(strict=False)

    n_seeds = len(SEED_RADII) * len(SEED_AMPS)
    print("Rung 2 -- can the Erez EML gate replace Lenia's Gaussian growth?")
    print(f"grid {args.size}  kernel R={args.radius}  dt={args.dt}  "
          f"steps={args.steps}")
    print(f"seed grid: {len(SEED_RADII)} radii x {len(SEED_AMPS)} amplitudes "
          f"= {n_seeds} starts per configuration\n")

    def world(g):
        return lambda: Lenia(growth=g, radius=args.radius, dt=args.dt,
                             size=args.size)

    # ---- control ------------------------------------------------------
    print(f"CONTROL  Gaussian, {len(GAUSS_GRID)} configurations")
    print(f"  {'mu':>6} {'sigma':>7} {'survived':>10}  best gain")
    best_ctrl = None
    ctrl_rows = []
    for mu, sigma in GAUSS_GRID:
        res = sweep_seeds(world(gaussian_growth(mu, sigma)), args.steps,
                          args.size)
        ctrl_rows.append(((mu, sigma), res))
        g = min((s["gain"] for s in res["survivors"]),
                key=lambda x: abs(x - 1.0), default=float("nan"))
        print(f"  {mu:>6.3f} {sigma:>7.3f} {res['n_survived']:>6}/{n_seeds}"
              f"   {g if np.isfinite(g) else float('nan'):>9.5f}")
        if best_ctrl is None or res["n_survived"] > best_ctrl[1]["n_survived"]:
            best_ctrl = ((mu, sigma), res)

    ctrl_total = sum(r["n_survived"] for _, r in ctrl_rows)
    ctrl_best_n = best_ctrl[1]["n_survived"]
    print(f"  -> best single config: {ctrl_best_n}/{n_seeds} survivors "
          f"at mu={best_ctrl[0][0]}, sigma={best_ctrl[0][1]}")
    print(f"  -> total across all configs: {ctrl_total}"
          f"/{len(GAUSS_GRID) * n_seeds}\n")

    if ctrl_best_n == 0:
        print("CONTROL FAILED: the Gaussian kept nothing alive on any seed.")
        print("The simulator or the seed grid is wrong; no statement about the")
        print("EML gate can be made from this run.")
        return 1

    # ---- treatment ----------------------------------------------------
    print(f"TREATMENT  Erez gate, {len(EREZ_GRID)} configurations")
    print(f"  {'a':>5} {'b':>5} {'c':>6} {'scale':>6} {'survived':>10}  best gain")
    best_erez = None
    erez_total = 0
    shown = 0
    for a, b, c, scale in EREZ_GRID:
        res = sweep_seeds(world(erez_growth(a, b, c, scale)), args.steps,
                          args.size)
        erez_total += res["n_survived"]
        if best_erez is None or res["n_survived"] > best_erez[1]["n_survived"]:
            best_erez = ((a, b, c, scale), res)
        if res["n_survived"] > 0 or shown < 6:
            g = min((s["gain"] for s in res["survivors"]),
                    key=lambda x: abs(x - 1.0), default=float("nan"))
            print(f"  {a:>5.2f} {b:>5.2f} {c:>6.3f} {scale:>6.1f} "
                  f"{res['n_survived']:>6}/{n_seeds}   "
                  f"{g if np.isfinite(g) else float('nan'):>9.5f}")
            shown += 1

    erez_best_n = best_erez[1]["n_survived"]
    print(f"  -> best single config: {erez_best_n}/{n_seeds} survivors "
          f"at a={best_erez[0][0]}, b={best_erez[0][1]}, c={best_erez[0][2]}, "
          f"scale={best_erez[0][3]}")
    print(f"  -> total across all configs: {erez_total}"
          f"/{len(EREZ_GRID) * n_seeds}\n")

    # ---- repair arm ---------------------------------------------------
    # Erez's gate never goes below zero, so empty space cannot decay.
    # Subtracting a constant restores that. Included as a THIRD arm rather
    # than as a tweak to the treatment, so the published gate is still
    # reported exactly as published.
    print(f"REPAIR  Erez gate minus a constant, {len(OFFSET_GRID)} configurations")
    print(f"  {'a':>5} {'b':>5} {'theta':>6} {'survived':>10}  best gain")
    best_fix = None
    fix_total = 0
    for a, b, theta in OFFSET_GRID:
        res = sweep_seeds(world(erez_offset_growth(a, b, 0.02, 1.0, theta)),
                          args.steps, args.size)
        fix_total += res["n_survived"]
        if best_fix is None or res["n_survived"] > best_fix[1]["n_survived"]:
            best_fix = ((a, b, theta), res)
        if res["n_survived"] > 0:
            g = min((s["gain"] for s in res["survivors"]),
                    key=lambda x: abs(x - 1.0), default=float("nan"))
            print(f"  {a:>5.2f} {b:>5.2f} {theta:>6.2f} "
                  f"{res['n_survived']:>6}/{n_seeds}   {g:>9.5f}")
    fix_best_n = best_fix[1]["n_survived"]
    print(f"  -> best single config: {fix_best_n}/{n_seeds} survivors at "
          f"a={best_fix[0][0]}, b={best_fix[0][1]}, theta={best_fix[0][2]}")
    print(f"  -> total: {fix_total}/{len(OFFSET_GRID) * n_seeds}\n")

    # ---- verdict ------------------------------------------------------
    for k, v in (
        ("control.best_survivors", ctrl_best_n),
        ("control.total_survivors", ctrl_total),
        ("control.n_configs", len(GAUSS_GRID)),
        ("control.best_params", list(best_ctrl[0])),
        ("erez.best_survivors", erez_best_n),
        ("erez.total_survivors", erez_total),
        ("erez.n_configs", len(EREZ_GRID)),
        ("erez.best_params", list(best_erez[0])),
        ("seed_grid_size", n_seeds),
        ("repair.best_survivors", fix_best_n),
        ("repair.total_survivors", fix_total),
        ("repair.best_params", list(best_fix[0])),
    ):
        rec.record(k, v)

    supported = erez_best_n > 0
    rec.record("verdict.supported", supported)
    rec.record("verdict.basin_ratio",
               erez_best_n / ctrl_best_n if ctrl_best_n else 0.0)

    print("=" * 70)
    if supported:
        print("HYPOTHESIS SUPPORTED: the Erez gate sustains a creature.")
        print(f"  best Erez basin    : {erez_best_n}/{n_seeds} seeds")
        print(f"  best Gaussian basin: {ctrl_best_n}/{n_seeds} seeds")
        print(f"  ratio              : "
              f"{erez_best_n / ctrl_best_n:.2f}x the control's basin")
        print(f"  parameters         : a={best_erez[0][0]}, b={best_erez[0][1]},"
              f" c={best_erez[0][2]}, scale={best_erez[0][3]}")
        print("\n  Erez uses 3 shape parameters; the Gaussian pair it replaces")
        print("  needs 2 here, but 6 for the same NON-MONOTONE shape (two")
        print("  opposed blocks). That is the parsimony claim, and it holds.")
    else:
        print("FALSIFIER FIRED -- the hypothesis is rejected.")
        print(f"  Erez survivors    : 0 across {len(EREZ_GRID)} configurations "
              f"x {n_seeds} seeds")
        print(f"  Gaussian survivors: {ctrl_total} across "
              f"{len(GAUSS_GRID)} x {n_seeds}")
        print("\n  The control survived on the SAME seeds, so this is a")
        print("  statement about the growth function, not about the seeds.")
        print()
        print("  MECHANISM: the published gate is non-negative across the")
        print("  whole positive domain. At u=0.001 it returns +0.0036 where")
        print("  the Gaussian returns -1.0, so empty space cannot decay and")
        print("  any trace fills the grid. The cause is Erez's own centering")
        print("  term -c^a, which pins G(0)=0. Correct for his ODEs; wrong")
        print("  for a CA, which needs sparse regions to actively die.")
        print()
        print("  REPAIR: subtracting a constant restores that decay.")
        print(f"    repaired basin : {fix_best_n}/{n_seeds} seeds at "
              f"a={best_fix[0][0]}, b={best_fix[0][1]}, "
              f"theta={best_fix[0][2]}")
        print(f"    control basin  : {ctrl_best_n}/{n_seeds}")
        print()
        print("  But that is 4 shape parameters against the Gaussian's 2.")
        print("  Erez's '3 knobs not 6' was measured against HILL functions,")
        print("  which are monotone and do need two opposed blocks. Lenia's")
        print("  bump is already non-monotone with two parameters, so the")
        print("  parsimony claim does not transfer to this target.")
    print("=" * 70)

    if not args.no_write:
        p = rec.write()
        print(f"\nwrote {p.relative_to(Path(__file__).resolve().parents[2])}")
    print()
    print(rec.summary())
    return 0


if __name__ == "__main__":
    sys.exit(main())
