# WHY — every control and visual, in plain English

No jargon. If a sentence here needs a maths degree, it is a bug in this file.

**The one-line version:** we are checking whether a new "rule" for a simple
growing-pattern game works as well as the one people already use. Most of the
work is making sure we do not fool ourselves.

---

## Part 1 — the controls

A **control** is the boring, already-works version you keep next to the exciting
new thing.

> 🍦 **Why you need one.** If you invent a new ice cream and everyone says
> "tasty", you have learned nothing — maybe they just like ice cream. You have
> to hand them the *normal* one too. Same recipe, same day, same people.
>
> A result with nothing to compare against is not a result.

### The controls in this project

| control | what it is | why it exists |
|---|---|---|
| **`configs/frozen/`** | settings nobody is allowed to change | A tape measure you never bend. If a test using it breaks, *we* broke something — the measuring stick did not move. |
| **polynomial library** (Rung 1) | a toolbox that definitely contains the right answer | If the toolbox *with* the answer in it still fails, the workshop is broken, not the tool. It scored 1e-31 — near-perfect — so we knew the setup was sound before blaming EML. |
| **Gaussian growth** (Rung 2) | the rule Lenia normally uses | Without it, "the new rule kept the creature alive" is meaningless. Alive compared to *what*? |
| **the same seeds for both** | identical starting shapes in every arm | Otherwise "the new rule killed it" might just mean "that starting shape was doomed anyway". |
| **"different seeds must differ"** | a test that the seed number actually matters | Caught a real bug: our test map squashed everything so hard that *every* start ended identically. The test would have passed with the seed ignored entirely. It was checking nothing. |
| **"Hill cannot be non-monotone"** | proof the old thing really has the limitation claimed | Otherwise the new thing's advantage might be imaginary. |
| **"empty grid is dead"** | check the judge calls nothing "nothing" | Sounds silly. It is not: a broken judge that says *everything* is alive would make every result a success and the whole project meaningless. |
| **"eating the screen is not winning"** | catch runaway growth | A creature that fills the world has not survived; it has broken the world. |
| **the fog check** | at least half the world must stay empty | ⬇️ this one changed a result — see below. |

### 🚨 The fog check — how a control saved us from a false discovery

The first Rung 2 run said the new rule kept the creature alive **20 times out of
20**. Better than the old rule. Exciting.

It was wrong.

Our judge only weighed the grid. But **a small bright creature on a black
background weighs the same as a whole screen of dim grey.** The new rule had
not made creatures — it had made **fog**. Every pixel slightly lit, nothing left
empty, no shape at all.

> 🌫️ **The picture to remember:** you asked "how much paint is on the canvas?"
> when you should have asked "is there a *picture* on the canvas?"

The fix: also require that most of the world stays empty. Measured gap:

| | how much of the grid stayed empty |
|---|---|
| real creatures | 81% and 99.6% ✅ |
| fog | 0% to 5.7% ❌ |

Nothing in between, so the 50% line is safe rather than arbitrary. With the fix,
the true score was **0 out of 2400**.

---

## Part 2 — the visuals

### 🎨 The live viewer — [akhiliyengar.github.io/eml-nca](https://akhiliyengar.github.io/eml-nca/)

**Why it exists.** The Rung 2 question is *"does the creature survive?"* That is
far easier to answer by **watching** than by reading a number. A number tells
you 0.43; your eye tells you instantly that the screen is fog.

It is not decoration. It found the fog problem before the experiment did.

| what you see | plain English | why it matters |
|---|---|---|
| **the black square** | the world. Bright = alive, dark = empty. | Shape is the whole point. If everything is one shade, nothing is happening. |
| **Gaussian / Erez buttons** | old rule vs new rule | Flip between them on the same starting shape. That flip *is* the experiment. |
| **mu, sigma** | "how much company does a cell want, and how fussy is it?" | Fussier means fewer survivors but sharper shapes. |
| **a, b, c** | new rule's knobs: how fast it grows, how hard it pushes back, where zero sits | The claim is *fewer knobs, same job*. |
| **radius** | how far a cell looks | Look at a *ring* of neighbours, not a blob — that is what makes shapes crawl instead of sit. |
| **dt** | how big a time step is | Too big and the simulation jumps past reality, like a flipbook missing pages. |
| **mass** | total brightness | Going up = filling. Going down = dying. |
| **gain** ⭐ | growth per step | The most important number here. See below. |
| **verdict** | alive / died / saturated | The judge's call, live. |

### ⭐ Gain — the one number that decides everything

Gain is **"how much bigger did it get in one step"**.

Sounds boring. It is not, because the rule runs **thousands** of times and small
things multiply:

| gain per step | after 100 steps |
|---|---|
| 1.05 (5% bigger) | **131.5× bigger** 💥 |
| 0.95 (5% smaller) | **0.0059 — basically gone** 💨 |

> 🎤 **The picture to remember:** a microphone next to its own speaker. One pass
> is fine. Feed it back a hundred times and you get either an ear-splitting
> squeal or dead silence. **There is almost no middle.**

That is why gain is measured from the very first run, not investigated after
something breaks.

### 🎬 The Manim explainers

Short animations. Each answers the same four questions: *what problem does this
solve, why does it matter, where else does it show up, and how would you check
it yourself?*

| video | plain English | why it matters |
|---|---|---|
| **Sheffer Stroke** | one Lego brick that builds anything | Chip factories perfect *one* gate and build every computer from it. That is why "one primitive" is an engineering result, not a party trick. |
| **Branch Cut** | a spiral staircase — walk around once and you are on a different floor | Our `ln(−1)` sits **8 ULPs** from silently giving the wrong answer. A different computer could flip it. Now pinned by a test. |
| **Spectral Radius** | marble in a bowl vs balanced on an upturned bowl | Same equations, opposite outcome. One number tells you which bowl you are on — and whether a pattern heals itself or explodes. |

**Every number on those slides is checked by a test.** That test already caught
one of my own mistakes: a slide said `131×` when the true value is `131.5`
(which *rounds to 132*). It had spread to eight files. A teaching slide with a
wrong number is worse than no slide — it is memorable, confident, and repeated.

---

## Part 3 — the pattern behind all of it

Every real bug in this project was caught by **something checking the checker** —
never by the thing being tested.

| what broke | what caught it |
|---|---|
| a test that passed while checking nothing | the "seeds must differ" control |
| the workshop was broken, not the tool | the polynomial control |
| fog scored as living creatures | the empty-space control |
| a wrong number on a teaching slide | the slide-content test |
| security hooks silently switched off on Linux | a job that *tries* to sneak a secret past them |

> **The rule:** every check needs a second check proving it can actually fail.
> Otherwise you are not measuring the world — you are measuring your own
> equipment, and it always agrees with you.

This is also the exact criticism this project makes of the papers it studies. It
would be embarrassing to repeat it, so the controls are the bulk of the work.
