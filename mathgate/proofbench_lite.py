"""
ProofBench-X Lite — a small, deterministic, reproducible verification suite
for the ``mathgate`` lite engine.

This is NOT the hosted engine's 1,116-case ProofBench X corpus (that engine
and its full case set are proprietary — see LICENSING.md). This is a
smaller, honest, fully public suite for the lite engine only, graded by an
**independently implemented oracle** (below) that does not share a single
line of code with ``engine.py``'s hand-written recursive-descent parser —
it walks Python's own ``ast`` module instead. Two different implementations
agreeing is a real cross-check; one implementation grading itself is not.

Run it:  python -m mathgate --bench
"""
from __future__ import annotations

import ast
import random
from dataclasses import dataclass
from fractions import Fraction

from .engine import calculate

SEED = 20260622  # fixed, so every run (yours and ours) produces the same cases


# ---------------------------------------------------------------------------
# Independent oracle: evaluates the same query text via Python's ast module,
# operating on fractions.Fraction throughout so it is exact, not float.
# ---------------------------------------------------------------------------

class OracleRefused(Exception):
    pass


def _oracle_eval(node):
    if isinstance(node, ast.Expression):
        return _oracle_eval(node.body)
    if isinstance(node, ast.BinOp):
        left = _oracle_eval(node.left)
        right = _oracle_eval(node.right)
        if isinstance(node.op, ast.Add):
            return left + right
        if isinstance(node.op, ast.Sub):
            return left - right
        if isinstance(node.op, ast.Mult):
            return left * right
        if isinstance(node.op, ast.Div):
            if right == 0:
                raise OracleRefused("division by zero")
            return left / right
        if isinstance(node.op, ast.Pow):
            if right.denominator != 1:
                raise OracleRefused("non-integer exponent")
            e = int(right)
            if e < 0:
                if left == 0:
                    raise OracleRefused("division by zero")
                return Fraction(1) / (left ** (-e))
            return left ** e
        raise OracleRefused(f"unsupported operator {node.op}")
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.USub):
        return -_oracle_eval(node.operand)
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
        return Fraction(node.value) if isinstance(node.value, int) else Fraction(str(node.value))
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "factorial":
        (arg,) = node.args
        n = _oracle_eval(arg)
        if n.denominator != 1 or n < 0:
            raise OracleRefused("factorial domain")
        import math
        return Fraction(math.factorial(int(n)))
    raise OracleRefused(f"unsupported node {type(node).__name__}")


def oracle_calculate(py_expr: str) -> Fraction:
    """Grade a plain-arithmetic query independently, via ``ast`` + ``Fraction``.
    ``py_expr`` must already be valid Python syntax (``factorial(n)`` for ``n!``,
    ``**`` for ``^``) — see :func:`_to_python` in the case generator."""
    tree = ast.parse(py_expr, mode="eval")
    return _oracle_eval(tree.body)


# ---------------------------------------------------------------------------
# Deterministic case generation, five lanes
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Case:
    lane: str
    query: str
    expect: str  # "OK" or "REFUSED"


def _gen_arithmetic(rng: random.Random, n: int) -> list[Case]:
    cases = []
    ops = ["+", "-", "*", "/"]
    for _ in range(n):
        a, b, c = (rng.randint(-99, 99) for _ in range(3))
        op1, op2 = rng.choice(ops), rng.choice(ops)
        b = b or 1
        c = c or 1
        cases.append(Case("arithmetic", f"{a} {op1} {b} {op2} {c}", "OK"))
    return cases


def _gen_sign_regression(rng: random.Random, n: int) -> list[Case]:
    # regression lane for the exact bug class the hosted engine's ProofBench
    # X caught: sign drop on a negated factor, e.g. (-A)*B.
    templates = [
        "(-{a})*{b}", "{a}*(-{b})", "(-{a})*(-{b})", "-({a}*{b})",
        "-{a}*{b}", "{a}*-{b}", "-(-{a})", "-(-{a}*{b})",
    ]
    cases = []
    for _ in range(n):
        a, b = rng.randint(1, 999), rng.randint(1, 999)
        tmpl = rng.choice(templates)
        cases.append(Case("sign_regression", tmpl.format(a=a, b=b), "OK"))
    return cases


def _gen_bigint(rng: random.Random, n: int) -> list[Case]:
    cases = []
    for i in range(n):
        if i % 2 == 0:
            cases.append(Case("bigint_exactness", f"{rng.randint(50, 400)}!", "OK"))
        else:
            base = rng.randint(2, 97)
            exp = rng.randint(50, 400)
            cases.append(Case("bigint_exactness", f"{base}^{exp}", "OK"))
    return cases


def _gen_refusal(rng: random.Random, n: int) -> list[Case]:
    pool = [
        "1 + + * 2 )(", "((1+2)", "1+2))", "", "   ", "1/0", "5//2",
        "(-5)!", "3.2!", "2^0.5", "0^0", "sqrt(-4)", "1 +", "* 3",
        "1 2 3", "3 ^ ^ 2",
    ]
    cases = []
    for i in range(n):
        cases.append(Case("refusal", pool[i % len(pool)], "REFUSED"))
    return cases


def _gen_symbolic_sqrt(rng: random.Random, n: int) -> list[Case]:
    cases = []
    for _ in range(n):
        k = rng.randint(2, 40)
        cases.append(Case("symbolic_sqrt", f"sqrt({k})*sqrt({k})", "OK"))
    return cases


def generate_cases(per_lane: int = 48) -> list[Case]:
    rng = random.Random(SEED)
    cases: list[Case] = []
    cases += _gen_arithmetic(rng, per_lane)
    cases += _gen_sign_regression(rng, per_lane)
    cases += _gen_bigint(rng, per_lane)
    cases += _gen_refusal(rng, per_lane)
    cases += _gen_symbolic_sqrt(rng, per_lane)
    return cases


def _to_python(query: str) -> str:
    """Rewrite mathgate surface syntax into valid Python for the ast oracle.
    Only used for the arithmetic/sign_regression/bigint lanes (no sqrt, no !
    in those lanes except via this helper for bigint factorials)."""
    text = query.replace("^", "**")
    if text.rstrip().endswith("!"):
        text = f"factorial({text.rstrip()[:-1].strip()})"
    return text


@dataclass
class BenchResult:
    total: int
    passed: int
    failed: int
    refused_as_expected: int
    unexpected_refusals: int
    unexpected_successes: int
    certificate_drift: int
    by_lane: dict


def run(per_lane: int = 48) -> BenchResult:
    cases = generate_cases(per_lane)
    passed = failed = refused_ok = unexpected_refusal = unexpected_success = drift = 0
    by_lane: dict = {}

    for case in cases:
        lane_stats = by_lane.setdefault(case.lane, {"total": 0, "ok": 0})
        lane_stats["total"] += 1

        r1 = calculate(case.query)
        r2 = calculate(case.query)  # replay: same query -> same certificate, always
        if r1.certificate_hash != r2.certificate_hash:
            drift += 1

        if case.expect == "REFUSED":
            if r1.status == "REFUSED":
                refused_ok += 1
                lane_stats["ok"] += 1
            else:
                unexpected_success += 1
            continue

        if r1.status == "REFUSED":
            unexpected_refusal += 1
            continue

        if case.lane == "symbolic_sqrt":
            # sqrt(k)*sqrt(k) must be exactly k, checked independently (no ast needed).
            k = int(case.query.split("(")[1].split(")")[0])
            ok = r1.result == str(k) and r1.exactness == "exact_integer"
        else:
            try:
                oracle_val = oracle_calculate(_to_python(case.query))
            except OracleRefused:
                oracle_val = None
            ok = oracle_val is not None and r1.result == (
                str(oracle_val.numerator) if oracle_val.denominator == 1
                else f"{oracle_val.numerator}/{oracle_val.denominator}"
            )

        if ok:
            passed += 1
            lane_stats["ok"] += 1
        else:
            failed += 1

    return BenchResult(
        total=len(cases),
        passed=passed,
        failed=failed,
        refused_as_expected=refused_ok,
        unexpected_refusals=unexpected_refusal,
        unexpected_successes=unexpected_success,
        certificate_drift=drift,
        by_lane=by_lane,
    )
