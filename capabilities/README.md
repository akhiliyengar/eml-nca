# Capabilities

Semantic modules. See [ADR-001](../docs/adr/ADR-001-semantic-vs-exact.md) for
why this split exists.

## The rule

> **Semantic** if its output is an *artifact you can verify*.
> **Exact** if its output is *evidence you must trust*.
>
> A module may be semantic **iff** its postconditions are checked by exact,
> committed code.

Fuzzy acquisition, exact verification.

## How a capability runs

```
1. an agent reads  capabilities/<name>.md
2. it builds an implementation suited to THIS machine
   -> written to .capabilities/generated/  (gitignored, for debugging)
3. it runs that implementation
4. it runs  capabilities/contracts/<name>.py --verify
5. contract PASSES -> done.  contract FAILS -> the capability failed.
```

Step 4 is not optional and is not advisory. **The contract is the definition of
done.** A capability that "looks complete" but fails its contract has failed.

## Required parts

A file in this directory is a capability only if it has all four. Three out of
four is a wish.

| Part | Purpose |
|---|---|
| **Postconditions** | checkable end-state, not prose about intent |
| **Exact verifier** | in `contracts/`, committed, tested, run in CI |
| **Guardrails** | network hosts, filesystem scope, no credentials, no `git push` |
| **Refusal clause** | what to do when it cannot be satisfied |

The refusal clause matters most. **Silent partial success is the failure mode
this repository keeps hitting** — three of the four real bugs found so far
stopped working without saying so. A capability that fetches 6 of 9 papers must
report *"6 of 9, missing: …"*, never *"done"*.

## Writing a contract

Write it **adversarially**. Existence checks are nearly worthless; the
interesting failure is a file that exists and looks plausible while being wrong.

The literature contract rejects:

| Plausible-looking failure | Detection |
|---|---|
| arXiv error page saved as `.pdf` | magic bytes must be `%PDF`, size > 20 KB |
| raw HTML saved as `.txt` | `<` must be under 2 % of characters |
| **right filename, wrong paper** | distinctive title words must appear in the body |
| truncated download that still opens | minimum size thresholds |

Verify **output**, never method. The moment a contract constrains *how*, the
capability stops being semantic and you have written exact code with extra
steps.

## Current capabilities

| capability | contract | status |
|---|---|---|
| [`fetch-literature`](fetch-literature.md) | `contracts/literature.py` | active |

## Not capabilities, and never will be

`src/emlnca/**` · `harness/**` · `security/**` · `.githooks/**` · `tests/**` ·
`configs/frozen/**`

These are the definition of the research, not artifacts about it. A regenerated
`eml_stable` with a different clamp is **a different operator**, and every number
downstream of it becomes unattributable.
