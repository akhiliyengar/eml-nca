"""Tier 1 tests: published identities.

These encode claims from arXiv:2603.21852 directly. They must never fail. If
one does, the primitive is broken and every downstream result is void.
"""

import cmath

import numpy as np
import pytest

from emlnca.identities import IDENTITIES, const_e, exp_, ln_
from emlnca.ops import (
    eml,
    eml_admissible,
    eml_generalized,
    eml_scalar,
    eml_stable,
    erez_gate,
    erez_peak,
    sol,
)


@pytest.mark.parametrize("name", sorted(IDENTITIES))
def test_published_identity(name):
    fn, args, expected = IDENTITIES[name]
    got = fn(*args)
    assert cmath.isclose(got, expected, rel_tol=1e-12, abs_tol=1e-12), (
        f"identity {name!r} broke: got {got!r}, expected {expected!r}"
    )


def test_e_from_two_ones():
    """The headline: the constant e out of nothing but eml and 1."""
    assert abs(const_e() - cmath.e) < 1e-15


def test_exp_is_depth_one():
    for x in [-3.0, -0.5, 0.0, 0.5, 3.0]:
        assert abs(exp_(x) - cmath.exp(x)) < 1e-12


def test_ln_roundtrip():
    """ln(exp(x)) == x through the EML forms only."""
    for x in [0.25, 1.0, 2.5, 7.0]:
        assert abs(ln_(exp_(x)) - x) < 1e-10


@pytest.mark.parametrize("z", [-1.0, -2.0, -0.5, -10.0])
def test_ln_negative_agrees_on_this_platform(z):
    """The EML ln form DOES agree with the principal branch on negative reals
    under CPython/IEEE-754 -- but only by a hair. See the fragility test below.
    """
    assert abs(ln_(z) - cmath.log(z)) < 1e-12


@pytest.mark.parametrize("z", [-1.0, -2.0, -0.5, -10.0])
def test_ln_negative_is_knife_edge_on_the_branch_cut(z):
    """Pins the fragility the paper warns about.

    The paper's simplest ln form is equivalent to e - log(e^e / z). For z < 0
    the intermediate e^e/z lands ON the negative real axis, i.e. exactly on the
    principal branch cut. Whether it rounds to just-below or just-above decides
    whether the final imaginary part is +i*pi or -i*pi.

    Empirically the intermediate sits ~2e-15 BELOW the axis (a few ULPs), which
    double-negates back to the correct answer. That margin is small enough that
    a different libm, rounding mode, FMA contraction or CPU could flip it -- and
    then formulas for i built on ln(-1) = i*pi silently get the wrong sign,
    exactly as Odrzywolek reports. He patches the sign by hand in his compiler.

    This test exists so that if a CI runner lands on the other side we find out
    from a red test rather than from corrupted downstream results.
    """
    inner = cmath.exp(cmath.e - cmath.log(z))
    assert inner.real < 0.0, "intermediate should sit on the negative real axis"
    assert abs(inner.imag) < 1e-13, "and essentially ON the cut"
    assert inner.imag < 0.0, (
        "intermediate flipped to the other side of the branch cut; the EML ln "
        "identity will now return the wrong sign for i. Enable the manual sign "
        "correction before trusting any downstream constant."
    )


def test_ln_sign_flips_if_pushed_across_the_cut():
    """Demonstrates the failure mode directly, by nudging the intermediate to
    the other side of the cut. Confirms the paper's claim is real rather than
    theoretical -- we are simply landing on the lucky side by ~8 ULPs.
    """
    z = -1.0
    inner = cmath.exp(cmath.e - cmath.log(z))
    lucky = cmath.e - cmath.log(complex(inner.real, -abs(inner.imag)))
    flipped = cmath.e - cmath.log(complex(inner.real, +abs(inner.imag)))
    assert abs(lucky - cmath.log(z)) < 1e-12
    assert abs(flipped.imag + cmath.log(z).imag) < 1e-12  # wrong sign
    assert abs(flipped - lucky) > 6.0  # a full 2*pi apart


def test_vectorised_matches_scalar():
    xs = np.array([0.1, 0.5, 1.0])
    ys = np.array([1.0, 2.0, 3.0])
    vec = eml(xs, ys)
    for i in range(len(xs)):
        assert abs(vec[i] - eml_scalar(xs[i], ys[i])) < 1e-12


def test_admissible_matches_vanilla_on_positive_domain():
    x = np.linspace(-2.0, 2.0, 17)
    y = np.linspace(0.1, 5.0, 17)
    assert np.allclose(eml_admissible(x, y), eml(x, y).real, atol=1e-12)


def test_admissible_rejects_nonpositive():
    """Loud failure, not silent NaN. A silent NaN contaminates a whole CA grid
    within a few steps."""
    with pytest.raises(ValueError, match="real-admissible"):
        eml_admissible(np.array([1.0]), np.array([-0.5]))
    with pytest.raises(ValueError):
        eml_admissible(np.array([1.0]), np.array([0.0]))


def test_stable_agrees_with_vanilla_where_it_should():
    """Softplus surrogate coincides with vanilla EML for comfortably positive y."""
    x = np.linspace(-2.0, 2.0, 21)
    y = np.full_like(x, 8.0)
    assert np.allclose(eml_stable(x, y), eml(x, y).real, atol=2e-3)


def test_stable_is_total():
    """Never NaN, never inf, anywhere on R^2. This is the property that makes it
    the only variant safe to iterate."""
    x = np.linspace(-500.0, 500.0, 401)
    y = np.linspace(-500.0, 500.0, 401)
    xx, yy = np.meshgrid(x, y)
    out = eml_stable(xx, yy)
    assert np.all(np.isfinite(out)), "eml_stable produced non-finite values"


def test_generalized_reduces_to_vanilla():
    """Germany et al. eq 2 at a=b=e=1, d=-1, c=f=0 must be vanilla EML."""
    x = np.linspace(-2.0, 2.0, 21)
    y = np.full_like(x, 4.0)
    gen = eml_generalized(x, y, a=1.0, b=1.0, c=0.0, d=-1.0, e=1.0, f=0.0)
    assert np.allclose(gen, eml_stable(x, y), atol=1e-12)


def test_sol_gives_trig_at_depth_one():
    """The whole point of SOL: sin and cos at depth 1 instead of depth ~8."""
    x = np.linspace(-np.pi, np.pi, 33)
    ones = np.ones_like(x)
    assert np.allclose(sol(x, ones) + np.cos(1.0), np.sin(x), atol=1e-12)
    assert np.allclose(np.sin(1.0) - sol(ones, x), np.cos(x), atol=1e-12)


def test_erez_gate_is_non_monotone():
    """The load-bearing claim for Lenia: one block, rise then fall.

    A Hill function cannot do this at any parameter setting; it needs a
    difference of two opposed blocks, doubling the parameter count.
    """
    a, b = 0.5, 0.3
    x = np.linspace(0.0, 12.0, 2001)
    g = erez_gate(x, a=a, b=b, c=0.0)
    peak_idx = int(np.argmax(g))
    assert 0 < peak_idx < len(x) - 1, "peak must be interior, i.e. it falls again"
    d = np.diff(g)
    assert np.any(d > 0) and np.any(d < 0), "must both rise and fall"


def test_erez_peak_matches_numerics():
    """Closed-form argmax R* = (a/b)^(1/(1-a)) against a fine grid."""
    for a, b in [(0.5, 0.3), (0.25, 1.0), (0.75, 0.5)]:
        analytic = erez_peak(a, b)
        x = np.linspace(1e-6, 4.0 * analytic + 1.0, 400001)
        numeric = x[int(np.argmax(np.power(x, a) - b * x))]
        assert abs(analytic - numeric) / analytic < 1e-3


def test_erez_peak_rejects_non_unimodal():
    with pytest.raises(ValueError):
        erez_peak(a=1.5, b=0.3)  # a > 1
    with pytest.raises(ValueError):
        erez_peak(a=0.5, b=-1.0)  # b <= 0


def test_hill_cannot_be_non_monotone():
    """Control for the above: the null model really is monotone for every h, Kd.

    This is what makes Erez's depth-1 claim meaningful rather than rhetorical.
    """
    x = np.linspace(0.01, 20.0, 4001)
    for h in [0.5, 1.0, 2.0, 4.0, 8.0]:
        for kd in [0.5, 1.0, 4.0]:
            hill = x**h / (kd**h + x**h)
            assert np.all(np.diff(hill) > -1e-12), "Hill must be non-decreasing"
