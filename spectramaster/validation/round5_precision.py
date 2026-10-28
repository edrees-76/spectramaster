"""Round-5 review, M4: full-precision proof of the round-4 activity criteria
(docs/baseline/round5_precision_protocol.md).

    python -m spectramaster.validation.round5_precision

Reads the R4-A harness runs on engines 1.14.0 and 1.15.0 committed in docs/baseline/after_R5F,
runs the harness on the current engine and writes ``round5_precision.json`` and
``round5_precision.md`` to that folder.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

from spectramaster.validation import round4_activity as r4

REPO = Path(__file__).resolve().parents[2]
OUT = REPO / "docs" / "baseline" / "after_R5F"
RUN_114 = OUT / "round4_activity_engine_1.14.0_a8d5346.json"
RUN_115 = OUT / "round4_activity_engine_1.15.0_c892145.json"
R4_PROTOCOL = REPO / "docs" / "baseline" / "round4_activity_protocol.md"
NAMES = ("RA.C1 threshold", "RA.C2 no blank threshold", "RA.C2 no blank limit", "RA.C2 no reference threshold",
         "RA.C2 no reference limit", "RA.C3 Currie threshold", "RA.C3 Currie limit", "RA.C4 COI Co-60 1173",
         "RA.C4 COI Co-60 1332", "RA.C4 COI Ba-133 356", "RA.C4 COI Ba-133 303", "RA.C6 Cs-137 best")


def quantities(res: dict) -> list[float]:
    """The "as before" values: 12 (the protocol counts 11, see its results)."""
    return ([res["C1"]["decision_threshold"]] + list(res["C2"]["no_blank"]) + list(res["C2"]["no_reference"])
            + list(res["C3"]["currie"]) + [float(x[2]) for x in res["C4"]["same_matrix"]]
            + [res["C6"]["cs_row"]["best"]])


def _rel(a: float, b: float) -> float:
    return abs(a - b) / abs(b)


def _printed() -> list[float]:
    """The full-precision values printed in the round-4 protocol's note, in their order."""
    text = R4_PROTOCOL.read_text(encoding="utf-8")
    note = text[text.index("At full precision"):]
    out = []
    for tok in note.split():
        tok = tok.strip("(),;.")
        whole, dot, frac = tok.partition(".")
        if dot and whole.isdigit() and frac.isdigit() and len(frac) >= 10:
            out.append(float(tok))
    return out


def criteria(cur: dict, r114: dict, r115: dict) -> dict:
    c = {}
    q114, q115, qcur = quantities(r114), quantities(r115), quantities(cur)
    worst = max(_rel(a, b) for a, b in zip(q115, q114))
    ld114, ld115 = r114["C1"]["detection_limit"], r115["C1"]["detection_limit"]
    c["RF.C1"] = (worst <= 1e-9 and _rel(ld115, ld114) > 0.1 and r114["engine"] == "1.14.0"
                  and r115["engine"] == "1.15.0",
                  f"engine {r115['engine']} against {r114['engine']}: largest relative difference {worst:.3g} "
                  f"over {len(q114)} values; RA.C1 detection limit {ld114:.5f} -> {ld115:.5f} Bq")
    worst = max(_rel(a, b) for a, b in zip(qcur, q114))
    c["RF.C2"] = (worst <= 1e-9, f"engine {cur['engine']} against 1.14.0: largest relative difference {worst:.3g}")
    printed = _printed()
    expect = q114[:5] + [q114[6]] + q114[7:11]
    c["RF.C3"] = (printed == expect, f"{len(printed)} printed values, equal to the 1.14.0 run: {printed == expect}")
    crit = r4.criteria(cur)
    c["RF.C4"] = (all(v["pass"] for v in crit.values()),
                  ", ".join(f"{k} {'PASS' if v['pass'] else 'FAIL'}" for k, v in crit.items()))
    return c


def main(argv=None) -> int:
    cur = r4.run()
    r114 = json.loads(RUN_114.read_text(encoding="utf-8"))
    r115 = json.loads(RUN_115.read_text(encoding="utf-8"))
    c = criteria(cur, r114, r115)
    table = [{"quantity": n, "1.14.0": a, "1.15.0": b, cur["engine"]: x}
             for n, a, b, x in zip(NAMES, quantities(r114), quantities(r115), quantities(cur))]
    (OUT / "round5_precision.json").write_text(json.dumps({"values": table, "criteria": c}, indent=1,
                                                          default=float), encoding="utf-8", newline="\n")
    lines = ["# Round-5 review, M4: full-precision proof of the round-4 activity criteria", "",
             "Protocol: `docs/baseline/round5_precision_protocol.md`.", "",
             "| ID | result | value |", "|---|---|---|"]
    lines += [f"| {k} | {'PASS' if ok else 'FAIL'} | {v} |" for k, (ok, v) in c.items()]
    lines += ["", "| quantity | 1.14.0 | 1.15.0 | " + cur["engine"] + " |", "|---|---|---|---|"]
    lines += [f"| {r['quantity']} | {r['1.14.0']!r} | {r['1.15.0']!r} | {float(r[cur['engine']])!r} |"
              for r in table]
    (OUT / "round5_precision.md").write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
    print(", ".join(f"{k}:{'PASS' if ok else 'FAIL'}" for k, (ok, _v) in c.items()))
    return 0 if all(ok for ok, _v in c.values()) else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
