#!/usr/bin/env python3
"""EXACT contract for the `fetch-literature` semantic capability.

This file is deliberately exact code, and must stay that way. It is the half of
the semantic/exact split that makes the other half safe: the acquisition may be
built however the environment suggests, but "did it work" is decided here, by
committed code that does not vary.

Written ADVERSARIALLY. The interesting failure is not "no file" -- it is a file
that exists and looks plausible while being wrong:

  * an arXiv error page saved as .pdf
  * raw HTML saved as .txt because extraction silently no-opped
  * the right filename holding the WRONG paper
  * a truncated download that still opens

Each of those would pass a naive existence check, and each is the "silent
partial success" failure this repository keeps encountering.

Usage:
    python capabilities/contracts/literature.py --verify
    python capabilities/contracts/literature.py --manifest   # write checksums
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
LIT = REPO / "literature"
INDEX = LIT / "index.json"
MANIFEST = LIT / "MANIFEST.sha256"

MIN_PDF_BYTES = 20_000
MIN_TEXT_CHARS = 2_000
MAX_TAG_RATIO = 0.02        # above this, extraction did not really run
TITLE_WORDS_REQUIRED = 3    # distinctive words that must appear in the text
HEADER_CHARS = 5_000        # a paper's own id is in its header, not its refs


def normalise(s: str) -> str:
    return re.sub(r"[^a-z0-9 ]+", " ", s.lower())


def distinctive_words(title: str) -> list[str]:
    """Longest words of a title, as a cheap 'is this the right paper' probe."""
    stop = {"the", "and", "for", "from", "with", "a", "an", "of", "on", "in",
            "to", "by", "via", "are", "is", "single", "all"}
    words = [w for w in normalise(title).split() if len(w) > 3 and w not in stop]
    return sorted(words, key=len, reverse=True)[:6]


class Failure:
    __slots__ = ("slug", "why")

    def __init__(self, slug: str, why: str):
        self.slug = slug
        self.why = why

    def __str__(self) -> str:
        return f"  FAIL  {self.slug:<44} {self.why}"


def check_pdf(slug: str, path: Path) -> list[Failure]:
    if not path.exists():
        return [Failure(slug, "pdf missing")]
    size = path.stat().st_size
    if size < MIN_PDF_BYTES:
        return [Failure(slug, f"pdf only {size} bytes (< {MIN_PDF_BYTES}); "
                              f"likely an error page, not a paper")]
    head = path.read_bytes()[:5]
    if not head.startswith(b"%PDF"):
        return [Failure(slug, f"not a PDF (magic bytes {head!r}); an HTML "
                              f"error page saved with a .pdf name would look "
                              f"exactly like this")]
    return []


def check_text(slug: str, path: Path, title: str, arxiv: str) -> list[Failure]:
    if not path.exists():
        return [Failure(slug, "text missing")]
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError as e:
        return [Failure(slug, f"text unreadable: {e}")]

    out: list[Failure] = []
    if len(text) < MIN_TEXT_CHARS:
        out.append(Failure(slug, f"text only {len(text)} chars "
                                 f"(< {MIN_TEXT_CHARS}); extraction likely "
                                 f"failed or the page was a stub"))
        return out

    tag_ratio = text.count("<") / max(len(text), 1)
    if tag_ratio > MAX_TAG_RATIO:
        out.append(Failure(slug, f"{tag_ratio:.1%} of characters are '<'; raw "
                                 f"HTML was saved instead of extracted text"))

    # PRIMARY identity check: the arXiv identifier, IN THE HEADER.
    #
    # This took three iterations, and the first two failed an adversarial swap:
    #
    #   1. distinctive title words -> FAILED. Paper 07's text passed as paper
    #      00 because "elementary", "functions" and "operator" appear in both.
    #      Structural, not tunable: these papers cite each other, so they share
    #      vocabulary. A corpus is self-similar; that is what makes it a corpus.
    #
    #   2. arXiv id anywhere in the text -> FAILED. Every citing paper carries
    #      the source paper's id in its BIBLIOGRAPHY.
    #
    #   3. arXiv id within the header region -> works. A document's own
    #      identifier appears near the top (observed at index 832 and 1045);
    #      cited identifiers appear deep in the references (observed at 43641).
    #      Position is the discriminator that content alone cannot provide.
    header = text[:HEADER_CHARS]
    if arxiv and arxiv not in header:
        where = text.find(arxiv)
        detail = (f"only at index {where}, i.e. in the bibliography"
                  if where != -1 else "not present at all")
        out.append(Failure(slug, f"arXiv id {arxiv} absent from the first "
                                 f"{HEADER_CHARS} chars ({detail}); this file "
                                 f"is a DIFFERENT paper under the right name"))

    # SECONDARY: title words. Weak alone, per (1) above, but catches a fetch
    # that returned a listing or abstract page carrying the right id.
    want = distinctive_words(title)
    body = normalise(text[:200_000])
    hits = [w for w in want if w in body]
    if want and len(hits) < min(TITLE_WORDS_REQUIRED, len(want)):
        out.append(Failure(slug, f"title words {want} not found (matched "
                                 f"{hits})"))
    return out


def load_index() -> dict:
    if not INDEX.exists():
        raise SystemExit(
            f"contract cannot run: {INDEX.relative_to(REPO)} is missing.\n"
            f"index.json is committed and authoritative -- restore it from git "
            f"rather than regenerating it."
        )
    data = json.loads(INDEX.read_text(encoding="utf-8"))
    if data.get("schema") != 1:
        raise SystemExit(f"index.json schema {data.get('schema')!r} != 1")
    return data


def verify() -> int:
    data = load_index()
    papers = data.get("papers", [])
    expected = [p for p in papers if p.get("arxiv")]

    failures: list[Failure] = []
    ok = 0
    for p in expected:
        slug = p["slug"]
        f = check_pdf(slug, LIT / "pdf" / f"{slug}.pdf")
        f += check_text(slug, LIT / "text" / f"{slug}.txt", p["title"],
                        p.get("arxiv") or "")
        if f:
            failures.extend(f)
        else:
            ok += 1

    print("contract: fetch-literature")
    print(f"  expected  {len(expected)} arXiv sources "
          f"({len(papers) - len(expected)} non-arXiv, not checked)")
    print(f"  verified  {ok}")
    print(f"  failed    {len(expected) - ok}")

    if not MANIFEST.exists():
        failures.append(Failure("MANIFEST.sha256", "missing; checksums are "
                                                   "required by the contract"))

    if failures:
        print()
        for f in failures:
            print(f)
        print("\n  CONTRACT FAILED.")
        print("  The capability did not succeed, regardless of how complete "
              "the run appeared.")
        print("  See capabilities/fetch-literature.md")
        return 1

    print("\n  CONTRACT PASSED")
    return 0


def write_manifest() -> int:
    lines = []
    for sub in ("pdf", "text"):
        d = LIT / sub
        if not d.exists():
            continue
        for path in sorted(d.iterdir()):
            if path.is_file():
                digest = hashlib.sha256(path.read_bytes()).hexdigest()
                lines.append(f"{digest}  {sub}/{path.name}")
    MANIFEST.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"wrote {MANIFEST.relative_to(REPO)} ({len(lines)} entries)")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--verify", action="store_true")
    ap.add_argument("--manifest", action="store_true")
    args = ap.parse_args()
    if args.manifest:
        return write_manifest()
    return verify()


if __name__ == "__main__":
    sys.exit(main())
