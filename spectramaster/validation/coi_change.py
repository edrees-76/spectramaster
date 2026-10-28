"""Change of the first-order coincidence correction (COI) between two coincidence tables, for every
line the table describes (docs/baseline/ensdf_level_balance_protocol.md): close geometry
``tcs_mc.eps_peak(E, 0.05)`` and ``tcs_mc.peak_to_total``.  Reported, not judged.  Called by
``coincidence_ensdf_check --eb1 --old OLD_TABLE``; writes ``coi_change.json`` and ``coi_change.md``.
"""
from __future__ import annotations

import json
from pathlib import Path

from spectramaster.analysis import coincidence as co

from . import tcs_mc

E1000 = 0.05
MIN_LINE = 0.01            # br x gammas per decay of the transition
SHOWN = 20


def _eps(e):
    return tcs_mc.eps_peak(e, E1000)


def _lines() -> list[tuple[str, float]]:
    out = set()
    for name, recs in co._table()["nuclides"].items():
        for rec in recs:
            for e, i in rec["g"]:
                if float(rec["br"]) * i >= MIN_LINE:
                    out.add((name, round(float(e), 4)))
    return sorted(out)


def _factors(table: Path, lines) -> dict:
    co.TABLE = table
    co._table.cache_clear()
    co._daughters.cache_clear()
    return {(n, e): co.coi(n, e, _eps, tcs_mc.peak_to_total).factor for n, e in lines}


def run(old) -> dict:
    current = Path(co.__file__).parent / "data" / "coincidence_table.json"
    lines = _lines()
    try:
        after = _factors(current, lines)
        before = _factors(Path(old), lines)
    finally:
        _factors(current, [])
    rows = [{"nuclide": n, "keV": e, "before": round(before[(n, e)], 6), "after": round(after[(n, e)], 6),
             "rel_change": round(after[(n, e)] / before[(n, e)] - 1.0, 6) if before[(n, e)] else 0.0}
            for n, e in lines]
    changed = sorted((r for r in rows if abs(r["rel_change"]) > 1e-6), key=lambda r: -abs(r["rel_change"]))
    gs_lines = []
    for name, recs in co._table()["nuclides"].items():
        for rec in recs:
            for (e, i), s in zip(rec["g"], rec.get("gs", [])):
                if i > 0 and abs(s / i - 1.0) > 0.01:
                    gs_lines.append({"nuclide": name, "mode": rec["mode"], "keV": e, "gs_over_g": round(s / i, 4)})
    recs_gs = sorted({n for n, recs in co._table()["nuclides"].items() for r in recs if "gs" in r})
    return {"e1000": E1000, "lines": len(rows), "changed": len(changed), "rows": changed,
            "records_with_gs": recs_gs, "lines_gs_over_1pct": gs_lines}


def write(old, out: Path) -> dict:
    if not old:
        raise SystemExit("--eb1 needs --old OLD_TABLE")
    res = run(old)
    (out / "coi_change.json").write_text(json.dumps(res, indent=1), encoding="utf-8", newline="\n")
    md = ["# COI change from the scheme intensities", "",
          "Protocol: `docs/baseline/ensdf_level_balance_protocol.md` (reported, not judged).", "",
          f"Close geometry: eps_peak(1000 keV) = {E1000}, `tcs_mc.peak_to_total`. Lines of at least "
          f"{MIN_LINE:g} per decay: {res['lines']}; COI changed: {res['changed']}.", "",
          f"Nuclides with scheme intensities (`gs`): {', '.join(res['records_with_gs']) or 'none'}.", "",
          "| Nuclide | keV | COI before | COI after | change |", "|---|---|---|---|---|"]
    md += [f"| {r['nuclide']} | {r['keV']} | {r['before']} | {r['after']} | {100 * r['rel_change']:+.3f} % |"
           for r in res["rows"][:SHOWN]]
    md += ["", "Lines whose scheme intensity differs from the tabulated one by more than 1 %:", "",
           "| Nuclide | mode | keV | I^s / I |", "|---|---|---|---|"]
    md += [f"| {r['nuclide']} | {r['mode']} | {r['keV']} | {r['gs_over_g']} |" for r in res["lines_gs_over_1pct"]]
    (out / "coi_change.md").write_text("\n".join(md) + "\n", encoding="utf-8", newline="\n")
    return res
