"""Stability instrumentation.

This module exists because of one specific hazard: a neural cellular automaton
applies its update rule 64-96 times during training and often many thousands of
times at inference. EML contains exp(). Gunlu's error analysis (arXiv:2607.16360)
gives the left-input sensitivity of an EML gate as exp(b), and the total
distortion at the root as the PRODUCT of sensitivities along the path.

Iterate a map with per-step gain g for T steps and the perturbation scales as
g**T. At g = 1.05 and T = 100 that is a factor of 131.5. At g = 0.95 it is 0.0059.
There is almost no middle ground, which is why gain must be measured from the
first run rather than inferred after a failure.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np


@dataclass
class GainTrace:
    """Per-step contraction/expansion record for an iterated map."""

    ratios: list[float] = field(default_factory=list)

    def update(self, prev: np.ndarray, curr: np.ndarray, ref: np.ndarray) -> float:
        """Record ||curr - ref|| / ||prev - ref|| for one step."""
        num = float(np.linalg.norm(curr - ref))
        den = float(np.linalg.norm(prev - ref))
        r = num / den if den > 1e-300 else 0.0
        self.ratios.append(r)
        return r

    @property
    def geometric_mean(self) -> float:
        """Effective per-step gain. This is the number that decides survival."""
        if not self.ratios:
            return float("nan")
        arr = np.asarray(self.ratios, dtype=np.float64)
        arr = arr[arr > 0.0]
        if arr.size == 0:
            return 0.0
        return float(np.exp(np.mean(np.log(arr))))

    def verdict(self, tol: float = 0.02) -> str:
        g = self.geometric_mean
        if not np.isfinite(g):
            return "diverged"
        if g > 1.0 + tol:
            return "expanding"
        if g < 1.0 - tol:
            return "contracting"
        return "marginal"


def spectral_radius(jac: np.ndarray) -> float:
    """Largest absolute eigenvalue of a Jacobian.

    For x_{t+1} = f(x_t) linearised near a fixed point x*, perturbations obey
    dx_t ~ J**t dx_0. Whether that grows or shrinks is decided entirely by
    rho(J) = max |eigenvalue|:

        rho < 1  -> perturbations decay: stable, self-healing
        rho > 1  -> perturbations grow: the pattern explodes
        rho ~ 1  -> edge of chaos, where the interesting structure lives

    NCA regeneration IS the rho < 1 case. With a ReLU MLP you can only obtain a
    numerical Jacobian of a function that is non-identifiable from the weights
    (Waxman et al.); with an EML tree the Jacobian is the exact analytic
    derivative of an explicit closed-form equation.
    """
    return float(np.max(np.abs(np.linalg.eigvals(np.asarray(jac)))))


def classify(rho: float, tol: float = 1e-3) -> str:
    if not np.isfinite(rho):
        return "diverged"
    if rho < 1.0 - tol:
        return "stable"
    if rho > 1.0 + tol:
        return "unstable"
    return "marginal"


def numeric_jacobian(f, x: np.ndarray, h: float = 1e-6) -> np.ndarray:
    """Central-difference Jacobian. Baseline for checking analytic ones."""
    x = np.asarray(x, dtype=np.float64)
    f0 = np.atleast_1d(np.asarray(f(x), dtype=np.float64))
    jac = np.zeros((f0.size, x.size), dtype=np.float64)
    for j in range(x.size):
        dx = np.zeros_like(x)
        dx[j] = h
        fp = np.atleast_1d(np.asarray(f(x + dx), dtype=np.float64))
        fm = np.atleast_1d(np.asarray(f(x - dx), dtype=np.float64))
        jac[:, j] = (fp - fm) / (2.0 * h)
    return jac


def transfer_gain(a: float, b: float, c: float, z_star: float) -> float:
    """Linearised gain of one centered EML cascade layer (Erez eq. 25).

        g_k = a_k (c_k + z*_{k-1})^(a_k - 1) - b_k

    Erez's cascade transfer function is H_K(s) = prod_k g_k / (1 + s tau_k):
    each layer contributes exactly one gain and one timescale. The product of
    the g_k is what decides whether a deep cascade holds or runs away.
    """
    return float(a * np.power(max(c + z_star, 1e-12), a - 1.0) - b)


def check_finite(arr: np.ndarray, name: str = "state") -> None:
    """Fail loudly on NaN/inf. In an iterated CA a single NaN contaminates the
    whole grid within a few steps, so late detection means a lost run."""
    a = np.asarray(arr)
    if not np.all(np.isfinite(a)):
        n_nan = int(np.sum(np.isnan(a)))
        n_inf = int(np.sum(np.isinf(a)))
        raise FloatingPointError(
            f"{name} became non-finite: {n_nan} NaN, {n_inf} inf "
            f"out of {a.size} elements"
        )
