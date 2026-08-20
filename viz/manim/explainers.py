"""Concept explainers for the EML/NCA study.

DELIBERATELY NO LaTeX. Every label uses `Text` with Unicode rather than
`MathTex`/`Tex`, which would pull in a ~1.5 GB TeX distribution and make the
render a toolchain problem instead of a content problem. The formulas here are
simple enough that Unicode carries them.

Each scene answers the same four questions, in this order:
  1. what problem does this solve, and why does that problem matter
  2. where else does the idea appear
  3. what is the visual intuition to remember
  4. how would you reproduce it yourself

Render:
    manim -ql viz/manim/explainers.py ShefferStroke
    manim -ql viz/manim/explainers.py BranchCut
    manim -ql viz/manim/explainers.py SpectralRadius

-ql is 480p and fast; -qh for 1080p. Output lands in media/, which is
gitignored -- videos are regenerable and would bloat the repository.
"""

from __future__ import annotations

import numpy as np
from manim import (
    DOWN,
    GREEN,
    GREY,
    LEFT,
    ORANGE,
    RED,
    RIGHT,
    UP,
    WHITE,
    YELLOW,
    Arrow,
    Axes,
    Circle,
    Create,
    Dot,
    FadeIn,
    FadeOut,
    Line,
    Scene,
    Text,
    VGroup,
    Write,
)

BG = "#0b0e14"
ACCENT = "#4fd1c5"
DIM = "#7c8ba1"


def title(text: str, sub: str = "") -> VGroup:
    t = Text(text, font_size=40, color=WHITE)
    if not sub:
        return VGroup(t)
    s = Text(sub, font_size=22, color=DIM)
    s.next_to(t, DOWN, buff=0.25)
    return VGroup(t, s)


class ShefferStroke(Scene):
    """Why 'one primitive generates everything' is an engineering result.

    The takeaway is NOT that EML is clever. It is that universality converts a
    design problem into a manufacturing problem -- which is why a chip fab
    perfects one gate geometry and builds everything from it.
    """

    def construct(self):
        self.camera.background_color = BG

        head = title("A single primitive",
                     "functional completeness, and why industry cares")
        self.play(Write(head))
        self.wait(1.5)
        self.play(head.animate.scale(0.55).to_edge(UP))

        problem = Text(
            "Problem: choose the primitives for a system.\n"
            "Too many and it is bloated, hard to reason about, hard to build.",
            font_size=24, color=WHITE, line_spacing=1.2,
        )
        self.play(FadeIn(problem))
        self.wait(2.5)
        self.play(FadeOut(problem))

        # Boolean side: NAND
        nand = Text("NAND", font_size=32, color=ACCENT)
        nand_sub = Text("Sheffer, 1913", font_size=18, color=DIM)
        nand_sub.next_to(nand, DOWN, buff=0.15)
        boolean = VGroup(nand, nand_sub).shift(LEFT * 3.2 + UP * 0.6)

        derived = VGroup(*[
            Text(s, font_size=22, color=WHITE)
            for s in ("AND", "OR", "NOT", "XOR")
        ]).arrange(DOWN, buff=0.3).shift(LEFT * 3.2 + DOWN * 1.6)

        self.play(FadeIn(boolean))
        arrows = VGroup(*[
            Arrow(nand.get_bottom() + DOWN * 0.45, d.get_left() + LEFT * 0.1,
                  buff=0.1, stroke_width=2, color=GREY)
            for d in derived
        ])
        self.play(Create(arrows), FadeIn(derived))
        self.wait(1.5)

        # Continuous side: EML
        eml = Text("eml(x,y) = eˣ − ln y", font_size=28, color=ORANGE)
        eml_sub = Text("Odrzywołek, 2026", font_size=18, color=DIM)
        eml_sub.next_to(eml, DOWN, buff=0.15)
        cont = VGroup(eml, eml_sub).shift(RIGHT * 3.0 + UP * 0.6)

        derived2 = VGroup(*[
            Text(s, font_size=22, color=WHITE)
            for s in ("sin, cos", "√, log", "π, e, i", "×, ÷, ^")
        ]).arrange(DOWN, buff=0.3).shift(RIGHT * 3.0 + DOWN * 1.6)

        self.play(FadeIn(cont))
        arrows2 = VGroup(*[
            Arrow(eml.get_bottom() + DOWN * 0.45, d.get_left() + LEFT * 0.1,
                  buff=0.1, stroke_width=2, color=GREY)
            for d in derived2
        ])
        self.play(Create(arrows2), FadeIn(derived2))
        self.wait(2)

        self.play(*[FadeOut(m) for m in
                    (boolean, derived, arrows, cont, derived2, arrows2)])

        why = Text(
            "Why it matters:\n"
            "universality turns a DESIGN problem into a MANUFACTURING problem.\n"
            "A fab perfects one gate geometry, then builds any circuit from it.",
            font_size=24, color=WHITE, line_spacing=1.2,
        )
        self.play(FadeIn(why))
        self.wait(3)
        self.play(FadeOut(why))

        elsewhere = Text(
            "Where else:  S and K combinators · SUBLEQ · FRACTRAN\n"
            "Rule 110 · the aperiodic 'einstein' monotile\n\n"
            "Same move every time: collapse a toolkit into one reusable atom.",
            font_size=22, color=DIM, line_spacing=1.2,
        )
        self.play(FadeIn(elsewhere))
        self.wait(3)
        self.play(FadeOut(elsewhere))

        repro = VGroup(
            Text("Reproduce it in 30 seconds:", font_size=24, color=ACCENT),
            Text("eml = lambda x, y: cmath.exp(x) - cmath.log(y)",
                 font_size=22, color=WHITE),
            Text("eml(1, 1)                 →  e", font_size=20, color=DIM),
            Text("eml(x, 1)                 →  eˣ", font_size=20, color=DIM),
            Text("eml(1, eml(eml(1,z), 1))  →  ln z", font_size=20, color=DIM),
        ).arrange(DOWN, buff=0.32, aligned_edge=LEFT)
        self.play(FadeIn(repro))
        self.wait(4)


class BranchCut(Scene):
    """The ln(-1) knife edge, found by writing a test rather than by reading.

    The paper reports an outright sign error. The truth is more interesting:
    the intermediate lands ~8 ULPs on the lucky side of the cut, so the answer
    is correct by a margin a different libm could erase.
    """

    def construct(self):
        self.camera.background_color = BG

        head = title("Branch cuts", "why ln(−1) is 8 ULPs from being wrong")
        self.play(Write(head))
        self.wait(1.5)
        self.play(head.animate.scale(0.55).to_edge(UP))

        problem = Text(
            "Problem: ln(−1) has infinitely many values: iπ, 3iπ, −iπ, …\n"
            "Pick one by convention — the 'principal branch'.\n"
            "That choice creates a CUT where the function jumps by 2πi.",
            font_size=23, color=WHITE, line_spacing=1.2,
        )
        self.play(FadeIn(problem))
        self.wait(3.5)
        self.play(FadeOut(problem))

        # complex plane with the cut on the negative real axis
        ax = Axes(x_range=[-3, 3, 1], y_range=[-2, 2, 1],
                  x_length=7, y_length=4,
                  axis_config={"color": GREY, "stroke_width": 2})
        cut = Line(ax.c2p(-3, 0), ax.c2p(0, 0), color=RED, stroke_width=6)
        cut_lbl = Text("branch cut", font_size=18, color=RED)
        cut_lbl.next_to(cut, UP, buff=0.15)
        self.play(Create(ax), Create(cut), FadeIn(cut_lbl))

        above = Dot(ax.c2p(-1.5, 0.12), color=GREEN, radius=0.08)
        below = Dot(ax.c2p(-1.5, -0.12), color=YELLOW, radius=0.08)
        a_lbl = Text("just above  →  +iπ", font_size=18, color=GREEN)
        b_lbl = Text("just below  →  −iπ", font_size=18, color=YELLOW)
        a_lbl.next_to(above, UP + LEFT, buff=0.2)
        b_lbl.next_to(below, DOWN + LEFT, buff=0.2)
        self.play(FadeIn(above), FadeIn(a_lbl))
        self.play(FadeIn(below), FadeIn(b_lbl))
        self.wait(2.5)

        self.play(*[FadeOut(m) for m in (ax, cut, cut_lbl, above, below,
                                         a_lbl, b_lbl)])

        finding = Text(
            "What the test found:\n\n"
            "The EML ln identity computes  e − log(e^e / z).\n"
            "For z < 0 that intermediate lands ON the cut —\n"
            "measured at 1.9 × 10⁻¹⁵ BELOW it, about 8 ULPs.\n\n"
            "The double negation cancels back to the correct answer.\n"
            "A different libm, rounding mode or FMA could flip it.",
            font_size=22, color=WHITE, line_spacing=1.15,
        )
        self.play(FadeIn(finding))
        self.wait(5)
        self.play(FadeOut(finding))

        intuition = Text(
            "Intuition: a spiral staircase.\n"
            "Walk once around the origin and you are on a different floor,\n"
            "not back where you started. The cut is where you slice it flat —\n"
            "and anything crossing teleports one storey.",
            font_size=23, color=WHITE, line_spacing=1.2,
        )
        self.play(FadeIn(intuition))
        self.wait(4)
        self.play(FadeOut(intuition))

        elsewhere = Text(
            "Where else:  every √ in a simulation · arctan2 in robotics\n"
            "phase unwrapping in radar · why sqrt(−1) differs across languages\n\n"
            "Reproduce:  print(cmath.exp(cmath.e - cmath.log(-1.0)).imag)\n"
            "            → −1.86e−15   (the lucky side)",
            font_size=21, color=DIM, line_spacing=1.2,
        )
        self.play(FadeIn(elsewhere))
        self.wait(4)


class SpectralRadius(Scene):
    """Why one number decides whether an NCA pattern lives or dies.

    This is the concept the whole project rests on: gain compounds, and it
    compounds fast enough that there is essentially no middle ground.
    """

    def construct(self):
        self.camera.background_color = BG

        head = title("Spectral radius",
                     "the number that decides if a pattern survives")
        self.play(Write(head))
        self.wait(1.5)
        self.play(head.animate.scale(0.55).to_edge(UP))

        problem = Text(
            "Problem: a system updates itself over and over:  x ← f(x).\n"
            "Does it settle, blow up, or oscillate forever?\n"
            "For nonlinear f this is generally undecidable in closed form.",
            font_size=23, color=WHITE, line_spacing=1.2,
        )
        self.play(FadeIn(problem))
        self.wait(3.5)
        self.play(FadeOut(problem))

        trick = Text(
            "Near a fixed point, replace f by its derivative matrix J:\n\n"
            "        δx(t)  ≈  Jᵗ · δx(0)\n\n"
            "Growth is decided entirely by ρ(J) = largest |eigenvalue|.",
            font_size=24, color=WHITE, line_spacing=1.2,
        )
        self.play(FadeIn(trick))
        self.wait(3.5)
        self.play(FadeOut(trick))

        # unit circle in the complex plane
        ax = Axes(x_range=[-1.6, 1.6, 0.5], y_range=[-1.3, 1.3, 0.5],
                  x_length=5.4, y_length=4.4,
                  axis_config={"color": GREY, "stroke_width": 2})
        unit = Circle(radius=ax.c2p(1, 0)[0] - ax.c2p(0, 0)[0],
                      color=WHITE, stroke_width=3).move_to(ax.c2p(0, 0))
        lbl = Text("|λ| = 1", font_size=18, color=WHITE)
        lbl.next_to(unit, UP, buff=0.1)
        self.play(Create(ax), Create(unit), FadeIn(lbl))

        inside = VGroup(Dot(ax.c2p(0.55, 0.3), color=GREEN, radius=0.07),
                        Dot(ax.c2p(0.2, -0.5), color=GREEN, radius=0.07))
        outside = VGroup(Dot(ax.c2p(1.25, 0.35), color=RED, radius=0.07))
        in_lbl = Text("ρ < 1  →  decays, self-healing",
                      font_size=19, color=GREEN)
        out_lbl = Text("ρ > 1  →  explodes", font_size=19, color=RED)
        in_lbl.to_edge(RIGHT).shift(UP * 1.2 + LEFT * 0.3)
        out_lbl.next_to(in_lbl, DOWN, buff=0.35, aligned_edge=LEFT)

        self.play(FadeIn(inside), FadeIn(in_lbl))
        self.play(FadeIn(outside), FadeIn(out_lbl))
        self.wait(2.5)
        self.play(*[FadeOut(m) for m in (ax, unit, lbl, inside, outside,
                                         in_lbl, out_lbl)])

        stakes = Text(
            "Why it matters here:\n\n"
            "An NCA applies its rule thousands of times.\n\n"
            "        gain 1.05, 100 steps   →   131.5 ×\n"
            "        gain 0.95, 100 steps   →   0.006\n\n"
            "There is almost no middle ground.",
            font_size=24, color=WHITE, line_spacing=1.15,
        )
        self.play(FadeIn(stakes))
        self.wait(4)
        self.play(FadeOut(stakes))

        intuition = Text(
            "Intuition: a marble in a bowl, versus balanced on an upturned one.\n"
            "Same equations, opposite curvature.\n"
            "The eigenvalues tell you which bowl you are on —\n"
            "and for a saddle, which direction each way.",
            font_size=22, color=WHITE, line_spacing=1.2,
        )
        self.play(FadeIn(intuition))
        self.wait(4)
        self.play(FadeOut(intuition))

        elsewhere = Text(
            "Where else:  chaos and Lyapunov exponents · PageRank convergence\n"
            "every ODE solver's stability · power-grid dynamics\n"
            "exploding/vanishing gradients ARE the recurrent Jacobian's ρ\n\n"
            "Reproduce:  J = [[r, .3], [0, r/2]]\n"
            "            compare max(abs(eigvals(J))) against ‖Jᵗx‖",
            font_size=20, color=DIM, line_spacing=1.2,
        )
        self.play(FadeIn(elsewhere))
        self.wait(4)


SCENES = {
    "ShefferStroke": "why one primitive matters, and to whom",
    "BranchCut": "the ln(-1) knife edge, 8 ULPs wide",
    "SpectralRadius": "the number that decides pattern survival",
}


def gain_after(gain: float, steps: int) -> float:
    """Shared with the tests: the compounding claim must be checkable, not
    merely asserted on a slide."""
    return float(np.power(gain, steps))
