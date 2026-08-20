"""Seed determinism: the invariant everything else rests on.

Previously claimed as implemented and was not. That gap is the same failure this
repository criticises in the EML literature -- asserting a control that does not
exist -- so it is pinned here first.

Why it is an invariant rather than a metric: if a fixed seed does not reproduce
a result, then no number the repository produces means anything. There is no
research reason to break it, only bugs: unseeded RNG, dict/set iteration order
leaking into arithmetic, thread scheduling, or a library reduction order change.
"""

from __future__ import annotations

import numpy as np
import pytest

from emlnca.ops import eml_stable, erez_gate, sol
from emlnca.stability import GainTrace, spectral_radius


def iterated_map(seed: int, steps: int = 200, n: int = 128) -> np.ndarray:
    """A small iterated EML system, deliberately shaped like the real thing.

    Uses eml_stable because it is the only variant safe to iterate: vanilla EML
    hits its domain trap within a few steps once values wander negative.

    The 0.99 retention factor is load-bearing, not arbitrary. An earlier version
    used 0.5, which contracts so hard that 0.5**50 ~ 8.9e-16 -- below machine
    epsilon. Every seed converged to the same fixed point within 50 steps, so
    the determinism test passed VACUOUSLY: it would have stayed green even if
    the seed were ignored entirely. Caught by
    test_different_seeds_actually_differ, which is exactly what that control is
    for.

    Near-unity gain is also the regime that matters here. A persistent NCA
    pattern sits at gain ~1; strongly contracting dynamics are precisely the
    case where nothing interesting survives.
    """
    rng = np.random.default_rng(seed)
    x = rng.uniform(-1.0, 1.0, size=n)
    for _ in range(steps):
        x = 0.99 * x + 0.01 * eml_stable(0.1 * x, np.abs(x) + 0.5)
    return x


def test_map_retains_initial_conditions():
    """Guards the guard.

    If the test map contracts too hard, every determinism assertion below
    becomes vacuous -- convergence to a shared fixed point looks identical to
    correct seed handling. This pins the property that makes the rest of the
    file meaningful.
    """
    a, b = iterated_map(0), iterated_map(1)
    spread = float(np.max(np.abs(a - b)))
    assert spread > 1e-6, (
        f"the test map has erased its initial conditions (max delta "
        f"{spread:.3e}). Every determinism test in this file is now vacuous: "
        f"they would pass even if the seed were ignored. Reduce the "
        f"contraction factor or the step count."
    )


@pytest.mark.parametrize("seed", [0, 1, 42, 12345])
def test_same_seed_is_bitwise_identical(seed):
    """Not 'close'. Bitwise equal.

    allclose would hide exactly the bugs this test exists to catch: a reduction
    order change moves the last bits first, and last-bit drift compounds over
    thousands of NCA steps into a visibly different pattern.
    """
    a = iterated_map(seed)
    b = iterated_map(seed)
    assert np.array_equal(a, b), (
        f"seed {seed} produced different results on two runs in the same "
        f"process. max|delta| = {np.max(np.abs(a - b)):.3e}"
    )
    assert a.tobytes() == b.tobytes(), "bitwise representation differs"


def test_different_seeds_actually_differ():
    """Control for the above.

    A function that ignores its seed entirely would pass the determinism test
    perfectly. This is what stops the suite being vacuously green.
    """
    a = iterated_map(0)
    b = iterated_map(1)
    assert not np.array_equal(a, b), (
        "different seeds produced identical output -- the seed is being "
        "ignored, which makes the determinism test vacuous"
    )


@pytest.mark.parametrize("seed", [0, 7])
def test_determinism_survives_interleaving(seed):
    """Runs must not depend on what ran before them.

    Catches global mutable state: a module-level RNG, a cache keyed on
    insertion order, or anything that makes result N depend on result N-1.
    """
    first = iterated_map(seed)
    _ = iterated_map(seed + 1000)     # unrelated work in between
    _ = np.random.random(1000)        # perturb the global legacy RNG
    second = iterated_map(seed)
    assert np.array_equal(first, second), (
        "interleaved unrelated work changed the result: global mutable state "
        "is leaking between runs"
    )


def test_pure_functions_are_deterministic():
    """The primitives themselves must be free of hidden state."""
    x = np.linspace(-2.0, 2.0, 257)
    y = np.abs(x) + 0.5
    for fn, args in (
        (eml_stable, (x, y)),
        (sol, (x, y)),
        (erez_gate, (np.abs(x), 0.5, 0.3, 0.1)),
    ):
        first = fn(*args)
        second = fn(*args)
        assert np.array_equal(first, second), f"{fn.__name__} is not pure"


def test_gain_trace_is_deterministic():
    def run() -> float:
        tr = GainTrace()
        ref = np.zeros(64)
        rng = np.random.default_rng(3)
        x = rng.uniform(-1.0, 1.0, 64)
        for _ in range(100):
            nxt = 0.97 * x
            tr.update(x, nxt, ref)
            x = nxt
        return tr.geometric_mean

    assert run() == run(), "GainTrace.geometric_mean is not deterministic"


def test_spectral_radius_is_deterministic():
    """Eigenvalue solvers can be order-sensitive; rho(J) drives the stability
    claims, so it must not wobble between calls."""
    rng = np.random.default_rng(11)
    jac = rng.normal(size=(8, 8))
    values = {spectral_radius(jac) for _ in range(5)}
    assert len(values) == 1, f"spectral_radius returned {values}"
