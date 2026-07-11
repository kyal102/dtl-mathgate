# What ProofBench X caught — and why this repo's test lanes look the way they do

This is a writeup about the **hosted** SuperMath engine (`core/supercharged_math.py`,
proprietary, not in this repository — see [LICENSING.md](../LICENSING.md)), not about
a bug found in this lite engine. It's included here because the lite engine's
ProofBench-X Lite suite (`mathgate/proofbench_lite.py`) has lanes named
`sign_regression`, `bigint_exactness`, and `refusal` specifically *because* of what's
below — they're the public, reproducible descendants of real bugs a verification
benchmark found in production math code.

The premise going in was ordinary: an engine doing exact integer/rational/symbolic
arithmetic, wrapped for years, should already be correct. Building a 1,116-case
seeded benchmark against an independent grading oracle (not the engine checking
itself) surfaced five real bugs before any score was published:

1. **`(-A)*B` sign drop.** A negated factor's sign was lost in one multiplication
   path. `(-3)*4` could come back `12` instead of `-12` under a specific parse
   route. This is exactly the class of bug a human spot-checking "does 2+2=4"
   would never catch, and exactly the class an adversarial/regression suite exists
   to catch. **This repo's `sign_regression` lane (48 seeded cases: `(-A)*B`,
   `A*(-B)`, `(-A)*(-B)`, `-(A*B)`, and variants) is the open reproduction of this
   check** — run against the lite engine here, graded by an independent `ast`-walking
   oracle that shares no code with the lite engine's own recursive-descent parser.

2. **Negative-entry determinant row-sum error.** Matrix determinant computation
   over matrices with negative entries used a row-sum shortcut that doesn't hold
   in general — correct for some inputs, silently wrong for others. (Linear
   algebra is out of scope for this lite engine, so there's no direct lane for
   this one here — noted for completeness.)

3. **Matrix inverse returning the determinant.** A copy/paste-shaped bug: the
   "inverse" operation returned the determinant value instead of the inverse
   matrix. Now the hosted engine computes the actual inverse and refuses
   singular/non-square/ragged matrices rather than returning a nonsense answer.
   (Also linear algebra — out of scope here.)

4. **6,000–10,000-digit products returned as lossy scientific notation.** Very
   large exact integer results were being formatted through a path that silently
   truncated to scientific notation — a five-thousand-digit exact answer coming
   back as `1.2345e5000` is not exact, it's a lie dressed as a number. Now returned
   as the full exact integer. **This repo's `bigint_exactness` lane (48 seeded
   cases: large factorials and large integer powers) checks the same failure
   mode** — the lite engine's own tests (`test_bigint_stays_exact_no_scientific_notation`)
   assert `"e"` never appears in a result string.

5. **Malformed-arithmetic salvage.** Given garbage input like `"1 + + * 2 )("`,
   the engine's "helpful" recovery logic would salvage *something* and return an
   answer rather than refuse. An answer to a malformed question is worse than no
   answer — it looks authoritative. Now guarded by an explicit well-formedness
   check that refuses instead of guessing. **This repo's `refusal` lane (48 seeded
   malformed/out-of-domain queries)** is the same principle, and it's the design
   the lite engine was built around from the start: `calculate()` in
   [`engine.py`](../mathgate/engine.py) never raises past its own boundary and
   never guesses — see `Refused` and the `REFUSED` status path.

## The point

None of this is a claim that the lite engine here has zero bugs — it's a much
smaller, newer, independently-written codebase and hasn't had 1,116 seeded cases
run against it by anyone but its own author yet. The point is narrower: a
verification benchmark is only doing its job if it's actively trying to break the
thing it's grading, graded by something that isn't the thing itself. That's why
`proofbench_lite.py`'s oracle (`oracle_calculate`, built on Python's `ast` module)
is a different implementation from `engine.py`'s hand-written recursive-descent
parser — and why you should read both and try to break them.
