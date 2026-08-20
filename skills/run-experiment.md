# Skill: run an experiment

**Trigger** — producing any number that might later be cited, in a paper, an
issue, or a conversation.

**Why this exists.** A number without its production conditions is an anecdote.
The gap between "I ran it and got 0.87" and "here is a result" is entirely
provenance.

## Preconditions

- A registered thread in `threads/registry.json` with a **falsifier**
- A config in `configs/experimental/` (or `configs/frozen/` for a regression run)
- A clean working tree — `python harness/provenance.py` reports no gaps

## Steps

1. **Declare the falsifier before running.** Write down what result would make
   you abandon the hypothesis. Doing this afterwards is how a null result
   becomes "interesting exploratory signal".

2. **Fix the seed.** Record it in the config, never as a CLI afterthought.

3. **Commit first.** A dirty tree means the code that produced the number
   exists nowhere but your disk. `provenance.reproducibility_problems()`
   reports this; do not ignore it.

4. **Instrument gain from step one.** Every iterated run records `GainTrace`.
   When something dies at step 3,000 you want to already know whether it was
   runaway growth or decay, not start bisecting.

5. **Run, and let invariants fail loudly.** Do not catch `InvariantViolation`
   to keep a run alive. An invariant failure means the result is void.

6. **Write `metrics.json`.** Small, diffable, committed. Artifacts — video,
   weights, frame dumps — stay out of git.

7. **Compare against a null model.** A result with no baseline is not a result.
   For growth functions the null is the Gaussian or Hill; for classification,
   logistic regression or XGBoost; for parameter count, the standard MLP.

8. **Report the delta, not just the value.** "0.87" is noise. "0.87 vs 0.91
   baseline, n=5 seeds, ±0.02" is a finding.

## Stop conditions

- **Stop when the falsifier fires.** That is the answer. Record it and mark the
  thread `abandoned` with its verdict. Do not sweep hyperparameters looking for
  a configuration that rescues the hypothesis — that is p-hacking with extra
  steps.
- **Stop when the invariant fails.** Fix the bug; the run is void, not
  interesting.
- **Stop at 3 seeds minimum** before reporting any comparison. A single seed is
  an anecdote; Belaiche's SINDy baseline looked catastrophic entirely because
  of one unlucky seed.

## Anti-patterns

- ❌ Running until it looks good, then recording that run
- ❌ Reporting raw accuracy on an imbalanced dataset — the corpus does this and
  self-flags it as inadequate
- ❌ Comparing against a baseline you tuned less than your method
- ❌ Quietly widening the catastrophe guard to make a run pass
