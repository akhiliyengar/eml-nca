# ADR-001: Semantic capabilities vs exact code

- **Status:** accepted
- **Date:** 2026-08-20
- **Supersedes:** the exact `scripts/fetch_literature.py`

## Context

Some modules here are brittle for reasons unrelated to the research: arXiv
changes its HTML, a PDF extractor stops working, a platform lacks a tool, an API
adds a rate limit. Pinning exact code for these means maintaining a scraper
forever, and that maintenance has zero scientific value.

The alternative is a **semantic capability**: a specification precise enough
that any competent agent — regardless of LLM provider — can construct a working
implementation at setup time, adapted to whatever environment it finds.

This is attractive and also dangerous, because this repository's central
commitment is reproducibility. If executing code is synthesised per install,
then a recorded git SHA describes the *specification* rather than the
*behaviour*, and two people can obtain different results from the same commit.

## Decision

Adopt semantic capabilities, bounded by a hard rule:

> A module MAY be semantic **if and only if** its postconditions are verified by
> exact, committed code.
>
> **Semantic** if its output is an *artifact you can verify*.
> **Exact** if its output is *evidence you must trust*.

Fuzzy acquisition, exact verification. The implementation may vary; the verified
end-state may not.

## Taxonomy

### Must be EXACT — no exceptions

| Module | Why |
|---|---|
| `src/emlnca/ops.py` | the primitives ARE the definition. There is no external check for "did this produce the right float"; a regenerated `eml_stable` with a different clamp is a different operator. |
| `harness/provenance.py`, `record.py` | the reproducibility machinery cannot itself be irreproducible |
| `security/scan.py`, `.githooks/*` | a control that varies per generation is not a control |
| `tests/**` | a test regenerated each run tests nothing. Tests are the specification made executable. |
| `configs/frozen/**` | frozen means frozen |
| anything producing a **reported number** | evidence must trace to fixed code |

### May be SEMANTIC — with a contract

| Capability | Why it qualifies | Verified by |
|---|---|---|
| literature acquisition | output is PDFs and text; correctness is checkable by size, content markers and metadata | `capabilities/contracts/literature.py` |
| environment bootstrap | environments differ wildly; success is checkable | `pytest` green |
| visualisation scaffolding | aesthetic, not scientific; no number depends on it | human review |
| dataset acquisition | third-party artifacts with published hashes | checksum manifest |

### The test

Ask: **if two people ran this and got different implementations, would a
reported result change?**

- **Yes** → exact.
- **No, and I can prove sameness of output** → semantic + contract.
- **No, but I cannot prove it** → exact, until a contract exists.

## Contract requirements

Every semantic capability MUST ship all four:

1. **Postconditions** — a checkable end-state, not prose about intent
2. **An exact verifier** in `capabilities/contracts/` — committed, tested, run
   in CI
3. **Guardrails** — explicit limits on what a generated implementation may do
   (allowed network hosts, filesystem scope, no credential access, no `git push`)
4. **A refusal clause** — what to do when the capability cannot be satisfied.
   Silent partial success is the failure mode that matters; a capability that
   half-works and reports success is worse than one that fails outright.

Missing any of the four means it is not a capability, it is a wish.

## Consequences

**Good**
- Brittle external-facing code stops being a maintenance burden
- Adapts to environments unknown at authoring time
- The specification is shorter and more stable than any implementation of it
- Provider-agnostic by construction

**Bad, accepted**
- A generated implementation may be subtly wrong in ways the contract does not
  check. Mitigation: contracts verify *output*, never *method*, and are written
  adversarially.
- Debugging is harder because the failing code is not in git. Mitigation:
  generated implementations are written to `.capabilities/generated/` and the
  run records which one was used.
- Prompt injection — a capability that fetches web content and then acts on it
  is an attack path. Mitigation: guardrails are mandatory, and fetched content
  is data, never instructions.

**Neutral**
- A two-tier repository. Already true: `configs/frozen` vs
  `configs/experimental` splits along the same seam.

## Rejected alternatives

**Everything exact** (status quo). Rejected: perpetual scraper maintenance with
no scientific value, and it breaks on environments not anticipated at authoring
time.

**Everything semantic** (the request as literally stated). Rejected: dissolves
reproducibility. If `ops.py` were regenerated per install, no reported number
would mean anything and the repository's stated purpose fails.

**Semantic with no contract.** Rejected: that is "hope the agent does it right",
whose failure mode is silent partial success — precisely the pattern behind
three of the four real bugs found here so far.
