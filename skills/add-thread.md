# Skill: open a research thread

**Trigger** - a new line of investigation, or forking an existing one.

**Why this exists.** Git branches carry the code; they do not carry the
argument. Branches get deleted and the reasoning evaporates with them. This
registry keeps what was believed, what would falsify it, and what happened.

## Steps

1. **State the hypothesis in one falsifiable sentence.**
   - Bad: "explore whether EML helps NCA"
   - Good: "an EML forest matches Growing-NCA morphogenesis at <= 300 params"

2. **Write the falsifier.** What observation makes you abandon this?
   **A thread with no falsifier is not research.** If you cannot name one, the
   hypothesis is too vague - go back to step 1.

3. **State your prior honestly.** If the evidence is against you, say so in
   `notes` and register it anyway. `t5-symbolic-recovery` is registered with an
   explicitly low prior because a negative result there is worth publishing.

4. **Set `parent`** if forking. Threads form a tree, not a list.

5. `python scripts/gen_docs.py` to refresh the catalog.

6. Open `journal/YYYY-MM-DD-<thread-id>.md`.

## Converging threads

When two threads reach the same conclusion, mark the subsumed one `converged`
and point its `verdict` at the survivor. Do not delete it - the fact that two
routes met is itself evidence.

## Abandoning threads

Set `abandoned` and **write the verdict**. An abandoned thread with a clear
negative verdict is one of the more valuable objects in this repository.
Deleting dead threads is how a research log turns into marketing.

## Stop conditions

- Stop if the hypothesis is not falsifiable after two attempts to sharpen it
- Stop if an existing thread already covers it - fork instead of duplicating
