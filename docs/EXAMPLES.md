# Examples

```bash
$ python -m mathgate "12 * (3 + 4)"
12 * (3 + 4)
  -> 84  (exact_integer)
     sealed sha256:6335247b30de6f51...

$ python -m mathgate "2^64"
2^64
  -> 18446744073709551616  (exact_integer)
     sealed sha256:0cacfc9c6e2c487f...

$ python -m mathgate "1/3 + 1/6"
1/3 + 1/6
  -> 1/2  (exact_rational)
     sealed sha256:a04cc202d3e61b5c...

$ python -m mathgate "sqrt(8)"
sqrt(8)
  -> 2*sqrt(2)  (exact_irrational_symbolic)
     sealed sha256:2168f777bb81ef1a...

$ python -m mathgate "1 + + * 2 )("
1 + + * 2 )(
  -> REFUSED: unexpected token '+'
     sealed sha256:8d1fb41ddfd9a51e...

$ python -m mathgate --json "1/0"
{
  "query": "1/0",
  "status": "REFUSED",
  "result": "",
  "exactness": "",
  "reason": "division by zero",
  "certificate_hash": "eef4f0d4170c6fd2..."
}
```

## Certificates are replayable

The same query always produces the same `certificate_hash` — run it twice, get
the same seal:

```bash
$ python -m mathgate --json "12*(3+4)" | python -c "import json,sys; print(json.load(sys.stdin)['certificate_hash'])"
6335247b30de6f51...
$ python -m mathgate --json "12*(3+4)" | python -c "import json,sys; print(json.load(sys.stdin)['certificate_hash'])"
6335247b30de6f51...
```

## Run the verification suite

```bash
$ python -m mathgate --bench
ProofBench-X Lite
  total cases            240
  passed (oracle-graded) 192
  refused as expected    48
  failed                 0
  unexpected refusals    0
  unexpected successes   0
  certificate drift      0
    arithmetic         48/48
    sign_regression    48/48
    bigint_exactness   48/48
    refusal            48/48
    symbolic_sqrt      48/48
```
