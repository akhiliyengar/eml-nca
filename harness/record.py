"""The metrics contract, and the invariant/metric split it enforces.

The single most important policy in this repository:

    INVARIANT   a property that is never legitimately false. Breaking one is
                always a bug. HARD FAILS.
    METRIC      a measurement that should move as research progresses.
                REPORTED, NEVER BLOCKING.

In software a falling number is a regression. In research it is frequently the
finding. Hard-failing CI on metric movement teaches people to add
`continue-on-error: true`, and then the safety net is gone for the invariants
too -- which is how a metric policy quietly destroys a correctness policy.
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .provenance import Provenance

REPO = Path(__file__).resolve().parents[1]
RESULTS = REPO / "results"

# Catastrophe guard, NOT a quality bar. A gain of 1.3 means the pattern expands
# -- that is a result, not a bug, and must never block. These bounds only catch
# structural breakage.
GAIN_CATASTROPHE_HI = 1e3
GAIN_CATASTROPHE_LO = 1e-3


class InvariantViolation(AssertionError):
    """A property that is never legitimately false was false."""


@dataclass
class RunRecord:
    provenance: Provenance
    invariants: dict[str, str] = field(default_factory=dict)
    metrics: dict[str, Any] = field(default_factory=dict)
    notes: list[str] = field(default_factory=list)

    # -- invariants: hard fail ------------------------------------------

    def check_finite(self, name: str, value: Any) -> None:
        """No NaN or inf, anywhere, ever."""
        arr = value if isinstance(value, (list, tuple)) else [value]
        bad = [v for v in arr if isinstance(v, float) and not math.isfinite(v)]
        if bad:
            self.invariants[f"finite:{name}"] = "FAIL"
            raise InvariantViolation(
                f"{name} contains non-finite values: {bad[:5]}"
            )
        self.invariants[f"finite:{name}"] = "pass"

    def check_gain_not_catastrophic(self, gain: float) -> None:
        """Wide sanity bound only.

        Deliberately NOT a quality bar. Whether a pattern grows or decays is the
        experiment's output; only absurd magnitudes indicate the code is broken
        rather than the hypothesis being wrong.
        """
        if not math.isfinite(gain):
            self.invariants["gain:finite"] = "FAIL"
            raise InvariantViolation(f"gain is not finite: {gain}")
        if gain > GAIN_CATASTROPHE_HI or (0.0 < gain < GAIN_CATASTROPHE_LO):
            self.invariants["gain:catastrophe"] = "FAIL"
            raise InvariantViolation(
                f"gain {gain:.3e} is outside the catastrophe guard "
                f"[{GAIN_CATASTROPHE_LO}, {GAIN_CATASTROPHE_HI}]. This is "
                f"structural breakage, not a finding."
            )
        self.invariants["gain:catastrophe"] = "pass"

    def check_reproducible(self, strict: bool = True) -> None:
        """Seed, commit and config hash must all be recorded."""
        problems = self.provenance.reproducibility_problems()
        if problems:
            self.invariants["reproducible"] = "FAIL" if strict else "WARN"
            self.notes.extend(problems)
            if strict:
                raise InvariantViolation(
                    "run is not reproducible:\n  - " + "\n  - ".join(problems)
                )
        else:
            self.invariants["reproducible"] = "pass"

    # -- metrics: never block -------------------------------------------

    def record(self, name: str, value: Any) -> None:
        self.metrics[name] = value

    # -- persistence ----------------------------------------------------

    def to_dict(self) -> dict[str, Any]:
        return {
            "provenance": self.provenance.to_dict(),
            "invariants": self.invariants,
            "metrics": self.metrics,
            "notes": self.notes,
        }

    def write(self, subdir: str | None = None) -> Path:
        """Write metrics.json.

        Only this small JSON is committed. Videos, weights and frame dumps stay
        out of git: diffing a metrics.json across 200 commits is a research
        superpower, diffing an MP4 is meaningless.
        """
        target = RESULTS / (subdir or self.provenance.thread)
        target.mkdir(parents=True, exist_ok=True)
        path = target / f"{self.provenance.run_id}.metrics.json"
        path.write_text(
            json.dumps(self.to_dict(), indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        return path

    def summary(self) -> str:
        ok = all(v == "pass" for v in self.invariants.values())
        head = "PASS" if ok else "INVARIANT FAILURE"
        p = self.provenance
        header = f"[{head}] run {p.run_id}  thread={p.thread}  seed={p.seed}"
        lines = [header]
        for k, v in sorted(self.invariants.items()):
            lines.append(f"    invariant  {v:<5} {k}")
        for k, v in sorted(self.metrics.items()):
            lines.append(f"    metric           {k} = {v}")
        for n in self.notes:
            lines.append(f"    note             {n}")
        return "\n".join(lines)
