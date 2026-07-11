# DTL MathGate (lite) limitations

- **This is the lite engine, not the hosted engine.** It covers exact integer/rational
  arithmetic, symbolic square roots (`sqrt(8)` -> `2*sqrt(2)`, never rounded), integer
  powers (positive, negative, zero) and factorial. The hosted SuperMath Lab additionally
  does symbolic calculus, linear algebra, proof mode, and a 1,116-case verification
  corpus — none of that is in this repository (see [LICENSING.md](../LICENSING.md)).
- **No decimals in results.** Every output is an exact `Fraction` or `coeff*sqrt(radicand)`
  — there is no floating-point approximation mode. `pi` and non-integer exponents are
  refused rather than approximated, because an approximation isn't exact and this engine
  doesn't guess.
- **Unlike surds don't combine.** `sqrt(2) + sqrt(3)` is refused, not approximated —
  this lite engine only does exact combination (matching radicands, e.g.
  `sqrt(2)*sqrt(2) = 2` or `sqrt(8) = 2*sqrt(2)`), not general symbolic simplification.
- **Factorial is capped at 5000** as a safety bound against unbounded compute in CI/demo
  contexts, not a mathematical limitation.
- **ProofBench-X Lite is 240 cases, not 1,116.** It's a public, honest, independently
  oracle-graded subset for *this* engine only — see [BUGS_FOUND.md](BUGS_FOUND.md) for
  why an independent oracle (not the engine checking itself) matters, and
  [ProofBench X](https://jvi3.com/packages#tab-supermath) for the hosted engine's full
  corpus and live scoreboard.
- **Refuses rather than guesses.** Malformed input (unbalanced parens, division by
  zero, factorial of a negative/non-integer, fractional exponents, sqrt of a negative
  number) always comes back `REFUSED` with a reason — never a best-effort answer.
