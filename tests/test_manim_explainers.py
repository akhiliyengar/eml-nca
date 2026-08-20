"""Tests for the Manim explainers.

Two jobs, and the first is the important one.

1. THE NUMBERS ON THE SLIDES MUST BE TRUE.
   A teaching artifact that states a wrong figure is worse than none: it is
   memorable, confident, and repeated. Every quantitative claim in a scene is
   asserted here against a computation. This repository criticises unverified
   claims in the literature, so its own slides get checked.

2. The render must stay dependency-light.
   Scenes use Text with Unicode, never MathTex/Tex, which would pull in a
   ~1.5 GB TeX distribution and turn rendering into a toolchain problem. A
   single Tex import would silently reintroduce that.

Rendering itself is NOT tested here -- it is slow and needs ffmpeg. These are
content tests, and they run in milliseconds.
"""

from __future__ import annotations

import cmath
import re
from pathlib import Path

import numpy as np
import pytest

SCENES = Path(__file__).resolve().parents[1] / "viz" / "manim" / "explainers.py"


@pytest.fixture(scope="module")
def src() -> str:
    return SCENES.read_text(encoding="utf-8")


def test_explainers_exist():
    assert SCENES.is_file()


# ------------------------------------------------------- claims on the slides

def test_gain_compounding_claims_are_correct(src):
    """The SpectralRadius scene states 1.05^100 -> 131.5x and 0.95^100 -> 0.006.

    This is the most repeated number in the project -- it appears in the README,
    SPEC, the viewer and the journal. If it were wrong it would be wrong
    everywhere.

    An earlier version of the slide said "131 ×" and this test caught it:
    1.05^100 = 131.501258, which rounds to 132, not 131. Truncation dressed as
    rounding is a small error, and small errors in teaching material are the
    ones that get repeated verbatim.
    """
    hi, lo = 1.05**100, 0.95**100
    assert hi == pytest.approx(131.501258, rel=1e-6)
    assert lo == pytest.approx(0.005921, rel=1e-4)
    assert "131.5 ×" in src, "the slide must state the value that was verified"
    assert "0.006" in src, "0.005921 displayed to 3 dp is 0.006"


def test_spectral_radius_claim_holds_numerically(src):
    """The scene claims rho(J) decides whether J^t grows or shrinks.

    Uses the same matrix shown on the slide, so the illustration and the
    mathematics cannot drift apart.
    """
    assert "[[r, .3], [0, r/2]]" in src
    for r, expect_decay in ((0.9, True), (1.1, False)):
        jac = np.array([[r, 0.3], [0.0, r / 2]])
        rho = float(np.max(np.abs(np.linalg.eigvals(jac))))
        assert rho == pytest.approx(r, abs=1e-12)
        grown = float(np.linalg.norm(np.linalg.matrix_power(jac, 100)
                                     @ np.ones(2)))
        assert (grown < 1e-3) is expect_decay


def test_branch_cut_ulp_claim_is_measured_not_guessed(src):
    """The scene states the intermediate lands ~1.9e-15 BELOW the cut.

    That is a measurement, and it is the whole point of the scene, so it is
    re-measured here. If a platform lands on the other side this fails, which
    is exactly the signal wanted -- the same property the CI OS matrix guards.
    """
    inner = cmath.exp(cmath.e - cmath.log(-1.0))
    assert inner.real < 0, "intermediate should sit on the negative real axis"
    assert inner.imag < 0, "expected the lucky side of the cut"
    assert abs(inner.imag) < 1e-13, "and essentially ON the cut"
    assert f"{abs(inner.imag):.1e}".startswith("1.9"), (
        f"scene claims 1.9e-15, measured {abs(inner.imag):.3e}"
    )
    assert "1.9 × 10⁻¹⁵" in src and "8 ULPs" in src


def test_ulp_count_claim(src):
    """'about 8 ULPs' must be arithmetic, not a vibe."""
    inner = cmath.exp(cmath.e - cmath.log(-1.0))
    ulp = np.spacing(abs(inner.real))
    n = abs(inner.imag) / ulp
    assert 1 <= n <= 64, f"measured {n:.1f} ULPs; the slide says about 8"


def test_sheffer_identities_shown_are_real(src):
    """The ShefferStroke scene shows three EML reductions. All must hold."""
    assert "eml(1, 1)" in src and "eml(x, 1)" in src
    assert "eml(1, eml(eml(1,z), 1))" in src

    def eml(x, y):
        return cmath.exp(x) - cmath.log(y)

    assert abs(eml(1, 1) - cmath.e) < 1e-15
    assert abs(eml(2.0, 1) - cmath.exp(2.0)) < 1e-12
    z = 3.7
    assert abs(eml(1, eml(eml(1, z), 1)) - cmath.log(z)) < 1e-12


# ------------------------------------------------------------- dependencies

def test_no_latex_dependency(src):
    """No MathTex/Tex CONSTRUCTION anywhere.

    One import would reintroduce a ~1.5 GB TeX toolchain and turn rendering
    into a toolchain problem rather than a content problem.

    Checks executable lines only: the module docstring legitimately names
    MathTex while explaining why it is avoided, and an earlier version of this
    test flagged that explanation. Same false positive as the viewer's
    Math.random check -- documentation that mentions a banned pattern is not a
    use of it.
    """
    code = re.sub(r'(?s)""".*?"""', "", src)      # drop docstrings
    code = re.sub(r"#.*", "", code)               # drop comments
    for banned in ("MathTex", "Tex(", "TexTemplate", "SingleStringMathTex"):
        assert banned not in code, f"{banned} reintroduces the LaTeX dependency"
    assert "Text(" in code, "scenes should use Text with Unicode"


def test_scene_registry_matches_defined_classes(src):
    """SCENES is the documented list; drift makes the docstring a lie."""
    defined = set(re.findall(r"^class (\w+)\(Scene\):", src, re.MULTILINE))
    listed = set(re.findall(r'^\s+"(\w+)": "', src, re.MULTILINE))
    assert defined == listed, (
        f"defined={sorted(defined)} but registry lists {sorted(listed)}"
    )
    assert len(defined) >= 3


def test_render_commands_in_docstring_name_real_scenes(src):
    defined = set(re.findall(r"^class (\w+)\(Scene\):", src, re.MULTILINE))
    for named in re.findall(r"explainers\.py (\w+)", src):
        assert named in defined, f"docstring renders {named}, which does not exist"


def test_media_output_is_not_committed():
    """Videos are regenerable and would bloat the repository."""
    root = Path(__file__).resolve().parents[1]
    ignore = (root / ".gitignore").read_text(encoding="utf-8")
    assert "media/" in ignore, "media/ must be gitignored"
