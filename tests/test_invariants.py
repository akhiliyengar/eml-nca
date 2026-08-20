"""Tier 2 tests: numerical invariants for iterated maps.

These are the tests that matter most for this project. Correctness of a single
forward pass tells you almost nothing about whether a rule survives 10,000
recursive applications.
"""

import numpy as np
import pytest

from emlnca.ops import EXP_CLAMP, eml_stable, erez_gate
from emlnca.stability import (
    GainTrace,
    check_finite,
    classify,
    numeric_jacobian,
    spectral_radius,
    transfer_gain,
)


def test_gain_trace_detects_expansion():
    """Sanity: a map with gain 1.05 must be flagged expanding."""
    tr = GainTrace()
    ref = np.zeros(2)
    x = np.array([1.0, 0.0])
    for _ in range(50):
        nxt = x * 1.05
        tr.update(x, nxt, ref)
        x = nxt
    assert abs(tr.geometric_mean - 1.05) < 1e-6
    assert tr.verdict() == "expanding"


def test_gain_trace_detects_contraction():
    tr = GainTrace()
    ref = np.zeros(2)
    x = np.array([1.0, 0.0])
    for _ in range(50):
        nxt = x * 0.95
        tr.update(x, nxt, ref)
        x = nxt
    assert abs(tr.geometric_mean - 0.95) < 1e-6
    assert tr.verdict() == "contracting"


def test_the_feedback_hazard_is_real():
    """Quantifies the microphone-next-to-speaker problem for the record.

    100 steps at gain 1.05 amplifies by 131.5x; at 0.95 it decays to 0.0059.
    There is no comfortable middle, which is why gain is instrumented from run
    one rather than diagnosed after a failure.
    """
    assert 1.05**100 > 100.0
    assert 0.95**100 < 0.01


def test_spectral_radius_predicts_iterated_growth():
    """rho(J) must agree with what J**t actually does. This is the whole basis
    for using analytic Jacobians to predict NCA pattern survival."""
    for r, expect in [(0.9, "stable"), (1.1, "unstable")]:
        jac = np.array([[r, 0.3], [0.0, r * 0.5]])
        rho = spectral_radius(jac)
        assert abs(rho - r) < 1e-12
        assert classify(rho) == expect
        grown = np.linalg.norm(np.linalg.matrix_power(jac, 60) @ np.ones(2))
        if expect == "stable":
            assert grown < 1e-2  # 0.9**60 ~ 1.8e-3, plus off-diagonal coupling
        else:
            assert grown > 1e2


def test_spectral_radius_marginal_band():
    assert classify(spectral_radius(np.eye(3))) == "marginal"


def test_analytic_vs_numeric_jacobian():
    """A gate's analytic derivative must match central differences.

    d/dx [ (c+x)^a - b x - c^a ] = a (c+x)^(a-1) - b
    """
    a, b, c = 0.5, 0.3, 0.2

    def f(v):
        return erez_gate(v, a=a, b=b, c=c)

    for x0 in [0.5, 1.0, 3.0]:
        num = numeric_jacobian(f, np.array([x0]))[0, 0]
        ana = a * (c + x0) ** (a - 1.0) - b
        assert abs(num - ana) < 1e-6
        assert abs(transfer_gain(a, b, c, x0) - ana) < 1e-12


def test_check_finite_raises_on_nan():
    with pytest.raises(FloatingPointError, match="non-finite"):
        check_finite(np.array([1.0, np.nan, 3.0]), name="grid")
    with pytest.raises(FloatingPointError):
        check_finite(np.array([np.inf]), name="grid")
    check_finite(np.zeros(4))  # must not raise


def test_eml_stable_never_explodes_under_iteration():
    """The headline safety property.

    Iterate a contractive eml_stable map 5,000 times from many random starts and
    require the state to stay finite throughout. Vanilla EML fails this almost
    immediately, which is precisely why it cannot be dropped into an NCA.
    """
    rng = np.random.default_rng(0)
    x = rng.uniform(-2.0, 2.0, size=256)
    for step in range(5000):
        x = 0.5 * x + 0.05 * eml_stable(0.1 * x, np.abs(x) + 0.5)
        if step % 500 == 0:
            check_finite(x, name=f"state@{step}")
    check_finite(x, name="final")
    assert np.all(np.abs(x) < 1e3)


def test_exp_clamp_bounds_output():
    """The clamp must actually bound exp, on inputs that would otherwise overflow
    float64 (exp overflows just above 709.78)."""
    huge = np.array([1e3, 1e6, np.inf])
    out = eml_stable(huge, np.ones_like(huge))
    assert np.all(np.isfinite(out))
    assert np.all(out <= np.exp(EXP_CLAMP) + 1.0)
