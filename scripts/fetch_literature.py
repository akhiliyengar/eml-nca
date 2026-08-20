#!/usr/bin/env python3
"""Fetch the paper corpus and build a hyperlinked index.

First-time setup step. Downloads the source paper and everything that cites it
from arXiv, extracts text for grepping, and writes literature/index.json which
the docs generator turns into a linked table.

PDFs and extracted text are NOT committed -- they are reproducible from this
script and would bloat the repository. index.json IS committed, because it is
small, diffable, and is the actual bibliographic record.

Usage:
    python scripts/fetch_literature.py           # fetch missing only
    python scripts/fetch_literature.py --force   # re-fetch everything
    python scripts/fetch_literature.py --index-only
"""

from __future__ import annotations

import argparse
import html
import json
import re
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
LIT = REPO / "literature"
PDF = LIT / "pdf"
TXT = LIT / "text"

UA = {"User-Agent": "eml-nca-research/0.1 (+https://github.com/akhiliyengar/eml-nca)"}

# The corpus. `role` records WHY each paper matters to this repository, which is
# the part a bare citation list always loses.
CORPUS = [
    {
        "n": 0, "arxiv": "2603.21852", "date": "2026-03",
        "slug": "00_source_eml_single_operator",
        "title": "All elementary functions from a single operator",
        "authors": "Odrzywolek",
        "role": "SOURCE. Defines eml(x,y)=exp(x)-ln(y). Reports blind symbolic "
                "recovery collapsing to 0/448 at depth 6.",
    },
    {
        "n": 1, "arxiv": "2604.23893", "date": "2026-04",
        "slug": "01_stachowiak_algebraic_structure",
        "title": "Algebraic structure behind Odrzywolek's EML operator",
        "authors": "Stachowiak",
        "role": "Shows EML is one member of a classifiable family; the depth-7 "
                "ln tree is structural, not logarithmic. Missed by Semantic "
                "Scholar; found via Belaiche's reference list.",
    },
    {
        "n": 2, "arxiv": "2604.26507", "date": "2026-04",
        "slug": "02_auto_relational_reasoning",
        "title": "Auto-Relational Reasoning",
        "authors": "Konstantoulas, Tsimas, Peppas, Sgarbas",
        "role": "Weakest link: cites EML in one sentence as justification, "
                "implements none of it. No code.",
    },
    {
        "n": 3, "arxiv": "2605.08130", "date": "2026-05",
        "slug": "03_additive_atomic_forests",
        "title": "Additive Atomic Forests for Symbolic Function and "
                 "Antiderivative Discovery",
        "authors": "Belaiche",
        "role": "Adds SOL = sin(u)-cos(v) because trig costs depth ~8 in EML. "
                "Strong empirical claims, no code released.",
    },
    {
        "n": 4, "arxiv": "2605.02972", "date": "2026-05",
        "slug": "04_eml_biological_dynamics",
        "title": "Non-Monotone Response Modules and Cascades from the EML "
                 "Operator",
        "authors": "Erez",
        "role": "MOST DIRECTLY USEFUL. 3-parameter non-monotone gate; ran the "
                "fair Hill comparison and reported the tie at depth 2. Ships "
                "code.",
    },
    {
        "n": 5, "arxiv": "2606.05942", "date": "2026-06",
        "slug": "05_eml_cd_causal",
        "title": "EML-CD: Causal Mechanism Recovery via EML Symbolic Trees",
        "authors": "Asanuma",
        "role": "Analytic Jacobians as the selling point. Documents that exp "
                "clipping is 'load-bearing rather than cosmetic'.",
    },
    {
        "n": 6, "arxiv": "2606.23179", "date": "2026-06",
        "slug": "06_eml_trees_universal_approximators",
        "title": "EML Trees Are Universal Approximators",
        "authors": "Germany, Abdo, Bakarji",
        "role": "CRITICAL NEGATIVE RESULT: 0/42 parameters snap to symbolic "
                "form. Theorem covers the 6-param generalized atom, not "
                "vanilla EML.",
    },
    {
        "n": 7, "arxiv": "2607.16360", "date": "2026-07",
        "slug": "07_eml_aircomp",
        "title": "EML-AirComp: Layered Over-the-Air Computation from a Single "
                 "Nomographic Gate",
        "authors": "Gunlu",
        "role": "The clean win. EML is exactly nomographic, so one analog gate "
                "type serves every tree node. Sidesteps complex domain via "
                "real-admissible trees.",
    },
    {
        "n": 8, "arxiv": None, "date": "2020-02",
        "slug": "08_growing_nca",
        "title": "Growing Neural Cellular Automata",
        "authors": "Mordvintsev, Randazzo, Niklasson, Levin",
        "url": "https://distill.pub/2020/growing-ca/",
        "role": "TARGET SYSTEM. ~8k-parameter MLP update rule; the thing an "
                "EML forest would replace.",
    },
]


def fetch(url: str, dest: Path, force: bool) -> str:
    if dest.exists() and not force:
        return "cached"
    try:
        req = urllib.request.Request(url, headers=UA)
        with urllib.request.urlopen(req, timeout=90) as r:
            dest.write_bytes(r.read())
        return "fetched"
    except (urllib.error.URLError, TimeoutError) as e:
        return f"FAILED ({e})"


def html_to_text(raw: bytes) -> str:
    t = raw.decode("utf-8", errors="replace")
    t = re.sub(r"(?s)<(script|style)[^>]*>.*?</\1>", " ", t)
    t = re.sub(r"(?i)</(p|div|h[1-6]|li|tr|section)>", "\n", t)
    t = re.sub(r"<[^>]+>", " ", t)
    t = html.unescape(t)
    t = re.sub(r"[ \t]+", " ", t)
    return re.sub(r"(\n\s*){3,}", "\n\n", t).strip()


def main() -> int:
    ap = argparse.ArgumentParser(description="Fetch the paper corpus")
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--index-only", action="store_true",
                    help="write index.json without downloading")
    args = ap.parse_args()

    LIT.mkdir(exist_ok=True)
    for d in (PDF, TXT):
        d.mkdir(exist_ok=True)

    if not args.index_only:
        print(f"fetching {len(CORPUS)} sources into literature/\n")
        for p in CORPUS:
            if p["arxiv"]:
                pdf_status = fetch(f"https://arxiv.org/pdf/{p['arxiv']}",
                                   PDF / f"{p['slug']}.pdf", args.force)
                html_url = f"https://arxiv.org/html/{p['arxiv']}"
            else:
                pdf_status = "n/a"
                html_url = p["url"]

            txt_path = TXT / f"{p['slug']}.txt"
            if txt_path.exists() and not args.force:
                txt_status = "cached"
            else:
                try:
                    req = urllib.request.Request(html_url, headers=UA)
                    with urllib.request.urlopen(req, timeout=90) as r:
                        txt_path.write_text(html_to_text(r.read()),
                                            encoding="utf-8")
                    txt_status = "extracted"
                except (urllib.error.URLError, TimeoutError) as e:
                    txt_status = f"FAILED ({e})"

            print(f"  [{p['n']}] {p['slug']:<42} pdf={pdf_status:<10} "
                  f"text={txt_status}")
            time.sleep(2)   # be polite to arXiv

    index = {
        "schema": 1,
        "generated_note": "Bibliographic record. PDFs and text are NOT "
                          "committed; regenerate with scripts/fetch_literature.py",
        "papers": CORPUS,
    }
    (LIT / "index.json").write_text(
        json.dumps(index, indent=2) + "\n", encoding="utf-8")
    print(f"\nwrote literature/index.json ({len(CORPUS)} entries)")
    print("run `python scripts/gen_docs.py` to refresh the linked table")
    return 0


if __name__ == "__main__":
    sys.exit(main())
