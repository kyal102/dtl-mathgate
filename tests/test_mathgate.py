import unittest

from mathgate.engine import calculate
from mathgate.proofbench_lite import run


class TestEngine(unittest.TestCase):
    def test_basic_arithmetic(self):
        self.assertEqual(calculate("12*(3+4)").result, "84")
        self.assertEqual(calculate("144/12 + 7").result, "19")

    def test_exact_rational(self):
        r = calculate("1/3 + 1/6")
        self.assertEqual(r.result, "1/2")
        self.assertEqual(r.exactness, "exact_rational")

    def test_bigint_stays_exact_no_scientific_notation(self):
        r = calculate("2^64")
        self.assertEqual(r.result, "18446744073709551616")
        self.assertNotIn("e", r.result.lower())

    def test_factorial(self):
        self.assertEqual(calculate("20!").result, "2432902008176640000")

    def test_symbolic_sqrt_simplifies_perfect_square(self):
        self.assertEqual(calculate("sqrt(2)*sqrt(2)").result, "2")

    def test_symbolic_sqrt_extracts_square_factor(self):
        self.assertEqual(calculate("sqrt(8)").result, "2*sqrt(2)")

    def test_sign_drop_regression(self):
        # regression class: negated-factor sign must never be dropped
        self.assertEqual(calculate("(-3)*4").result, "-12")
        self.assertEqual(calculate("3*(-4)").result, "-12")
        self.assertEqual(calculate("(-3)*(-4)").result, "12")
        self.assertEqual(calculate("-(3*4)").result, "-12")

    def test_refuses_malformed_input(self):
        self.assertEqual(calculate("1 + + * 2 )(").status, "REFUSED")
        self.assertEqual(calculate("").status, "REFUSED")
        self.assertEqual(calculate("1+2))").status, "REFUSED")

    def test_refuses_division_by_zero(self):
        self.assertEqual(calculate("1/0").status, "REFUSED")

    def test_refuses_out_of_domain_factorial(self):
        self.assertEqual(calculate("(-5)!").status, "REFUSED")
        self.assertEqual(calculate("3.2!").status, "REFUSED")

    def test_certificate_is_replayable(self):
        a = calculate("12*(3+4)")
        b = calculate("12*(3+4)")
        self.assertEqual(a.certificate_hash, b.certificate_hash)

    def test_certificate_differs_for_different_queries(self):
        a = calculate("12*(3+4)")
        b = calculate("12*(3+5)")
        self.assertNotEqual(a.certificate_hash, b.certificate_hash)


class TestProofBenchLite(unittest.TestCase):
    def test_full_suite_passes_clean(self):
        result = run(per_lane=48)
        self.assertEqual(result.total, 240)
        self.assertEqual(result.failed, 0)
        self.assertEqual(result.unexpected_refusals, 0)
        self.assertEqual(result.unexpected_successes, 0)
        self.assertEqual(result.certificate_drift, 0)

    def test_deterministic_across_runs(self):
        r1 = run(per_lane=24)
        r2 = run(per_lane=24)
        self.assertEqual(r1.total, r2.total)
        self.assertEqual(r1.passed, r2.passed)


if __name__ == "__main__":
    unittest.main()
