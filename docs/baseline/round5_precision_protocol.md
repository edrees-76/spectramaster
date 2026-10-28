# Round-5 review: full-precision proof of the round-4 activity criteria, M4 (pre-registered)

Written 2026-10-28, before any change to the harness. Codex round-5 review
(`D:\DSpectraMaster_reviews\codex_review_round5.md`, main 865c1ec), finding M4, checked on the code
(`validation/round4_activity.py`, `BEFORE` and `criteria`) before this protocol was written.

**Finding.** `round4_activity_protocol.md` registered "as before (relative 1e-9)" for RA.C2-C4 and the
Cs-137 row of RA.C6 (and 1e-6 for the RA.C1 threshold). The harness compares with reference values
printed to 6-7 digits, so it checks relative 1e-6; the protocol's results disclose this and list
full-precision values "identical in every digit", but no committed file holds the values of the
engine before the change. The PASS therefore does not prove 1e-9.

**Values before (collected before this protocol, disclosed).** The R4-A harness as committed with
its results (`git show c892145:spectramaster/validation/round4_activity.py`) was run, unchanged,
against the engine of two detached checkouts: a8d5346 (engine 1.14.0, the protocol's "before") and
c892145 (engine 1.15.0, the R4-A result). The script, run with `python -I` from a folder outside the
repository, with the checkout and the harness as arguments:

```python
import importlib.util, json, os, sys
root, harness = sys.argv[1], sys.argv[2]
sys.path.insert(0, root)
spec = importlib.util.spec_from_file_location("h", harness)
h = importlib.util.module_from_spec(spec)
spec.loader.exec_module(h)
import spectramaster
assert os.path.normcase(os.path.abspath(spectramaster.__file__)).startswith(os.path.normcase(os.path.abspath(root)))
print(json.dumps(h.run(), default=lambda o: o.item() if hasattr(o, "item") else repr(o)))
```

Outputs (key `commit_root` removed): `after_R5F/round4_activity_engine_1.14.0_a8d5346.json` and
`after_R5F/round4_activity_engine_1.15.0_c892145.json`, committed with this protocol.

## Change

1. `round4_activity.BEFORE` holds the full-precision values of the 1.14.0 run (read from the
   committed file), and `criteria` compares RA.C2, RA.C3, RA.C4 and the Cs-137 row of RA.C6 at
   relative 1e-9 and the RA.C1 threshold at relative 1e-6, as registered in 2026-10-23. The comment
   about the 6-7 digit rounding is removed.
2. A harness `validation/round5_precision.py` evaluates the criteria below and writes to the fixed
   folder `after_R5F`. `after_R4A` is not rewritten.
3. No engine change (engine stays 1.24.0); no change to the round-4 limits.

## Criteria

The 11 "as before" quantities: RA.C1 decision threshold; RA.C2 no blank (threshold, limit) and no
reference peak (threshold, limit); RA.C3 Currie (threshold, limit); RA.C4 four COI; RA.C6 Cs-137 best.

| ID | quantity | limit |
|---|---|---|
| RF.C1 | the 11 quantities, engine 1.15.0 (c892145) against 1.14.0 (a8d5346), both from the committed runs | relative difference <= 1e-9 for each (the round-4 criterion at full precision); and the two runs are different engines: RA.C1 detection limit 28.19756 Bq (1.14.0) and 31.46646 Bq (1.15.0), relative difference > 0.1 |
| RF.C2 | the 11 quantities, current engine against 1.14.0 | relative difference <= 1e-9 for each |
| RF.C3 | the full-precision values printed in `round4_activity_protocol.md` (note after the results) | equal (==) to the 1.14.0 run, each of the 10 printed |
| RF.C4 | `round4_activity.criteria` on the current engine with the full-precision `BEFORE` | RA.C1-C6 PASS |
| RF.C5 | full test suite | passes; each changed existing test listed with its reason (no benchmark run: engine unchanged) |

## Limits of this proof (stated now)

- The runs on the old engines are on this Windows machine, as were the original runs; another
  platform can differ in the last digits.
- It proves the registered criteria, nothing beyond them (RA.C5 and the Co-60 part of RA.C6 were
  already full-precision comparisons in the harness).
