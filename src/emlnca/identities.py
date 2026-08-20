"""Published EML identities, kept as executable specification.

Every entry here is a claim made in arXiv:2603.21852 that we can check
numerically. They are the bedrock regression tests: if a refactor breaks one of
these, the primitive is wrong and nothing downstream is trustworthy.

RPN column is the paper's own notation, with E = eml. Depth is tree depth.
"""

from __future__ import annotations

import cmath

from .ops import eml_scalar

# The single distinguished constant. ln(1) = 0 is what lets EML neutralise its
# own logarithm term, which is why the constant cannot simply be dropped.
ONE = 1.0


def const_e() -> complex:
    """e = eml(1, 1).  RPN: 11E  (depth 1)"""
    return eml_scalar(ONE, ONE)


def exp_(x: complex) -> complex:
    """exp(x) = eml(x, 1).  RPN: x1E  (depth 1)"""
    return eml_scalar(x, ONE)


def ln_(z: complex) -> complex:
    """ln(z) = eml(1, eml(eml(1, z), 1)).  RPN: 11zE1EE  (depth 3, K=7)

    Unfolding: eml(1,z) = e - ln z, then eml(that, 1) = exp(e - ln z) = e^e / z,
    then eml(1, e^e/z) = e - ln(e^e / z) = ln z.

    Stachowiak (arXiv:2604.23893) showed this length-7 form is NOT a property of
    the logarithm: it falls out of the generic six-step derivation chain for any
    f and any anti-associative M. The depth is structural, not logarithmic.
    """
    return eml_scalar(ONE, eml_scalar(eml_scalar(ONE, z), ONE))


IDENTITIES = {
    "e": (const_e, (), cmath.e),
    "exp(1)": (exp_, (1.0,), cmath.e),
    "exp(0)": (exp_, (0.0,), 1.0),
    "exp(2)": (exp_, (2.0,), cmath.e**2),
    "ln(e)": (ln_, (cmath.e,), 1.0),
    "ln(1)": (ln_, (1.0,), 0.0),
    "ln(2)": (ln_, (2.0,), cmath.log(2.0)),
    "ln(10)": (ln_, (10.0,), cmath.log(10.0)),
}
