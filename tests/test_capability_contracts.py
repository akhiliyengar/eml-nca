"""Tests for the literature capability contract.

The contract is the half of the semantic/exact split that makes the other half
safe, so it gets tested like a security control rather than a helper.

The point is NOT that it detects missing files -- anything does that. The point
is that it detects files which exist and look plausible while being wrong,
because that is what a fuzzy generated implementation actually produces when it
half-works:

  * an arXiv error page saved with a .pdf extension
  * raw HTML saved as .txt because extraction silently no-opped
  * the right filename holding the WRONG paper
  * a truncated download that still opens

Every one of those passes a naive existence check. Every one is the same
"silent partial success" pattern behind three of the four real bugs found in
this repository so far.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
CONTRACT = REPO / "capabilities" / "contracts" / "literature.py"


def load_contract():
    spec = importlib.util.spec_from_file_location("lit_contract", CONTRACT)
    mod = importlib.util.module_from_spec(spec)
    sys.modules["lit_contract"] = mod
    spec.loader.exec_module(mod)
    return mod


lit = load_contract()

REAL_PDF = b"%PDF-1.5\n" + b"x" * 30_000
REAL_TEXT = (
    "arXiv:2603.21852 [cs.SC]  All elementary functions from a single operator. "
    "We show that the binary operator eml(x,y) = exp(x) - log(y) together "
    "with the constant 1 generates the standard repertoire. " + "lorem " * 500
)
TITLE = "All elementary functions from a single operator"
ARXIV = "2603.21852"


# ------------------------------------------------------------------ pdf

def test_accepts_a_real_looking_pdf(tmp_path):
    p = tmp_path / "ok.pdf"
    p.write_bytes(REAL_PDF)
    assert lit.check_pdf("ok", p) == []


def test_rejects_missing_pdf(tmp_path):
    fails = lit.check_pdf("gone", tmp_path / "nope.pdf")
    assert len(fails) == 1 and "missing" in fails[0].why


def test_rejects_html_error_page_named_pdf(tmp_path):
    """The realistic failure: arXiv returns an error page, the fetcher saves it
    under a .pdf name, and an existence check calls that success."""
    p = tmp_path / "err.pdf"
    p.write_bytes(b"<html><body>404 Not Found</body></html>" + b" " * 30_000)
    fails = lit.check_pdf("err", p)
    assert fails and "not a PDF" in fails[0].why


def test_rejects_truncated_pdf(tmp_path):
    """Opens fine, is not a paper."""
    p = tmp_path / "trunc.pdf"
    p.write_bytes(b"%PDF-1.5\n" + b"x" * 100)
    fails = lit.check_pdf("trunc", p)
    assert fails and "bytes" in fails[0].why


# ----------------------------------------------------------------- text

def test_accepts_real_looking_text(tmp_path):
    p = tmp_path / "ok.txt"
    p.write_text(REAL_TEXT, encoding="utf-8")
    assert lit.check_text("ok", p, TITLE, ARXIV) == []


def test_rejects_raw_html_saved_as_text(tmp_path):
    """Extraction silently no-opped and the page was written verbatim."""
    p = tmp_path / "raw.txt"
    p.write_text("<div><p>elementary functions single operator</p></div>" * 400,
                 encoding="utf-8")
    fails = lit.check_text("raw", p, TITLE, "")
    assert any("raw HTML" in f.why for f in fails)


def test_rejects_wrong_paper_under_right_filename(tmp_path):
    """THE test that matters, and the one that took three iterations.

    Correct size, correct extension, clean text -- and a completely different
    paper. Only a content-identity check catches this.
    """
    p = tmp_path / "wrong.txt"
    p.write_text("Attention is all you need. The dominant sequence "
                 "transduction models are based on recurrent networks. "
                 + "transformer " * 600, encoding="utf-8")
    fails = lit.check_text("wrong", p, TITLE, ARXIV)
    assert any("DIFFERENT paper" in f.why for f in fails)


def test_rejects_sibling_paper_from_the_same_corpus(tmp_path):
    """Regression for the failure the contract originally shipped with.

    A live adversarial swap -- paper 07's text under paper 00's filename --
    PASSED the first two versions of this check:

      v1  distinctive title words. Failed: "elementary", "functions" and
          "operator" appear in both, because these papers cite each other. A
          corpus is self-similar by construction; that is what makes it a
          corpus.
      v2  arXiv id anywhere in the text. Failed: every citing paper carries the
          source paper's id in its BIBLIOGRAPHY.
      v3  arXiv id within the header region. Works, because position
          discriminates where content cannot.

    This is the hardest case precisely because sibling papers are maximally
    similar, so it is pinned.
    """
    p = tmp_path / "sibling.txt"
    p.write_text(
        "arXiv:2607.16360 [cs.IT]  EML-AirComp: Layered Over-the-Air "
        "Computation. We study a reusable gate for the exp-minus-log "
        "operation. All elementary functions follow from this operator. "
        + "nomographic " * 400
        + " References [12] A. Odrzywolek, arXiv:2603.21852, 2026.",
        encoding="utf-8")
    fails = lit.check_text("sibling", p, TITLE, ARXIV)
    assert any("bibliography" in f.why for f in fails), (
        "the sibling paper was accepted: shared vocabulary plus a bibliography "
        "citation is exactly the case that defeated v1 and v2"
    )


def test_rejects_stub_text(tmp_path):
    p = tmp_path / "stub.txt"
    p.write_text("Page not available.", encoding="utf-8")
    fails = lit.check_text("stub", p, TITLE, ARXIV)
    assert fails and "chars" in fails[0].why


def test_rejects_padded_text(tmp_path):
    """Padding past the length threshold must not buy a pass."""
    p = tmp_path / "pad.txt"
    p.write_text("x" * 5000, encoding="utf-8")
    fails = lit.check_text("pad", p, TITLE, ARXIV)
    assert any("DIFFERENT paper" in f.why for f in fails)


# ------------------------------------------------------------- helpers

def test_distinctive_words_skips_stopwords():
    words = lit.distinctive_words(TITLE)
    assert "the" not in words and "from" not in words
    assert "elementary" in words and "functions" in words


def test_distinctive_words_handles_punctuation():
    w = lit.distinctive_words("EML-AirComp: Layered Over-the-Air Computation!")
    assert "aircomp" in w or "computation" in w
    assert all(c.isalnum() for word in w for c in word)


# ------------------------------------------------------------ contract

def test_contract_is_exact_code_not_semantic():
    """ADR-001: the verifier must never itself become a capability.

    If the thing deciding 'did it work' can vary per install, the semantic
    half has no anchor and the whole split collapses.
    """
    assert CONTRACT.exists()
    text = CONTRACT.read_text(encoding="utf-8")
    assert "EXACT contract" in text


@pytest.mark.parametrize("path", [
    "src/emlnca/ops.py",
    "harness/provenance.py",
    "security/scan.py",
    "tests/test_determinism.py",
])
def test_exact_only_modules_have_no_capability_spec(path):
    """Nothing on the exact list may acquire a semantic counterpart.

    A capability spec for ops.py would mean the operator itself could be
    regenerated per install, which makes every downstream number
    unattributable.
    """
    stem = Path(path).stem.replace("_", "-")
    assert not (REPO / "capabilities" / f"{stem}.md").exists(), (
        f"{path} is on the EXACT list in ADR-001 but a capability spec exists"
    )
