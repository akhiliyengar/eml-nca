"""Core EML-family primitive operators.

Reference: Odrzywolek, "All elementary functions from a single operator",
arXiv:2603.21852v2.

Three variants are provided, and the distinction matters enormously in
practice:

    eml            vanilla, complex-domain, principal branch. Faithful to the
                   paper. Will produce NaN/inf on real pipelines.
    eml_admissible Gunlu's real-admissible restriction (arXiv:2607.16360):
                   caller guarantees y > 0, everything stays real.
    eml_stable     Germany/Abdo/Bakarji's softplus surrogate
                   (arXiv:2606.23179 sec 3.1): ln -> ln(softplus(y) + eps).
                   Differentiable everywhere, no domain trap.

Only `eml_stable` is safe to iterate inside a cellular automaton.
"""

from __future__ import annotations

import cmath

import numpy as np

EPS = 1e-6

# --- exp overflow guard -----------------------------------------------------
# float64 exp overflows just above 709.78. We clamp well below that because
# EML trees compose exponentials, so intermediate blowup compounds.
EXP_CLAMP = 20.0


def _softplus(x: np.ndarray) -> np.ndarray:
    """log(1 + e^x), computed without overflowing for large x."""
    return np.logaddexp(0.0, x)


def eml_scalar(x: complex, y: complex) -> complex:
    """Vanilla EML on the complex plane, principal branch.

    eml(x, y) = exp(x) - ln(y)

    This is the operator exactly as defined in the source paper. It is the
    reference implementation used to verify the published identities; it is
    NOT the one to use inside a simulation.
    """
    return cmath.exp(x) - cmath.log(y)


def eml(x: np.ndarray, y: np.ndarray) -> np.ndarray:
    """Vectorised vanilla EML. Complex in, complex out."""
    x = np.asarray(x, dtype=np.complex128)
    y = np.asarray(y, dtype=np.complex128)
    return np.exp(x) - np.log(y)


def eml_admissible(x: np.ndarray, y: np.ndarray) -> np.ndarray:
    """Real-admissible EML (Gunlu). Requires y > 0 elementwise.

    Raises rather than silently returning NaN, because in an iterated CA a
    silent NaN propagates across the whole grid within a few steps and you
    lose the run.
    """
    x = np.asarray(x, dtype=np.float64)
    y = np.asarray(y, dtype=np.float64)
    if np.any(y <= 0.0):
        raise ValueError(
            "eml_admissible requires y > 0 (real-admissible tree); "
            f"got min(y)={float(np.min(y)):.6g}"
        )
    return np.exp(np.clip(x, -EXP_CLAMP, EXP_CLAMP)) - np.log(y)


def eml_stable(x: np.ndarray, y: np.ndarray, eps: float = EPS) -> np.ndarray:
    """Softplus-stabilised EML. Total on all of R^2, no domain trap.

    Coincides with vanilla EML on strictly positive y (up to eps) and
    deviates smoothly near and below zero instead of exploding.
    """
    x = np.asarray(x, dtype=np.float64)
    y = np.asarray(y, dtype=np.float64)
    return np.exp(np.clip(x, -EXP_CLAMP, EXP_CLAMP)) - np.log(_softplus(y) + eps)


def sol(u: np.ndarray, v: np.ndarray) -> np.ndarray:
    """SOL primitive (Belaiche, arXiv:2605.08130): sin(u) - cos(v).

    Supplementary, not generating: it cannot produce exp or ln at any depth.
    Its purpose is depth reduction. Trigonometric atoms cost depth ~8 in pure
    EML (2^8 = 256 leaves); SOL delivers them at depth 1 (2 leaves).
    """
    return np.sin(np.asarray(u, dtype=np.float64)) - np.cos(
        np.asarray(v, dtype=np.float64)
    )


def eml_generalized(
    x: np.ndarray,
    y: np.ndarray,
    a: float = 1.0,
    b: float = 1.0,
    c: float = 0.0,
    d: float = -1.0,
    e: float = 1.0,
    f: float = 0.0,
    eps: float = EPS,
) -> np.ndarray:
    """Six-parameter EML atom (Germany/Abdo/Bakarji eq. 2).

        EML_theta(x, y) = a*exp(b*x + c) + d*ln(e*y + f)

    Vanilla EML is recovered at a=b=e=1, d=-1, c=f=0.

    The universal approximation theorem is proved for THIS form, not for
    vanilla EML. The generalisation exists because in vanilla EML every
    constant must be rebuilt recursively from the digit 1, so tree size
    scales badly with coefficient magnitude. Whether the theorem survives
    for vanilla EML is stated as an open problem in that paper.
    """
    x = np.asarray(x, dtype=np.float64)
    y = np.asarray(y, dtype=np.float64)
    lin = np.clip(b * x + c, -EXP_CLAMP, EXP_CLAMP)
    return a * np.exp(lin) + d * np.log(_softplus(e * y + f) + eps)


def erez_gate(
    x: np.ndarray, a: float, b: float, c: float = 0.0
) -> np.ndarray:
    """Centered activation-suppression gate (Erez, arXiv:2605.02972 eq. 6).

        G_{a,b,c}(x) = (c + x)^a - b*x - c^a

    Non-monotone in a SINGLE block for 0 < a < 1, b > 0: rises, peaks, falls.
    A Hill function is monotone and needs a difference of two opposed blocks
    to produce the same shape, which doubles the static parameter count.

    This is the most directly transferable result in the citing literature:
    Lenia's growth function is exactly a non-monotone univariate map.
    """
    x = np.asarray(x, dtype=np.float64)
    base = np.maximum(c + x, 0.0)
    return np.power(base, a) - b * x - np.power(max(c, 0.0), a)


def erez_peak(a: float, b: float) -> float:
    """Argmax of the uncentered gate R^a - b*R, valid for 0 < a < 1, b > 0.

        R* = (a / b) ** (1 / (1 - a))

    Derived by setting a*R^(a-1) - b = 0. Second derivative
    a*(a-1)*R^(a-2) < 0 confirms it is a maximum.
    """
    if not (0.0 < a < 1.0):
        raise ValueError(f"unimodality requires 0 < a < 1, got a={a}")
    if b <= 0.0:
        raise ValueError(f"unimodality requires b > 0, got b={b}")
    return float((a / b) ** (1.0 / (1.0 - a)))
