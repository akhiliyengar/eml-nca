# Skill: review critically

**Trigger** - reviewing any work, including and especially your own.

**Why this exists.** The default failure of an AI assistant is agreeableness.
Agreeable review of research produces confident wrong results.

## The checklist

1. **What is the weakest step?** Name it explicitly. Every argument has one; if
   you cannot find it you have not understood the argument.

2. **What is measured vs assumed?** Confident prose hides the seam. Mark each
   load-bearing statement as one or the other.

3. **Where is the control?** A claim of superiority without a null model is not
   evidence. Ask what the baseline was and whether it was tuned equally.

4. **Does the evidence cover the claim's scope?** Watch for variant drift
   (tested the generalized form, claimed for vanilla), depth drift, domain
   drift.

5. **Would this fail open?** For any guard, control or check: if it broke,
   would anything say so? Silent failure is the recurring bug class here -
   three of the four real bugs found in this repo failed open and quiet.

6. **What would change my mind?** If nothing would, this is not a review.

## On reviewing your own work

Harder and more important. Specifically re-check:

- Did I claim a test exists? **Verify with `git ls-files` and read it.** This
  exact failure happened here - a determinism invariant was asserted in
  conversation before it was written.
- Did I report a number I did not measure?
- Did I round a hedge into a certainty between one message and the next?

## Stop conditions

- Stop when you have named the weakest step and stated what would change your
  mind. Those two are the minimum viable review.
- Do not pad with style notes to appear thorough.

## Anti-patterns

- Leading with praise to soften a finding
- "Looks good overall, minor note:" followed by a fatal flaw
- Reviewing what was written instead of what was claimed
