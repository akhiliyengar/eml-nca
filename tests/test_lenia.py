"""Tests for the Lenia simulator.

INVARIANTS only. Whether the EML gate keeps a creature alive is a METRIC and
lives in results/, never here.

PLAIN ENGLISH
These check the game board works: pieces do not vanish for no reason, the same
opening always plays out the same way, and the "is it alive" judge actually
tells alive from dead. They say nothing about who wins -- that is the
experiment's job, and a test that decided it would be marking its own homework.
"""

from __future__ import annotations

import numpy as np
import pytest

from emlnca.lenia import (
    Lenia,
    erez_growth,
    gaussian_growth,
    make_growth,
    ring_kernel,
    run,
    seed_disc,
)
from emlnca.ops import erez_peak

# --------------------------------------------------------------- growth fns

def test_gaussian_growth_peaks_at_mu():
    """The control must brighten most at exactly the amount it was told to."""
    g = gaussian_growth(mu=0.15, sigma=0.017)
    u = np.linspace(0.0, 0.5, 20001)
    assert u[int(np.argmax(g(u)))] == pytest.approx(0.15, abs=1e-3)
    assert g(np.array([0.15]))[0] == pytest.approx(1.0, abs=1e-9)


def test_gaussian_growth_is_bounded():
    """Never outside [-1, 1], or a single step could swamp the grid."""
    g = gaussian_growth()
    out = g(np.linspace(-5.0, 5.0, 5001))
    assert out.min() >= -1.0 - 1e-12 and out.max() <= 1.0 + 1e-12


def test_erez_growth_is_non_monotone():
    """THE load-bearing claim.

    PLAIN ENGLISH
    The curve must go up and then come back down. If it only ever went up, it
    would be an ordinary saturating curve and there would be no reason to
    prefer it over what Lenia already uses.
    """
    g = erez_growth(a=0.5, b=0.3, c=0.02)
    x = np.linspace(0.0, 6.0, 6001)
    y = g(x)
    peak = int(np.argmax(y))
    assert 0 < peak < len(x) - 1, "peak must be interior: it has to come down"
    d = np.diff(y)
    assert np.any(d > 0) and np.any(d < 0)


def test_erez_growth_is_zero_at_zero():
    """Empty space must stay empty.

    PLAIN ENGLISH
    If a blank cell grew even slightly each step, the whole grid would slowly
    fog over and every creature would be buried. The -c^a term exists purely to
    stop that, so it gets its own test.
    """
    for a, b, c in ((0.5, 0.3, 0.02), (0.25, 1.0, 0.1), (0.75, 0.5, 0.001)):
        assert erez_growth(a, b, c)(np.array([0.0]))[0] == pytest.approx(
            0.0, abs=1e-9)


def test_erez_peak_matches_closed_form():
    """Grid search must agree with R* = (a/b)^(1/(1-a)) when centering is off."""
    for a, b in ((0.5, 0.3), (0.25, 1.0)):
        g = erez_growth(a=a, b=b, c=0.0, scale=1.0)
        x = np.linspace(1e-6, 6.0 * erez_peak(a, b), 200001)
        assert x[int(np.argmax(g(x)))] == pytest.approx(erez_peak(a, b), rel=1e-3)


def test_erez_growth_is_bounded():
    g = erez_growth(a=0.5, b=0.3, c=0.02, scale=4.0)
    out = g(np.linspace(-2.0, 50.0, 20001))
    assert out.min() >= -1.0 - 1e-12 and out.max() <= 1.0 + 1e-12


def test_make_growth_rejects_unknown():
    with pytest.raises(ValueError, match="unknown growth"):
        make_growth("not-a-growth-function")


# ------------------------------------------------------------------ kernel

def test_kernel_sums_to_one():
    """Normalised, so 'neighbour activity' is on a fixed scale.

    PLAIN ENGLISH
    Without this, making the ring bigger would also make every number bigger,
    and you could not tell whether a change came from the rule or from the
    ring size.
    """
    for r in (6, 13, 20):
        assert ring_kernel(r).sum() == pytest.approx(1.0, abs=1e-12)


def test_kernel_is_a_ring_not_a_blob():
    """Peak weight at mid-radius, near-zero at the centre.

    PLAIN ENGLISH
    Caring about distance is what makes shapes that MOVE. A blob kernel gives
    you puddles that sit still.
    """
    k = ring_kernel(13)
    c = k.shape[0] // 2
    assert k[c, c] < 1e-12, "centre must be excluded"
    mid = k[c, c + 6]
    assert mid > k[c, c + 1] and mid > k[c, c + 12]


def test_kernel_is_symmetric():
    """No preferred direction from the kernel itself, or drift would be an
    artifact rather than a property of the creature."""
    k = ring_kernel(11)
    assert np.allclose(k, k[::-1, :]) and np.allclose(k, k[:, ::-1])


# --------------------------------------------------------------------- sim

def test_potential_of_empty_grid_is_zero():
    w = Lenia(growth=gaussian_growth(), size=64)
    assert np.allclose(w.potential(np.zeros((64, 64))), 0.0, atol=1e-12)


def test_potential_is_periodic():
    """Edges wrap, matching the viewer's fract() sampling.

    PLAIN ENGLISH
    The world is a doughnut: walk off one side and you come back on the other.
    If the viewer and the experiment disagreed here, a creature could live in
    one and die in the other for no reason anyone would notice.
    """
    w = Lenia(growth=gaussian_growth(), size=64, radius=8)
    a = np.zeros((64, 64))
    a[0, 0] = 1.0
    p = w.potential(a)
    assert p[0, 60] > 1e-6, "activity must wrap around the edge"


def test_state_stays_in_bounds():
    w = Lenia(growth=gaussian_growth(), size=48)
    a = seed_disc(48, 8, 0.6)
    for _ in range(50):
        a = w.step(a)
        assert a.min() >= 0.0 and a.max() <= 1.0
        assert np.all(np.isfinite(a))


def test_simulation_is_deterministic():
    """Same start, same ending. Every time.

    PLAIN ENGLISH
    If pressing play twice gave two different films, no result would mean
    anything.
    """
    def once():
        return run(Lenia(growth=gaussian_growth(), size=64),
                   seed_disc(64, 8, 0.6), steps=120)
    a, b = once(), once()
    assert (a.verdict, a.steps) == (b.verdict, b.steps)
    assert a.final_mass == b.final_mass


# ----------------------------------------------------------------- outcomes

def test_empty_grid_is_judged_dead():
    """The judge must call an empty screen dead.

    PLAIN ENGLISH
    Sounds too obvious to test. It is not: if the judge were broken the other
    way, every run would read as a success and the whole experiment would be
    meaningless.
    """
    out = run(Lenia(growth=gaussian_growth(), size=48),
              np.zeros((48, 48)), steps=50)
    assert out.verdict == "died" and not out.survived


def test_runaway_growth_is_judged_saturated():
    """A rule that only ever brightens must be caught, not scored as alive.

    PLAIN ENGLISH
    A creature that eats the whole screen has not survived -- it has broken the
    world. Counting that as success is how you get an impressive-looking result
    that means nothing.
    """
    out = run(Lenia(growth=lambda u: np.ones_like(u), size=48),
              seed_disc(48, 8, 0.5), steps=200)
    assert out.verdict == "saturated"


def test_known_survivor_still_survives():
    """GOLDEN. Measured while building the viewer: this configuration lives.

    PLAIN ENGLISH
    One setting we already know works, kept as a tripwire. If a future change
    kills it, something broke -- and we find out immediately instead of
    concluding the EML gate is bad when the bug was ours.
    """
    out = run(Lenia(growth=gaussian_growth(0.15, 0.017), size=128, radius=13),
              seed_disc(128, 8, 0.60), steps=400)
    assert out.verdict == "alive", (
        f"the known-good Gaussian configuration now reports {out.verdict!r}; "
        f"the simulator changed, not the science"
    )


def test_known_death_still_dies():
    """The other half of the tripwire.

    PLAIN ENGLISH
    A test that only checks 'the good one lives' would still pass if the judge
    called EVERYTHING alive. So we also keep one we know dies.
    """
    out = run(Lenia(growth=gaussian_growth(0.15, 0.017), size=128, radius=13),
              seed_disc(128, 10, 0.40), steps=400)
    assert out.verdict == "died"


def test_gain_is_recorded_for_survivors():
    out = run(Lenia(growth=gaussian_growth(), size=128, radius=13),
              seed_disc(128, 8, 0.60), steps=300)
    assert out.survived
    assert np.isfinite(out.gain) and out.gain > 0
    assert np.isfinite(out.mass_cv)


def test_fog_is_not_counted_as_alive():
    """THE test that changed the Rung 2 result.

    PLAIN ENGLISH
    A grid lit uniformly to a middling grey weighs the same as a small bright
    creature on a dark field. The first sweep scored 20/20 for the Erez gate
    using mass alone; inspection showed those runs had NO empty space left --
    fog, not creatures.

    A judge that cannot tell a creature from fog will happily report a
    discovery. This pins the distinction.
    """
    out = run(Lenia(growth=erez_growth(0.50, 1.0, 0.08, 1.0), size=128,
                    radius=13),
              seed_disc(128, 8, 0.60), steps=400)
    assert out.verdict == "fogged", (
        f"expected fog, got {out.verdict!r} with empty_fraction="
        f"{out.empty_fraction:.4f}; the structure check is not working"
    )
    assert out.empty_fraction < 0.5


def test_real_creature_has_background():
    """The other half: a genuine survivor must keep most of the world empty."""
    out = run(Lenia(growth=gaussian_growth(0.15, 0.017), size=128, radius=13),
              seed_disc(128, 8, 0.60), steps=400)
    assert out.verdict == "alive"
    assert out.empty_fraction > 0.9, (
        f"a real Lenia creature sits on a mostly empty grid; measured "
        f"{out.empty_fraction:.4f}"
    )
    assert out.spatial_std > 0.01, "a creature must have visible contrast"


def test_structure_check_separates_the_measured_cases():
    """Pins the measured separation that motivated the threshold.

    gaussian survivors : 81% and 99.6% of the grid near-empty
    erez fog           : 0.0% to 5.7%
    A threshold of 50% sits in a very wide gap, not on a knife edge.
    """
    gauss = run(Lenia(growth=gaussian_growth(0.13, 0.020), size=128, radius=13),
                seed_disc(128, 8, 0.60), steps=400)
    fog = run(Lenia(growth=erez_growth(0.80, 1.0, 0.08, 1.0), size=128,
                    radius=13),
              seed_disc(128, 8, 0.60), steps=400)
    assert gauss.empty_fraction > 0.7
    assert fog.empty_fraction < 0.1
    assert gauss.empty_fraction - fog.empty_fraction > 0.6, (
        "the two classes must be far apart, or the threshold is arbitrary"
    )
