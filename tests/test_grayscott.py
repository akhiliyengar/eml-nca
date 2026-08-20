"""Tests for the Gray-Scott reference and the atom-library forest.

These are INVARIANTS -- properties of the implementation, not research
outcomes. The experiment's actual finding (can EML recover u*v^2?) is a METRIC
and lives in results/, never here.
"""

from __future__ import annotations

import dataclasses

import numpy as np
import pytest

from emlnca.forest import build_library, search
from emlnca.grayscott import PRESETS, GrayScott, sample_domain

# ------------------------------------------------------------ gray-scott

def test_reaction_terms_match_closed_form():
    gs = GrayScott(F=0.035, k=0.065)
    u, v = sample_domain(n=256, seed=0)
    assert np.allclose(gs.reaction_u(u, v), -u * v**2 + gs.F * (1 - u))
    assert np.allclose(gs.reaction_v(u, v), u * v**2 - (gs.F + gs.k) * v)


def test_laplacian_of_constant_is_zero():
    """Sanity on the stencil: a flat field has no curvature."""
    a = np.full((16, 16), 3.7)
    assert np.allclose(GrayScott.laplacian(a), 0.0, atol=1e-12)


def test_laplacian_is_periodic():
    """np.roll wraps, so opposite edges must be coupled."""
    a = np.zeros((8, 8))
    a[0, 0] = 1.0
    lap = GrayScott.laplacian(a)
    assert lap[-1, 0] == pytest.approx(1.0)
    assert lap[0, -1] == pytest.approx(1.0)
    assert lap[0, 0] == pytest.approx(-4.0)


def test_simulation_is_deterministic():
    a = GrayScott.preset("solitons").run(n=32, steps=50, seed=0)
    b = GrayScott.preset("solitons").run(n=32, steps=50, seed=0)
    assert np.array_equal(a[0], b[0]) and np.array_equal(a[1], b[1])


def test_simulation_stays_finite():
    """Gray-Scott can blow up if dt is too large for the diffusion constants.
    Non-finite state is an invariant violation, never a finding."""
    u, v = GrayScott.preset("coral").run(n=48, steps=500, seed=1)
    assert np.all(np.isfinite(u)) and np.all(np.isfinite(v))


def test_simulation_actually_forms_a_pattern():
    """Guards the guard.

    A run that decays to a uniform field would make any downstream comparison
    vacuous -- exactly the failure caught in the determinism suite, where an
    over-contracting map erased its initial conditions.
    """
    u, _ = GrayScott.preset("solitons").run(n=64, steps=1500, seed=0)
    assert float(np.std(u)) > 0.01, (
        f"field is essentially uniform (std={np.std(u):.2e}); no pattern "
        f"formed, so nothing downstream would be meaningful"
    )


def test_presets_are_known():
    for name in PRESETS:
        gs = GrayScott.preset(name)
        assert 0.0 < gs.F < 0.1 and 0.0 < gs.k < 0.1
    with pytest.raises(KeyError):
        GrayScott.preset("does-not-exist")


def test_params_are_frozen():
    """A config that can drift mid-run is a provenance hole."""
    gs = GrayScott()
    with pytest.raises(dataclasses.FrozenInstanceError):
        gs.F = 0.5


# ---------------------------------------------------------------- forest

def test_library_is_deterministic():
    u, v = sample_domain(n=200, seed=0)
    a = [x.name for x in build_library(u, v)]
    b = [x.name for x in build_library(u, v)]
    assert a == b


def test_library_always_contains_trivial_regressors():
    """Without a constant and the raw inputs, a negative result could just mean
    the basis was rigged."""
    u, v = sample_domain(n=200, seed=0)
    names = {x.name for x in build_library(u, v)}
    assert {"1", "u", "v"} <= names


def test_library_rejects_degenerate_atoms():
    """Derived atoms must be finite and non-constant.

    The intercept is exempt: a constant regressor has zero variance by
    definition, and removing it was the bug the polynomial control caught.
    """
    u, v = sample_domain(n=200, seed=0)
    for atom in build_library(u, v):
        assert np.all(np.isfinite(atom.values))
        if atom.name != "1":
            assert float(np.std(atom.values)) >= 1e-10


def test_intercept_is_present_and_constant():
    """Pins the fix: the constant atom must survive the degeneracy filter."""
    u, v = sample_domain(n=200, seed=0)
    const = [a for a in build_library(u, v) if a.name == "1"]
    assert len(const) == 1, "the intercept was filtered out"
    assert float(np.std(const[0].values)) == 0.0


def test_polynomial_control_recovers_the_cross_term():
    """THE CONTROL, and the test that makes a negative EML result readable.

    The polynomial library contains u*v^2 exactly, so it MUST recover the
    Gray-Scott reaction term to machine precision. If this fails, the harness
    is broken and no statement about EML can be made from it.
    """
    gs = GrayScott(F=0.035, k=0.065)
    u, v = sample_domain(n=3000, seed=0)
    target = gs.reaction_u(u, v)
    atoms = build_library(u, v, families=("poly",))
    fit = search(atoms, target, max_terms=3)
    assert fit.rel_mse < 1e-12, (
        f"the CONTROL library failed (relMSE={fit.rel_mse:.3e}). The harness "
        f"is broken; no conclusion about EML can be drawn until this passes."
    )


def test_search_is_deterministic():
    gs = GrayScott()
    u, v = sample_domain(n=500, seed=0)
    target = gs.reaction_u(u, v)
    atoms = build_library(u, v, families=("poly",))
    f1 = search(atoms, target, max_terms=2)
    f2 = search(atoms, target, max_terms=2)
    assert f1.atoms == f2.atoms
    assert np.array_equal(f1.coeffs, f2.coeffs)


def test_search_improves_with_more_terms():
    """More atoms cannot fit worse -- least squares is nested."""
    gs = GrayScott()
    u, v = sample_domain(n=800, seed=0)
    target = gs.reaction_u(u, v)
    atoms = build_library(u, v, families=("poly",))
    prev = np.inf
    for k in (1, 2, 3):
        fit = search(atoms, target, max_terms=k)
        assert fit.mse <= prev + 1e-12
        prev = fit.mse


def test_fit_formula_is_readable():
    gs = GrayScott()
    u, v = sample_domain(n=300, seed=0)
    atoms = build_library(u, v, families=("poly",))
    fit = search(atoms, gs.reaction_u(u, v), max_terms=2)
    s = fit.formula()
    assert "*" in s and len(s) > 3


def test_atoms_can_be_re_evaluated_off_domain():
    """Pins the fix for a harness artifact.

    The extrapolation test must re-evaluate the FITTED atoms on a held-out
    band. Rebuilding the library there is not equivalent: dedup is
    data-dependent, so a different set survives and a fitted name may be
    absent, which reported extrapolation error as `inf` and overstated a real
    failure with an artifact.
    """
    from emlnca.grayscott import split_domain
    (uf, vf), (ut, vt) = split_domain(n=300, seed=0)
    for atom in build_library(uf, vf, families=("eml", "sol", "poly")):
        out = atom.evaluate(ut, vt)
        assert out.shape == ut.shape
        assert np.all(np.isfinite(out)), f"{atom.name} not finite off-domain"


def test_re_evaluation_matches_original_grid():
    u, v = sample_domain(n=200, seed=0)
    for atom in build_library(u, v, families=("eml", "sol", "poly")):
        assert np.allclose(atom.evaluate(u, v), atom.values, atol=0, rtol=0)


def test_extrapolation_separates_exact_from_approximate():
    """The criterion that replaced a bad falsifier.

    An exact basis (polynomial, which contains u*v^2) must extrapolate without
    degrading. A basis that merely approximates on the fitted band must not.
    Without this, relMSE < 0.01 on the fitted domain reads as success for a fit
    that is 28 orders of magnitude worse than the control.
    """
    from emlnca.grayscott import split_domain
    gs = GrayScott()
    (uf, vf), (ut, vt) = split_domain(n=2000, seed=0)
    y_fit, y_test = gs.reaction_u(uf, vf), gs.reaction_u(ut, vt)

    atoms = build_library(uf, vf, families=("poly",))
    fit = search(atoms, y_fit, max_terms=3)
    by_name = {a.name: a for a in atoms}
    pred = sum(c * by_name[n].evaluate(ut, vt)
               for c, n in zip(fit.coeffs, fit.atoms))
    extrap = float(np.mean((pred - y_test) ** 2) / np.mean(y_test**2))
    assert extrap < 1e-12, (
        f"the exact basis failed to extrapolate (relMSE={extrap:.3e}); the "
        f"criterion itself would then be meaningless"
    )
