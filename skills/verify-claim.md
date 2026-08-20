# Skill: verify a claim

**Trigger** — a paper, a person, a README, or you yourself assert something
factual.

**Why this exists.** The literature this repository studies contains claims
that dissolve on inspection: a universal-approximation theorem proved for a
6-parameter atom but reported as if it covered vanilla EML; a symbolic
interpretability claim contradicted by the authors' own 0/42 snapping table;
an "expressiveness" advantage that a fair Hill comparison shows is a tie at
depth 2. **None of these required new experiments to find — only reading the
paper properly.**

## Preconditions

- The exact claim, written down in one sentence
- The primary source, not a summary of it

## Steps

1. **Restate the claim precisely.** Vague claims cannot be checked. Convert
   "EML is interpretable" into "trained EML tree parameters snap to values in
   {0, ±1} within a stated loss tolerance".

2. **Locate the primary evidence.** Not the abstract, not the introduction —
   the table, figure or proof. Abstracts routinely overstate what the body
   supports.

3. **Check scope drift.** Does the evidence cover what the claim says?
   - Which *variant* was tested? (vanilla vs generalized EML)
   - Which *depth*, *domain*, *sample size*?
   - Was there a **control**? A claim of superiority with no null model is not
     evidence of superiority.

4. **Look for the authors' own caveats.** In this corpus the most damaging
   admissions were in Section 3.4, "Limitations", and a footnote. Authors are
   frequently more honest than their abstracts.

5. **Try to falsify it cheaply.** Can it be checked numerically in ten lines?
   The branch-cut fragility here was found by writing one test.

6. **Classify the verdict:**
   | verdict | meaning |
   |---|---|
   | `supported` | primary evidence covers the claim as stated |
   | `narrower` | true, but only under conditions the claim omits |
   | `unsupported` | no evidence found for it |
   | `contradicted` | evidence points the other way |
   | `unverifiable` | no code, no data, no derivation |

7. **Record it.** If it changes a repo decision, add a journal entry. If it is
   about a corpus paper, update `role` in `scripts/fetch_literature.py`.

## Stop conditions

- **Stop at `unverifiable`.** Do not reconstruct someone's unreleased method to
  give their claim the benefit of the doubt. "No code, no data" is a complete
  and legitimate verdict.
- **Stop when the verdict changes no decision.** Verification is a means, not
  a hobby.

## Anti-patterns

- ❌ Accepting a claim because the paper is cited a lot
- ❌ Accepting your own claim because you remember writing the test — check
  with `git ls-files` and read it
- ❌ Reporting "roughly confirms" — say which of the six verdicts applies
