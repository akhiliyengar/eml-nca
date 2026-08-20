"""Tests for the WebGL Lenia viewer.

The risk this file exists for is DRIFT. The growth functions are implemented
twice -- once in Python (`emlnca.ops.erez_gate`) for experiments, once in GLSL
for the viewer. If they diverge, the picture stops describing the measurement,
and a visualisation that quietly disagrees with the data is worse than no
visualisation: it produces confident wrong intuition.

These are structural checks on the shader source, not a GLSL interpreter. They
catch the realistic failure -- someone edits one implementation and not the
other -- without pretending to execute the shader.
"""

from __future__ import annotations

import re
from pathlib import Path

import numpy as np
import pytest

from emlnca.ops import erez_gate, erez_peak

VIZ = Path(__file__).resolve().parents[1] / "viz" / "three"
JS = VIZ / "lenia.js"
HTML = VIZ / "index.html"


@pytest.fixture(scope="module")
def js() -> str:
    return JS.read_text(encoding="utf-8")


def test_viewer_files_exist():
    assert HTML.is_file() and JS.is_file()


def test_no_build_step_required(js):
    """The viewer must run from `python -m http.server` with no toolchain.

    A visualisation behind a build step gets looked at once. This one is raw
    WebGL2 with no runtime download, so it also works offline and cannot rot
    when a CDN changes.
    """
    assert "webgl2" in js
    assert "import " not in js.split("/*")[0], "no bare module imports"
    assert not (VIZ / "package.json").exists(), "no npm dependency tree"


def test_erez_gate_glsl_matches_the_python_formula(js):
    """G(x) = (c + x)^a - b*x - c^a, in both implementations.

    Structural rather than numerical: the three terms must all be present with
    the right operators. A dropped `- c^a` would shift the quiescent state and
    slowly inflate the whole field, which looks like a subtle visual artefact
    rather than a bug.
    """
    body = re.search(r"float growthErez\(float x\)\s*\{(.*?)\n\}", js, re.DOTALL)
    assert body, "growthErez not found in the shader source"
    src = body.group(1)

    assert "pow(base, uA)" in src, "missing the (c+x)^a activation term"
    assert "uB * x" in src, "missing the -b*x suppression term"
    assert re.search(r"pow\(max\(uC[^)]*\)[^)]*, uA\)", src), \
        "missing the -c^a centering term"
    assert "max(uC + x, 0.0)" in src, "base must be clamped at 0 before pow"


def test_python_gate_has_the_same_three_terms():
    """Anchors the structural test above to executable behaviour.

    Verified numerically:  G(0) = 0  (centering works)
                           G has an interior maximum  (non-monotone)
                           peak matches (a/b)^(1/(1-a))
    """
    a, b, c = 0.5, 0.3, 0.02
    assert erez_gate(np.array([0.0]), a, b, c)[0] == pytest.approx(0.0, abs=1e-12)

    x = np.linspace(0.0, 8.0, 4001)
    g = erez_gate(x, a, b, 0.0)
    peak = x[int(np.argmax(g))]
    assert 0 < int(np.argmax(g)) < len(x) - 1, "gate must be non-monotone"
    assert peak == pytest.approx(erez_peak(a, b), rel=1e-2)


def test_gaussian_control_is_present(js):
    """The control must not be quietly removed.

    Without a baseline in the same viewer, any EML result is unfalsifiable by
    eye -- which is how a demo replaces an experiment.
    """
    assert "float growthGaussian(float u)" in js
    assert "2.0 * exp(-0.5 * x * x) - 1.0" in js
    assert 'el(\'bGauss\')' in js and 'el(\'bErez\')' in js


def test_seeding_is_deterministic(js):
    """No Math.random INVOCATION anywhere.

    Determinism is an invariant in this project. A viewer whose initial state
    cannot be reproduced cannot be cited, and "it looked stable when I ran it"
    is not evidence.

    Checks for the call `Math.random(` rather than the bare string: the source
    legitimately mentions Math.random in a comment explaining why it is not
    used, and an earlier version of this test flagged its own documentation.
    """
    assert "Math.random(" not in js, "viewer must not call Math.random()"
    assert "1103515245" in js, "expected the deterministic LCG seed generator"


def test_boundary_is_periodic(js):
    """fract() on the sampled coordinate, matching the Python laplacian's
    np.roll wrap. A viewer with reflecting edges would show different
    long-horizon behaviour from the experiments."""
    assert "fract(uv + o)" in js


def test_gain_readout_exists(js):
    """Gain decides survival: 1.05^100 is 131x, 0.95^100 is 0.006. The viewer
    must show it, or judging 'does Orbium survive' becomes guesswork."""
    assert "rgain" in js and "massHist" in js
    assert "DIED" in js and "SATURATED" in js


def test_shader_sources_are_balanced(js):
    """Cheap syntax guard. A malformed shader fails at runtime in the browser
    with no CI signal, so catch the common case here."""
    for name in ("STEP", "SHOW", "VERT"):
        m = re.search(rf"const {name} = `(.*?)`;", js, re.DOTALL)
        assert m, f"shader {name} not found"
        src = m.group(1)
        assert src.count("{") == src.count("}"), f"{name} has unbalanced braces"
        assert src.count("(") == src.count(")"), f"{name} has unbalanced parens"
        assert "void main()" in src, f"{name} has no entry point"
        assert src.lstrip().startswith("#version 300 es"), \
            f"{name} must declare GLSL ES 3.00"


def test_html_references_the_module(js):
    html = HTML.read_text(encoding="utf-8")
    assert './lenia.js' in html
    for control in ("mu", "sig", "a", "b", "c", "R", "dt"):
        assert f'id="{control}"' in html, f"missing control {control!r}"
        assert f"'{control}'" in js, f"control {control!r} unused in js"
