"""Additive atomic forests over EML/SOL primitives.

Implements Belaiche's "materialised-library mode" (arXiv:2605.08130): rather
than gradient descent over tree parameters, precompute a library of candidate
atoms and search for a sparse linear combination

    f(u, v) ~= sum_k  c_k * phi_k(u, v)

Chosen over the gradient mode for three reasons that matter here:

  convex      given a chosen subset, the coefficient fit is least squares. No
              optimiser, no learning rate, no restarts, no local minima -- so a
              failure is a statement about the BASIS, not about optimisation.
              That distinction is the whole point of Rung 1.
  numpy-only  no torch. Fewer moving parts, and determinism is an invariant.
  honest      Odrzywolek reports blind gradient recovery collapsing to 0/448 at
              depth 6. Using gradients here would conflate "EML cannot express
              this" with "Adam could not find it".

The subset search itself remains combinatorial; only the coefficient fit is
convex.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from functools import partial
from itertools import combinations

import numpy as np

from .ops import eml_stable, sol

# Inner linear forms fed to the binary primitives. Deliberately small and
# hand-picked: a full sweep of integer coefficients explodes the library
# without adding expressive reach, and a bloated library makes a negative
# result unconvincing ("you just did not search hard enough").
INNER: list[tuple[str, Callable[[np.ndarray, np.ndarray], np.ndarray]]] = [
    ("1", lambda u, v: np.ones_like(u)),
    ("u", lambda u, v: u),
    ("v", lambda u, v: v),
    ("u+v", lambda u, v: u + v),
    ("u-v", lambda u, v: u - v),
    ("2u", lambda u, v: 2.0 * u),
    ("2v", lambda u, v: 2.0 * v),
    ("1+u", lambda u, v: 1.0 + u),
    ("1+v", lambda u, v: 1.0 + v),
]


@dataclass
class Atom:
    """A candidate regressor.

    Carries its generating function, not only its values on one grid. That
    matters for the extrapolation test: fitted atoms must be re-evaluated on a
    held-out band, and rebuilding the library there is NOT equivalent -- dedup
    is data-dependent, so a different set survives and a fitted name may not
    exist at all. An earlier version did exactly that and reported
    extrapolation error as `inf`, overstating a real failure with an artifact
    of the harness.
    """

    name: str
    values: np.ndarray
    family: str          # eml | sol | poly | linear
    fn: Callable[[np.ndarray, np.ndarray], np.ndarray] | None = None

    def evaluate(self, u: np.ndarray, v: np.ndarray) -> np.ndarray:
        if self.fn is None:
            raise ValueError(f"atom {self.name!r} cannot be re-evaluated")
        return self.fn(u, v)

    def __repr__(self) -> str:
        return f"Atom({self.name!r}, {self.family})"


def _binary(op, f1, f2, a: np.ndarray, b: np.ndarray) -> np.ndarray:
    """Module-level so atoms stay picklable and lint-clean (no IIFE lambdas)."""
    return op(f1(a, b), f2(a, b))


def _monomial(p: int, q: int, a: np.ndarray, b: np.ndarray) -> np.ndarray:
    return (a**p) * (b**q)


def _finite(a: np.ndarray) -> bool:
    return bool(np.all(np.isfinite(a)))


def _degenerate(a: np.ndarray) -> bool:
    """Constant or near-constant atoms carry no information."""
    return float(np.std(a)) < 1e-10


def build_library(
    u: np.ndarray,
    v: np.ndarray,
    families: tuple[str, ...] = ("eml", "sol"),
    dedup_corr: float = 0.9995,
) -> list[Atom]:
    """Materialise candidate atoms on the sample grid.

    Deduplication is by correlation on the grid: two atoms that agree to
    |corr| > dedup_corr are the same regressor for fitting purposes, and
    keeping both only inflates the apparent search size.

    Deterministic by construction: INNER is an ordered list, families are
    iterated in the given order, and no set/dict iteration reaches the output.
    """
    atoms: list[Atom] = []

    def add(name: str, fn: Callable, family: str, force: bool = False) -> None:
        vals = fn(u, v)
        # `force` exempts the trivial regressors from the degeneracy filter.
        # The constant atom has zero variance BY DEFINITION, so the generic
        # "reject near-constant atoms" rule silently removed the intercept and
        # every fit then had to approximate F with slope terms. Caught by the
        # polynomial control, which is exactly why the control exists.
        if not _finite(vals):
            return
        if not force and _degenerate(vals):
            return
        for a in atoms:                      # dedup against what we have
            n1 = vals - vals.mean()
            n2 = a.values - a.values.mean()
            d = float(np.linalg.norm(n1) * np.linalg.norm(n2))
            if d > 0 and abs(float(n1 @ n2) / d) > dedup_corr:
                return
        atoms.append(Atom(name, vals, family, fn))

    # Always include the trivial regressors. Without them a "failure" could
    # just mean the basis lacked a constant, which would be a rigged test.
    add("1", lambda a, b: np.ones_like(a), "linear", force=True)
    add("u", lambda a, b: a.copy(), "linear", force=True)
    add("v", lambda a, b: b.copy(), "linear", force=True)

    if "eml" in families:
        for n1, f1 in INNER:
            for n2, f2 in INNER:
                add(f"eml({n1},{n2})", partial(_binary, eml_stable, f1, f2), "eml")

    if "sol" in families:
        for n1, f1 in INNER:
            for n2, f2 in INNER:
                add(f"sol({n1},{n2})", partial(_binary, sol, f1, f2), "sol")

    if "poly" in families:
        # CONTROL library. Contains u*v^2 exactly, so it must succeed. If it
        # does not, the harness is broken rather than EML being inadequate --
        # which is the only way to read a negative result honestly.
        for i in range(4):
            for j in range(4):
                if 0 < i + j <= 3:
                    add(f"u^{i}v^{j}", partial(_monomial, i, j), "poly")

    return atoms


@dataclass
class Fit:
    atoms: list[str]
    coeffs: np.ndarray
    mse: float
    rel_mse: float
    residual: np.ndarray

    def formula(self, precision: int = 4) -> str:
        parts = [f"{c:+.{precision}g}*{n}" for c, n in zip(self.coeffs, self.atoms)]
        return " ".join(parts).lstrip("+")


def _lstsq(design: np.ndarray, target: np.ndarray) -> tuple[np.ndarray, float]:
    coeffs, *_ = np.linalg.lstsq(design, target, rcond=None)
    resid = design @ coeffs - target
    return coeffs, float(np.mean(resid**2))


def search(
    atoms: list[Atom],
    target: np.ndarray,
    max_terms: int = 3,
    beam: int = 40,
) -> Fit:
    """Best sparse combination up to `max_terms` atoms.

    K=1 and K=2 are exhaustive. K>=3 uses beam search seeded from the best
    K-1 subsets, which is Belaiche's structure and keeps the run tractable
    without hiding the combinatorics.
    """
    design_all = np.stack([a.values for a in atoms], axis=1)
    denom = float(np.mean(target**2)) or 1.0

    best: tuple[float, tuple[int, ...], np.ndarray] | None = None

    def consider(idx: tuple[int, ...]) -> tuple[float, np.ndarray]:
        coeffs, mse = _lstsq(design_all[:, list(idx)], target)
        return mse, coeffs

    # K = 1
    scored: list[tuple[float, tuple[int, ...]]] = []
    for i in range(len(atoms)):
        mse, coeffs = consider((i,))
        scored.append((mse, (i,)))
        if best is None or mse < best[0]:
            best = (mse, (i,), coeffs)

    # K = 2, exhaustive
    if max_terms >= 2:
        for i, j in combinations(range(len(atoms)), 2):
            mse, coeffs = consider((i, j))
            scored.append((mse, (i, j)))
            if mse < best[0]:
                best = (mse, (i, j), coeffs)

    # K >= 3, beam
    frontier = [idx for _, idx in sorted(scored)[:beam] if len(idx) == 2]
    for _ in range(3, max_terms + 1):
        nxt: list[tuple[float, tuple[int, ...]]] = []
        for idx in frontier:
            for i in range(len(atoms)):
                if i in idx:
                    continue
                cand = tuple(sorted((*idx, i)))
                mse, coeffs = consider(cand)
                nxt.append((mse, cand))
                if mse < best[0]:
                    best = (mse, cand, coeffs)
        frontier = [idx for _, idx in sorted(nxt)[:beam]]
        if not frontier:
            break

    mse, idx, coeffs = best
    design = design_all[:, list(idx)]
    return Fit(
        atoms=[atoms[i].name for i in idx],
        coeffs=coeffs,
        mse=mse,
        rel_mse=mse / denom,
        residual=design @ coeffs - target,
    )
