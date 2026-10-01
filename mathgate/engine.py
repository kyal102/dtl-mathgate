"""
Deterministic exact-arithmetic engine.

Grammar (recursive descent, hand-written — deliberately NOT built on Python's
``eval``/``ast`` for the main path, so the independent oracle in
``proofbench_lite.py`` — which *does* use ``ast`` — is a genuinely separate
implementation, not the same code checking itself):

    expr    := term (('+' | '-') term)*
    term    := unary (('*' | '/') unary)*
    unary   := '-' unary | power
    power   := postfix ('^' unary)?
    postfix := atom '!'*
    atom    := NUMBER | 'sqrt' '(' expr ')' | '(' expr ')'

Every value is either an exact ``Fraction`` or a ``Sqrt`` (coefficient *
sqrt(radicand), radicand square-free) so results are never rounded.
"""
from __future__ import annotations

import hashlib
import math
from dataclasses import dataclass
from fractions import Fraction
from typing import Union


class Refused(Exception):
    """Raised for malformed input or an operation outside the safe domain.

    The engine refuses rather than guesses — e.g. unbalanced parentheses,
    division/mod by zero, factorial of a negative or non-integer, a
    fractional exponent (outside this lite engine's exact-symbolic scope),
    or sqrt of a negative number.
    """


@dataclass(frozen=True)
class Sqrt:
    """Exact value ``coeff * sqrt(radicand)``, kept symbolic (never rounded).

    Invariant: ``radicand`` is square-free and >= 0. ``radicand == 1``
    never appears standalone here; callers normalize that case back to a
    plain ``Fraction`` via :func:`_simplify_sqrt`.
    """

    coeff: Fraction
    radicand: int


Value = Union[Fraction, Sqrt]

# Limits are part of this lite engine's supported input domain. In particular,
# do not disable Python's process-wide integer-to-string safety limit.
MAX_QUERY_CHARS = 4096
MAX_VALUE_BITS = 14000
MAX_EXPONENT = 10000
MAX_SURD_RADICAND = 10**12


def _bounded(v: Value) -> Value:
    coeff = v.coeff if isinstance(v, Sqrt) else v
    if max(coeff.numerator.bit_length(), coeff.denominator.bit_length()) > MAX_VALUE_BITS:
        raise Refused("exact value exceeds this lite engine's 14000-bit size bound")
    return v


# ---------------------------------------------------------------------------
# Tokenizer
# ---------------------------------------------------------------------------

_OPS = set("+-*/^()!")


def _tokenize(text: str):
    tokens = []
    i, n = 0, len(text)
    while i < n:
        c = text[i]
        if c.isspace():
            i += 1
            continue
        if c.isdigit() or c == ".":
            j = i
            seen_dot = False
            while j < n and (text[j].isdigit() or (text[j] == "." and not seen_dot)):
                if text[j] == ".":
                    seen_dot = True
                j += 1
            tokens.append(("NUM", text[i:j]))
            i = j
            continue
        if c.isalpha():
            j = i
            while j < n and text[j].isalpha():
                j += 1
            word = text[i:j]
            if word not in ("sqrt", "pi"):
                raise Refused(f"unknown identifier '{word}'")
            tokens.append(("ID", word))
            i = j
            continue
        if c in _OPS:
            tokens.append((c, c))
            i += 1
            continue
        raise Refused(f"unexpected character '{c}'")
    return tokens


# ---------------------------------------------------------------------------
# Parser + evaluator (single pass, recursive descent)
# ---------------------------------------------------------------------------

class _Parser:
    def __init__(self, tokens):
        self.toks = tokens
        self.pos = 0

    def _peek(self):
        return self.toks[self.pos] if self.pos < len(self.toks) else None

    def _advance(self):
        tok = self._peek()
        self.pos += 1
        return tok

    def _expect(self, kind):
        tok = self._advance()
        if tok is None or tok[0] != kind:
            raise Refused(f"expected '{kind}', got {tok[1] if tok else 'end of input'}")
        return tok

    def parse(self) -> Value:
        if not self.toks:
            raise Refused("empty expression")
        val = self._expr()
        if self._peek() is not None:
            raise Refused(f"unexpected trailing token '{self._peek()[1]}'")
        return val

    def _expr(self) -> Value:
        val = self._term()
        while self._peek() and self._peek()[0] in ("+", "-"):
            op = self._advance()[0]
            rhs = self._term()
            val = _add(val, rhs) if op == "+" else _add(val, _neg(rhs))
        return val

    def _term(self) -> Value:
        val = self._unary()
        while self._peek() and self._peek()[0] in ("*", "/"):
            op = self._advance()[0]
            rhs = self._unary()
            val = _mul(val, rhs) if op == "*" else _div(val, rhs)
        return val

    def _power(self) -> Value:
        val = self._postfix()
        if self._peek() and self._peek()[0] == "^":
            self._advance()
            exp = self._unary()
            val = _pow(val, exp)
        return val

    def _unary(self) -> Value:
        if self._peek() and self._peek()[0] == "-":
            self._advance()
            return _neg(self._unary())
        return self._power()

    def _postfix(self) -> Value:
        val = self._atom()
        while self._peek() and self._peek()[0] == "!":
            self._advance()
            val = _factorial(val)
        return val

    def _atom(self) -> Value:
        tok = self._advance()
        if tok is None:
            raise Refused("unexpected end of input")
        kind, text = tok
        if kind == "NUM":
            return _num(text)
        if kind == "ID" and text == "pi":
            raise Refused("pi is not exact — this lite engine only returns exact results")
        if kind == "ID" and text == "sqrt":
            self._expect("(")
            inner = self._expr()
            self._expect(")")
            return _sqrt(inner)
        if kind == "(":
            inner = self._expr()
            self._expect(")")
            return inner
        raise Refused(f"unexpected token '{text}'")


def _num(text: str) -> Fraction:
    if text.count(".") > 1:
        raise Refused(f"malformed number '{text}'")
    return _bounded(Fraction(text))


# ---------------------------------------------------------------------------
# Exact arithmetic over Fraction | Sqrt
# ---------------------------------------------------------------------------

def _simplify_sqrt(coeff: Fraction, radicand: int) -> Value:
    if radicand < 0:
        raise Refused("sqrt of a negative number is not real-exact in this engine")
    if radicand == 0:
        return Fraction(0)
    root = math.isqrt(radicand)
    if root * root == radicand:
        return _bounded(coeff * root)
    if radicand > MAX_SURD_RADICAND:
        raise Refused("non-square radicand exceeds this lite engine's factorization bound (10^12)")
    extracted = 1
    r = radicand
    d = 2
    while d * d <= r:
        while r % (d * d) == 0:
            r //= d * d
            extracted *= d
        d += 1
    coeff = _bounded(coeff * extracted)
    if r == 1:
        return coeff
    return Sqrt(coeff, r)


def _sqrt(v: Value) -> Value:
    if isinstance(v, Sqrt):
        raise Refused("nested sqrt of a symbolic value is out of scope for this lite engine")
    if v.denominator != 1:
        raise Refused("sqrt of a non-integer is out of scope for this lite engine")
    return _simplify_sqrt(Fraction(1), int(v))


def _neg(v: Value) -> Value:
    if isinstance(v, Sqrt):
        return Sqrt(-v.coeff, v.radicand)
    return -v


def _add(a: Value, b: Value) -> Value:
    if isinstance(a, Fraction) and isinstance(b, Fraction):
        return _bounded(a + b)
    a_rad = a.radicand if isinstance(a, Sqrt) else 1
    b_rad = b.radicand if isinstance(b, Sqrt) else 1
    if a_rad != b_rad:
        raise Refused(
            f"cannot combine unlike surds (sqrt({a_rad}) and sqrt({b_rad})) "
            "into a single exact value in this lite engine"
        )
    a_coeff = a.coeff if isinstance(a, Sqrt) else a
    b_coeff = b.coeff if isinstance(b, Sqrt) else b
    return _simplify_sqrt(a_coeff + b_coeff, a_rad)


def _mul(a: Value, b: Value) -> Value:
    if isinstance(a, Fraction) and isinstance(b, Fraction):
        return _bounded(a * b)
    a_rad = a.radicand if isinstance(a, Sqrt) else 1
    a_coeff = a.coeff if isinstance(a, Sqrt) else a
    b_rad = b.radicand if isinstance(b, Sqrt) else 1
    b_coeff = b.coeff if isinstance(b, Sqrt) else b
    return _simplify_sqrt(a_coeff * b_coeff, a_rad * b_rad)


def _div(a: Value, b: Value) -> Value:
    if isinstance(b, Sqrt) or (isinstance(b, Fraction) and b == 0):
        if isinstance(b, Fraction) and b == 0:
            raise Refused("division by zero")
        raise Refused("division by a symbolic surd is out of scope for this lite engine")
    if isinstance(a, Sqrt):
        return _bounded(Sqrt(a.coeff / b, a.radicand))
    return _bounded(a / b)


def _pow(base: Value, exp: Value) -> Value:
    if isinstance(exp, Sqrt):
        raise Refused("symbolic exponent is out of scope for this lite engine")
    if exp.denominator != 1:
        raise Refused("non-integer exponent is out of scope for this lite engine (would not be exact)")
    e = int(exp)
    if abs(e) > MAX_EXPONENT:
        raise Refused("exponent exceeds this lite engine's magnitude bound (10000)")
    if isinstance(base, Sqrt):
        if e < 0:
            raise Refused("negative exponent on a symbolic surd is out of scope for this lite engine")
        result: Value = Fraction(1)
        for _ in range(e):
            result = _mul(result, base)
        return result
    if e == 0:
        if base == 0:
            raise Refused("0^0 is undefined")
        return Fraction(1)
    # Refuse oversized powers before allocating them. This lower bound is
    # conservative; the exact result is checked again after computation.
    base_bits = max(base.numerator.bit_length(), base.denominator.bit_length())
    if (base_bits - 1) * abs(e) + 1 > MAX_VALUE_BITS:
        raise Refused("exact power exceeds this lite engine's 14000-bit size bound")
    if e > 0:
        return _bounded(base ** e)
    if base == 0:
        raise Refused("division by zero (negative exponent of 0)")
    return _bounded(Fraction(1) / (base ** (-e)))


def _factorial(v: Value) -> Value:
    if isinstance(v, Sqrt) or v.denominator != 1:
        raise Refused("factorial is only defined here for non-negative integers")
    n = int(v)
    if n < 0:
        raise Refused("factorial of a negative number is undefined")
    if n > 5000:
        raise Refused("factorial argument too large for this lite engine's safety bound (5000)")
    return _bounded(Fraction(math.factorial(n)))


# ---------------------------------------------------------------------------
# Public result type + certificate
# ---------------------------------------------------------------------------

def _render(v: Value) -> str:
    if isinstance(v, Fraction):
        if v.denominator == 1:
            return str(v.numerator)
        return f"{v.numerator}/{v.denominator}"
    coeff_str = "" if v.coeff == 1 else ("-" if v.coeff == -1 else _render(v.coeff))
    sign = "-" if coeff_str == "-" else ""
    prefix = "" if coeff_str in ("", "-") else coeff_str + "*"
    return f"{sign}{prefix}sqrt({v.radicand})"


def _exactness(v: Value) -> str:
    if isinstance(v, Sqrt):
        return "exact_irrational_symbolic"
    return "exact_integer" if v.denominator == 1 else "exact_rational"


@dataclass(frozen=True)
class Result:
    query: str
    status: str          # "OK" or "REFUSED"
    result: str           # rendered exact value, or "" if refused
    exactness: str        # exactness class, or "" if refused
    reason: str           # populated only when refused
    certificate_hash: str  # sha256 over (normalized query, status, result) — replayable

    def to_dict(self) -> dict:
        return {
            "query": self.query,
            "status": self.status,
            "result": self.result,
            "exactness": self.exactness,
            "reason": self.reason,
            "certificate_hash": self.certificate_hash,
        }


def _certificate(query: str, status: str, result: str) -> str:
    canonical = f"{query}|{status}|{result}"
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def calculate(query: str) -> Result:
    """Evaluate a string ``query`` exactly. Malformed/out-of-scope
    input comes back as a ``Result`` with ``status == "REFUSED"``, sealed
    with the same certificate scheme as a successful result, so a refusal
    is just as replayable and auditable as an answer."""
    normalized = query.strip()
    try:
        if len(normalized) > MAX_QUERY_CHARS:
            raise Refused("expression exceeds this lite engine's length bound (4096 characters)")
        tokens = _tokenize(normalized)
        value = _Parser(tokens).parse()
        rendered = _render(value)
    except Refused as exc:
        cert = _certificate(normalized, "REFUSED", "")
        return Result(normalized, "REFUSED", "", "", str(exc), cert)
    except (ZeroDivisionError, ValueError, OverflowError) as exc:
        cert = _certificate(normalized, "REFUSED", "")
        return Result(normalized, "REFUSED", "", "", f"invalid expression: {exc}", cert)
    except RecursionError:
        cert = _certificate(normalized, "REFUSED", "")
        return Result(normalized, "REFUSED", "", "", "expression nesting exceeds this runtime's safe parsing depth", cert)
    cert = _certificate(normalized, "OK", rendered)
    return Result(normalized, "OK", rendered, _exactness(value), "", cert)
