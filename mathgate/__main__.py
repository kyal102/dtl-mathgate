"""CLI:  python -m mathgate "12*(3+4)"   |   --demo   |   --bench   |   --json"""
import argparse
import json
import sys

from .engine import calculate
from .proofbench_lite import run as run_bench

DEMO = [
    "12 * (3 + 4)", "2^64", "1/3 + 1/6", "sqrt(2)*sqrt(2)", "20!",
    "144/12 + 7", "(-3)*4", "sqrt(8)", "1 + + * 2 )(", "1/0",
]


def _print_result(r, as_json):
    if as_json:
        print(json.dumps(r.to_dict(), indent=2))
        return
    print(f"{r.query}")
    if r.status == "OK":
        print(f"  -> {r.result}  ({r.exactness})")
    else:
        print(f"  -> REFUSED: {r.reason}")
    print(f"     sealed sha256:{r.certificate_hash[:16]}...")


def _print_bench(result, as_json):
    if as_json:
        print(json.dumps(
            {
                "total_cases": result.total,
                "passed": result.passed,
                "failed": result.failed,
                "refused_as_expected": result.refused_as_expected,
                "unexpected_refusals": result.unexpected_refusals,
                "unexpected_successes": result.unexpected_successes,
                "certificate_drift": result.certificate_drift,
                "by_lane": result.by_lane,
            },
            indent=2,
        ))
        return
    print("ProofBench-X Lite")
    print(f"  total cases            {result.total}")
    print(f"  passed (oracle-graded) {result.passed}")
    print(f"  refused as expected    {result.refused_as_expected}")
    print(f"  failed                 {result.failed}")
    print(f"  unexpected refusals    {result.unexpected_refusals}")
    print(f"  unexpected successes   {result.unexpected_successes}")
    print(f"  certificate drift      {result.certificate_drift}")
    for lane, stats in result.by_lane.items():
        print(f"    {lane:<18} {stats['ok']}/{stats['total']}")


def main(argv=None):
    ap = argparse.ArgumentParser(
        prog="mathgate",
        description="Deterministic exact-arithmetic engine with replayable certificates.",
    )
    ap.add_argument("query", nargs="?", help='e.g. "12*(3+4)"')
    ap.add_argument("--demo", action="store_true", help="run built-in examples")
    ap.add_argument("--bench", action="store_true", help="run ProofBench-X Lite (240 seeded, oracle-graded cases)")
    ap.add_argument("--json", action="store_true", help="emit JSON")
    args = ap.parse_args(argv)

    if args.bench:
        result = run_bench()
        _print_bench(result, args.json)
        return 1 if (result.failed or result.unexpected_refusals or result.unexpected_successes or result.certificate_drift) else 0

    if args.demo:
        for q in DEMO:
            _print_result(calculate(q), args.json)
            if not args.json:
                print()
        return 0

    if not args.query:
        ap.print_help()
        return 2

    r = calculate(args.query)
    _print_result(r, args.json)
    return 1 if r.status == "REFUSED" else 0


if __name__ == "__main__":
    sys.exit(main())
