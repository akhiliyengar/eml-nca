"""Gray-Scott reaction-diffusion: the Rung 1 ground truth.

    du/dt = Du * lap(u) - u*v^2 + F*(1 - u)
    dv/dt = Dv * lap(v) + u*v^2 - (F + k)*v

Chosen as the first rung precisely because it is the experiment most likely to
FAIL. The reaction term contains u*v^2 -- a cross-variable interaction, which
Asanuma (arXiv:2606.05942) documents as the specific weakness of the
univariate-additive EML form: "cannot represent cross-variable interactions".

Running the least likely experiment first is deliberate. It costs a day, it is
a real control, and it calibrates what failure looks like in this codebase
before a month is invested. Starting with Rung 2 (highest prior) would mean the
first result is a success with no failure calibration.

Turing's 1952 question: how does a chemically uniform embryo develop spots and
stripes? A slow-diffusing activator with a fast-diffusing inhibitor makes
uniformity unstable, so structure must appear. Reaction-diffusion is where that
is made concrete.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

# Classic parameter sets. Names follow the Pearson (1993) classification.
PRESETS: dict[str, tuple[float, float]] = {
    "solitons": (0.030, 0.062),
    "coral": (0.0545, 0.062),
    "mitosis": (0.0367, 0.0649),
    "spots": (0.035, 0.065),
    "worms": (0.078, 0.061),
}


@dataclass(frozen=True)
class GrayScott:
    """Immutable parameter set. Frozen so a config cannot drift mid-run."""

    F: float = 0.035
    k: float = 0.065
    Du: float = 0.16
    Dv: float = 0.08
    dt: float = 1.0

    @classmethod
    def preset(cls, name: str, **kw) -> GrayScott:
        if name not in PRESETS:
            raise KeyError(f"unknown preset {name!r}; have {sorted(PRESETS)}")
        f, k = PRESETS[name]
        return cls(F=f, k=k, **kw)

    # -- the terms we will try to recover symbolically -------------------

    def reaction_u(self, u: np.ndarray, v: np.ndarray) -> np.ndarray:
        """-u*v^2 + F*(1 - u).

        THE TARGET. Two structurally different pieces:
          u*v^2      cross-variable, degree 3   <- the hard part
          F*(1 - u)  affine in u alone          <- trivial for any basis
        """
        return -u * v * v + self.F * (1.0 - u)

    def reaction_v(self, u: np.ndarray, v: np.ndarray) -> np.ndarray:
        """u*v^2 - (F + k)*v"""
        return u * v * v - (self.F + self.k) * v

    # -- simulation -----------------------------------------------------

    @staticmethod
    def laplacian(a: np.ndarray) -> np.ndarray:
        """5-point stencil with periodic wrap.

        np.roll rather than convolution: no dependency, and the operation order
        is fixed, which matters because determinism is an invariant here.
        """
        return (
            np.roll(a, 1, 0) + np.roll(a, -1, 0)
            + np.roll(a, 1, 1) + np.roll(a, -1, 1)
            - 4.0 * a
        )

    def step(self, u: np.ndarray, v: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        du = self.Du * self.laplacian(u) + self.reaction_u(u, v)
        dv = self.Dv * self.laplacian(v) + self.reaction_v(u, v)
        return u + self.dt * du, v + self.dt * dv

    def run(
        self, n: int = 96, steps: int = 2000, seed: int = 0, seed_size: int = 10
    ) -> tuple[np.ndarray, np.ndarray]:
        """Simulate to a patterned state.

        Starts from u=1, v=0 with a small perturbed square, which is the
        standard initialisation: the uniform state is unstable, so the
        perturbation is what lets Turing structure grow.
        """
        rng = np.random.default_rng(seed)
        u = np.ones((n, n), dtype=np.float64)
        v = np.zeros((n, n), dtype=np.float64)
        c = n // 2
        s = seed_size // 2
        u[c - s:c + s, c - s:c + s] = 0.50
        v[c - s:c + s, c - s:c + s] = 0.25
        u += 0.01 * rng.standard_normal((n, n))
        v += 0.01 * rng.standard_normal((n, n))
        np.clip(u, 0.0, 1.0, out=u)
        np.clip(v, 0.0, 1.0, out=v)
        for _ in range(steps):
            u, v = self.step(u, v)
        return u, v


def sample_domain(
    n: int = 4096, seed: int = 0, u_range=(0.0, 1.0), v_range=(0.0, 0.5)
) -> tuple[np.ndarray, np.ndarray]:
    """Uniform (u, v) samples for fitting the reaction term.

    Deliberately samples the DOMAIN rather than a trajectory. A trajectory
    concentrates on the attractor, which would let a fit look excellent while
    having learned only the region the system happens to occupy -- flattering,
    and not a test of whether the functional form was recovered.

    v is capped at 0.5 because Gray-Scott v stays well below 1 in the patterned
    regime; sampling v up to 1 would test the fit far outside the region the
    dynamics ever visit.
    """
    rng = np.random.default_rng(seed)
    u = rng.uniform(*u_range, size=n)
    v = rng.uniform(*v_range, size=n)
    return u, v


def split_domain(
    n: int = 4000, seed: int = 0, v_cut: float = 0.35, v_max: float = 0.5
) -> tuple[tuple[np.ndarray, np.ndarray], tuple[np.ndarray, np.ndarray]]:
    """Interpolation / extrapolation split on v.

    THE decisive test for symbolic recovery, and the one a plain relMSE misses.

    Any sufficiently rich smooth basis can fit a smooth target on a bounded
    domain to small error -- that is approximation, not recovery. The question
    is whether the FUNCTIONAL FORM was recovered, and the way to tell is to fit
    on v in [0, v_cut] and evaluate on v in [v_cut, v_max].

    A basis that genuinely contains u*v^2 extrapolates with unchanged error.
    A basis that merely approximated it on the training band diverges, because
    exponentials, logarithms and sinusoids fitted to a cubic agree locally and
    part company immediately outside.

    Returns ((u_fit, v_fit), (u_test, v_test)).
    """
    rng = np.random.default_rng(seed)
    u_fit = rng.uniform(0.0, 1.0, size=n)
    v_fit = rng.uniform(0.0, v_cut, size=n)
    u_test = rng.uniform(0.0, 1.0, size=n)
    v_test = rng.uniform(v_cut, v_max, size=n)
    return (u_fit, v_fit), (u_test, v_test)
