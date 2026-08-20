"""Lenia with a pluggable growth function -- the Rung 2 target.

PLAIN ENGLISH
-------------
Lenia is a game where every dot on a grid looks at its neighbours and decides
whether to get brighter or dimmer. One rule, applied everywhere, over and over.
Do it right and shapes appear that crawl around like little animals.

The rule has two halves:

    kernel  "which neighbours do I look at, and how much do I care?"
    growth  "given what I saw, do I brighten or dim?"

This file keeps the kernel fixed and lets you swap the growth half, because
that is the whole experiment: Lenia's usual growth function is a bell curve,
and Erez's EML gate is a different shape that does the same job with fewer
knobs. We want to know whether the swap keeps the animals alive.

WHY THIS IS RUNG 2
------------------
Rung 1 failed for a reason that does not apply here. It needed u*v^2 -- two
variables multiplied -- and the univariate-additive EML form cannot express
that. Lenia's growth function takes ONE number in and gives ONE number out, so
the weakness that sank Rung 1 is simply absent.

It is also the one place the literature genuinely supports. Erez
(arXiv:2605.02972) shows his gate is non-monotone -- it rises, peaks, then
falls -- in a single 3-parameter block, where a bell curve or Hill function
needs two opposed blocks. Lenia's growth function is exactly a rise-then-fall
shape. This is the closest match between claim and target in the whole corpus.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Literal

import numpy as np
from numpy.fft import irfft2, rfft2

GrowthFn = Callable[[np.ndarray], np.ndarray]


# ---------------------------------------------------------------- growth fns

def gaussian_growth(mu: float = 0.15, sigma: float = 0.017) -> GrowthFn:
    """THE CONTROL. Standard Lenia growth: a bell curve mapped to [-1, 1].

    PLAIN ENGLISH
    A cell is happy only when it has *just the right* amount of neighbour
    activity -- not too little, not too much. Like porridge temperature. Get it
    right and the cell brightens; wrong in either direction and it dims.

    WHY IT IS THE CONTROL
    This is what Lenia normally uses, so it is the thing to beat. Without it in
    the same table, "the EML gate kept the pattern alive" is unfalsifiable --
    you would have no idea whether that is good, bad, or what always happens.
    A result with no baseline is not a result.
    """
    def g(u: np.ndarray) -> np.ndarray:
        return 2.0 * np.exp(-0.5 * ((u - mu) / sigma) ** 2) - 1.0
    return g


def erez_growth(
    a: float = 0.5, b: float = 0.3, c: float = 0.02, scale: float = 1.0
) -> GrowthFn:
    """THE TREATMENT. Erez's centered gate, arXiv:2605.02972 eq. 6.

        G(x) = (c + x)^a - b*x - c^a

    PLAIN ENGLISH
    Two forces pulling against each other. The first term is "more neighbours,
    more growth", but it gets tired as it rises (that is what the power a < 1
    does -- doubling the input less than doubles the output). The second term
    is a steady penalty that grows in a straight line. Early on the first wins;
    later the penalty catches up and overtakes it. So the curve goes up, turns
    over, and comes down.

    The -c^a bit is bookkeeping: it makes G(0) exactly 0 so that empty space
    stays empty. Without it every blank cell would drift upward a little each
    step and the whole grid would slowly fog over.

    WHY IT MIGHT WIN
    It reaches the same rise-then-fall shape with 3 knobs where a bell curve
    plus its opposite needs 6. Fewer knobs means fewer things to tune and fewer
    ways to fool yourself.
    """
    c_off = np.power(max(c, 1e-9), a)

    def g(x: np.ndarray) -> np.ndarray:
        base = np.maximum(c + x, 0.0)
        return np.clip(scale * (np.power(base, a) - b * x - c_off), -1.0, 1.0)
    return g


def erez_offset_growth(
    a: float = 0.25, b: float = 1.0, c: float = 0.02,
    scale: float = 1.0, theta: float = 0.1,
) -> GrowthFn:
    """Erez's gate MINUS a constant. The one-parameter repair.

        G(x) = (c + x)^a - b*x - c^a - theta

    PLAIN ENGLISH
    Erez's gate never goes below zero, so empty space just sits there and any
    stray brightness slowly fills the whole grid. Subtracting a small constant
    pushes the whole curve down, so faint areas now actively fade. That one
    change is the difference between fog and creatures.

    WHY THIS EXISTS
    Measured, not guessed. The published gate scored 0 survivors across 120
    configurations x 20 seeds. Inspecting growth at low activity showed why:

        gaussian at u=0.001  ->  -1.0000   (empty space dies, hard)
        erez     at u=0.001  ->  +0.0036   (empty space GROWS)

    The gate is non-negative everywhere on the positive domain. It does rise
    and fall -- the peak is real -- but the falling part never crosses zero,
    and Lenia needs it to. Subtracting theta and re-running gives 20/20.

    NOTE ON THE PARSIMONY CLAIM
    This makes it four shape parameters (a, b, c, theta) against the Gaussian's
    two (mu, sigma). Erez's "3 knobs instead of 6" was measured against HILL
    functions, which are monotone and genuinely need two opposed blocks for a
    rise-then-fall. Lenia's Gaussian bump is ALREADY non-monotone with two
    parameters, so that comparison does not transfer to this target.
    """
    base = erez_growth(a, b, c, scale)

    def g(x: np.ndarray) -> np.ndarray:
        return np.clip(base(x) - theta, -1.0, 1.0)
    return g


GROWTH_KINDS = Literal["gaussian", "erez", "erez_offset"]


def make_growth(kind: GROWTH_KINDS, **kw) -> GrowthFn:
    if kind == "gaussian":
        return gaussian_growth(**kw)
    if kind == "erez":
        return erez_growth(**kw)
    if kind == "erez_offset":
        return erez_offset_growth(**kw)
    raise ValueError(f"unknown growth kind {kind!r}")


# -------------------------------------------------------------------- kernel

def ring_kernel(radius: int = 13, peak: float = 0.5, width: float = 0.15):
    """A donut, not a blob.

    PLAIN ENGLISH
    Each cell cares most about neighbours at a particular DISTANCE -- not the
    ones touching it, and not the far-away ones. A ring, like standing in a
    circle holding hands with people one arm's length away.

    WHY A RING AND NOT A BLOB
    Caring about distance is what makes shapes that MOVE. If a cell just added
    up everything nearby, blobs would grow or shrink and sit still. The ring is
    the continuous version of Conway's "exactly 2 or 3 neighbours" rule, and
    rules like that are where gliders come from.
    """
    y, x = np.mgrid[-radius:radius + 1, -radius:radius + 1]
    r = np.hypot(x, y) / radius
    k = np.exp(-0.5 * ((r - peak) / width) ** 2)
    k[r > 1.0] = 0.0
    k[r < 1e-9] = 0.0
    total = k.sum()
    if total <= 0:
        raise ValueError("degenerate kernel")
    return k / total


# ---------------------------------------------------------------------- sim

@dataclass
class Lenia:
    """One Lenia world.

    PLAIN ENGLISH
    Holds the grid, the "who do I look at" ring, and the "should I brighten"
    rule. Call step() to advance time.
    """

    growth: GrowthFn
    radius: int = 13
    dt: float = 0.1
    size: int = 128
    _kfft: np.ndarray | None = field(default=None, repr=False)

    def kernel_fft(self) -> np.ndarray:
        """Precomputed so each step is one FFT pair instead of a nested loop.

        PLAIN ENGLISH
        Adding up every neighbour for every cell is slow. There is a maths
        trick (the Fourier transform) that does the whole grid at once. We
        prepare the trick once and reuse it every step.
        """
        if self._kfft is None:
            k = ring_kernel(self.radius)
            pad = np.zeros((self.size, self.size))
            s = k.shape[0] // 2
            pad[:k.shape[0], :k.shape[1]] = k
            pad = np.roll(pad, (-s, -s), axis=(0, 1))
            self._kfft = rfft2(pad)
        return self._kfft

    def potential(self, a: np.ndarray) -> np.ndarray:
        """How much neighbour activity each cell sees. Wraps at the edges."""
        return irfft2(rfft2(a) * self.kernel_fft(), a.shape)

    def step(self, a: np.ndarray) -> np.ndarray:
        return np.clip(a + self.dt * self.growth(self.potential(a)), 0.0, 1.0)


# --------------------------------------------------------------------- seeds

def seed_disc(size: int, radius: float, amp: float,
              shell: float = 0.55, width: float = 0.28) -> np.ndarray:
    """A soft ring of brightness in the middle of an empty grid.

    PLAIN ENGLISH
    Where the creature starts. A fuzzy donut of "on" cells.

    WHY THE EXACT NUMBERS MATTER MORE THAN YOU EXPECT
    Measured while building the viewer: radius 8 amplitude 0.50 dies at step
    22, but amplitude 0.60 lives past 400. Radius 10 dies for every amplitude
    tried. The set of starting shapes that survive is TINY. So an experiment
    must try many seeds -- otherwise "the EML gate killed it" is
    indistinguishable from "that particular seed was doomed anyway".
    """
    a = np.zeros((size, size))
    c = size // 2
    y, x = np.mgrid[0:size, 0:size]
    r = np.hypot(x - c, y - c) / radius
    m = r < 1.0
    a[m] = amp * np.exp(-((r[m] - shell) / width) ** 2)
    return np.clip(a, 0.0, 1.0)


# ------------------------------------------------------------------ outcomes

DEATH_MASS = 1e-7
SATURATION_MASS = 0.55

# A living creature needs BACKGROUND. This threshold exists because the first
# Rung 2 sweep reported 20/20 survivors for the Erez gate, which was false.
#
# PLAIN ENGLISH
# Those runs had not produced creatures. They had produced fog: the entire grid
# lit up to a middling grey, with literally no empty space left (measured
# fraction of near-empty cells: 0.0000). Mass alone could not tell that apart
# from a bright creature on a dark field, because a half-lit grid and a small
# bright blob can weigh the same.
#
# Measured separation is clean:
#     gaussian survivors  81% and 99.6% of the grid near-empty
#     erez "survivors"    0.0% to 5.7%
#
# So: at least half the world must still be background.
MIN_EMPTY_FRACTION = 0.50
EMPTY_LEVEL = 0.01


@dataclass
class Outcome:
    """What happened to one world.

    PLAIN ENGLISH
        died       everything faded to nothing
        saturated  everything filled up; the grid is a solid block
        fogged     no empty space left -- a uniform haze, not a creature
        alive      still going, still a recognisable SHAPE on a background
    """

    verdict: Literal["alive", "died", "saturated", "fogged"]
    steps: int
    final_mass: float
    gain: float
    mass_cv: float
    empty_fraction: float = 0.0
    spatial_std: float = 0.0

    @property
    def survived(self) -> bool:
        return self.verdict == "alive"


def run(
    world: Lenia, seed_state: np.ndarray, steps: int = 1000, warmup: int = 100
) -> Outcome:
    """Advance the world and judge the result.

    PLAIN ENGLISH
    Press play, watch, and write down whether the creature lived, vanished, or
    swallowed the screen.

    WHY GAIN IS MEASURED
    Gain is "how much bigger did it get each step, on average". Not a detail:
    a rule applied 1000 times with gain 1.05 multiplies things by 131.5, and
    with 0.95 shrinks them to 0.0059. Almost nothing lands in between, so gain
    is the number that decides life or death.

    WHY STRUCTURE IS CHECKED, NOT JUST MASS
    A grid uniformly lit to a middling grey weighs the same as a small bright
    creature on a dark field. The first Rung 2 sweep scored 20/20 for the Erez
    gate on mass alone; inspection showed those runs had NO empty space at all.
    Fog, not creatures. So "alive" now also requires that at least half the
    world is still background.
    """
    a = seed_state.copy()
    masses: list[float] = []
    for i in range(steps):
        a = world.step(a)
        m = float(a.mean())
        masses.append(m)
        if m < DEATH_MASS:
            return Outcome("died", i + 1, m, 0.0, 0.0)
        if m > SATURATION_MASS:
            return Outcome("saturated", i + 1, m, float("inf"), 0.0)

    empty = float((a < EMPTY_LEVEL).mean())
    sstd = float(a.std())

    tail = np.asarray(masses[warmup:]) if len(masses) > warmup else np.asarray(masses)
    gain = float((tail[-1] / tail[0]) ** (1.0 / max(len(tail) - 1, 1))) \
        if tail[0] > 0 else 0.0
    cv = float(np.std(tail) / np.mean(tail)) if np.mean(tail) > 0 else 0.0

    if empty < MIN_EMPTY_FRACTION:
        return Outcome("fogged", steps, float(masses[-1]), gain, cv, empty, sstd)
    return Outcome("alive", steps, float(masses[-1]), gain, cv, empty, sstd)
