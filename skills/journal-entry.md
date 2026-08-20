# Skill: write a journal entry

**Trigger** - anything was learned. Especially if it was negative.

**Why this exists.** The end goal of this repository is understanding, not
code. Code without the reasoning that produced it is an artifact nobody can
extend - including you in six months.

## Format

`journal/YYYY-MM-DD-<slug>.md`

```markdown
# <what this was about>

thread: <id from threads/registry.json>
status: <what changed - hypothesis supported / falsified / refined / blocked>

## Expected
What I predicted before running, and why.

## Observed
What actually happened. Numbers with seeds and provenance.

## Interpretation
What it means. What it does NOT mean - overreach is the default error.

## Next
The single most informative next step, and why that one.
```

## Rules

1. **Write "Expected" before running.** Written afterwards it is rationalisation
   with a timestamp.
2. **Record negative results with equal care.** They are the point.
3. **Separate observation from interpretation.** Two headings, deliberately.
4. **Link the evidence** - metrics.json path, commit SHA, test name.
5. **Never edit an entry to look better.** Append a correction with a new date.
   The corpus this repo studies would be improved by the same discipline.

## Stop conditions

- Stop at four sections. A journal entry is not a paper.
- If there is no "Next", say so - a dead end is a legitimate ending.
