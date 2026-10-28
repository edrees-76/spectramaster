"""Round-5 review, H4: a TKA file named .txt (docs/baseline/round5_tka_protocol.md).

    python -m spectramaster.validation.round5_tka [--collect FILE]

Synthetic files, the test corpus and, when present, the public spectra
(D:/SpectraMaster_public_data): only file names, formats and sums are written.  ``--collect FILE``
writes the raw observations only (used for the "before" values); without it the criteria are
evaluated against ``docs/baseline/after_R5D/round5_tka_before.json``.
"""
from __future__ import annotations

import argparse
import json
import shutil
import sys
import tempfile
from datetime import datetime
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
OUT = REPO / "docs" / "baseline" / "after_R5D"
BEFORE_JSON = OUT / "round5_tka_before.json"
PUBLIC = Path("D:/SpectraMaster_public_data")
TXT_ROOTS = (REPO / "test_corpus", REPO / "tests", PUBLIC)


def _read(path, fmt=None):
    from spectramaster.convert import read_spectra
    try:
        r, used = read_spectra(path, fmt)
    except Exception as exc:
        return f"{type(exc).__name__}: {exc}"[:200]
    s = r[0]
    return [used.key, len(s.counts), float(sum(s.counts)), s.live_time, s.real_time]


def _synthetic() -> dict:
    from spectramaster.convert import resolve_format, write_spectrum
    from spectramaster.formats.base import detect
    from spectramaster.model import Spectrum
    s = Spectrum(counts=[i % 31 for i in range(1024)], live_time=100.0, real_time=110.0,
                 energy_coeffs=[0.0, 0.5], start_time=datetime(2024, 1, 1, 10))
    zero_start = Spectrum(counts=[0, 0] + [i % 31 for i in range(2, 1024)], live_time=100.0, real_time=110.0)
    # a one-column spectrum whose first two counts pass the TKA time test (0 < c0 <= c1 <= 10 c0)
    timelike = Spectrum(counts=[i % 31 + 1 for i in range(1024)], live_time=100.0, real_time=110.0)
    tmp = Path(tempfile.mkdtemp(prefix="r5d_"))
    out = {}
    try:
        for label, spec, key, name in (("tka as .txt", s, "tka", "a.txt"),
                                       ("tka as .tka", s, "tka", "a.tka"),
                                       ("ascii1 starting with zeros as .txt", zero_start, "ascii1", "z.txt"),
                                       ("ascii1 as .txt", timelike, "ascii1", "b.txt")):
            p = tmp / ("src" + resolve_format(key).default_ext)
            write_spectrum(spec, p, resolve_format(key))
            q = tmp / name
            shutil.copyfile(p, q)
            f, how, cands = detect(q)
            out[label] = {"detected": f.key if f else None, "how": how,
                          "candidates": sorted(c.key for c in cands), "read": _read(q),
                          "read_as_tka": _read(q, resolve_format("tka")),
                          "read_as_ascii1": _read(q, resolve_format("ascii1"))}
            p.unlink()
            q.unlink()
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    return out


def _txt_files() -> dict:
    from spectramaster.formats.base import detect
    out = {}
    for root in TXT_ROOTS:
        if not root.is_dir():
            continue
        for p in sorted(root.rglob("*")):
            if p.is_file() and p.suffix.lower() == ".txt":
                f, how, cands = detect(p)
                key = p.relative_to(root).as_posix()
                out[f"{root.name}/{key}"] = [f.key if f else None, how, sorted(c.key for c in cands)]
    return out


def collect() -> dict:
    from spectramaster.formats import load_all
    from spectramaster.lab.session import ENGINE_VERSION
    from spectramaster.validation import any_extension
    load_all()
    return {"engine": ENGINE_VERSION, "synthetic": _synthetic(), "txt": _txt_files(),
            "any_extension": any_extension.collect()}


def criteria(res: dict, before: dict) -> dict:
    c = {}
    sy, sb = res["synthetic"], before["synthetic"]
    t = sy["tka as .txt"]
    ok = (t["detected"] is None and t["how"] == "ambiguous" and t["candidates"] == ["ascii1", "tka"]
          and isinstance(t["read"], str) and t["read"].startswith("FormatError")
          and "choose the input format" in t["read"]
          and t["read_as_tka"] == ["tka", 1024, 15345.0, 100.0, 110.0])
    c["RD.C1"] = (ok, f"TKA named .txt: {t['how']} {t['candidates']}, read: {t['read']}; chosen TKA: "
                      f"{t['read_as_tka']} (before: {sb['tka as .txt']['how']}, {sb['tka as .txt']['read']})")
    ok = all(sy[k] == sb[k] for k in ("tka as .tka", "ascii1 starting with zeros as .txt"))
    c["RD.C2"] = (ok, f".tka: {sy['tka as .tka']['read']}; one-column .txt starting with zeros: "
                      f"{sy['ascii1 starting with zeros as .txt']['how']} {sy['ascii1 starting with zeros as .txt']['read']}")
    a = sy["ascii1 as .txt"]
    ok = (a["how"] == "ambiguous" and a["read_as_ascii1"] == sb["ascii1 as .txt"]["read"])
    c["RD.C3"] = (ok, f"one-column .txt whose first two counts look like times: {a['how']} {a['candidates']}; "
                      f"chosen ASCII-1: {a['read_as_ascii1']} (before read as {sb['ascii1 as .txt']['read']})")
    changed = sorted(k for k in set(res["txt"]) | set(before["txt"]) if res["txt"].get(k) != before["txt"].get(k))
    c["RD.C4"] = (not changed and len(res["txt"]) == len(before["txt"]),
                  f"{len(res['txt'])} .txt files, detection changed for {len(changed)}: {changed[:10]}")
    ra = {r["file"]: r for r in res["any_extension"]["rows"]}
    rb = {r["file"]: r for r in before["any_extension"]["rows"]}
    diff = sorted(f for f in set(ra) | set(rb) if ra.get(f) != rb.get(f))
    c["RD.C5"] = (not diff, f"{len(ra)} files with own name, .xyz and no extension: changed {diff[:10]}")
    return c


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--collect")
    a = ap.parse_args(argv)
    res = collect()
    if a.collect:
        Path(a.collect).write_text(json.dumps(res, indent=1, ensure_ascii=False, default=str), encoding="utf-8")
        return 0
    before = json.loads(BEFORE_JSON.read_text(encoding="utf-8"))
    c = criteria(res, before)
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "round5_tka.json").write_text(json.dumps({"result": res, "criteria": c}, indent=1, ensure_ascii=False,
                                                    default=str), encoding="utf-8")
    lines = ["# Round-5 review, H4: a TKA file named .txt", "",
             "Protocol: `docs/baseline/round5_tka_protocol.md`.", "", "| ID | result | value |", "|---|---|---|"]
    lines += [f"| {k} | {'PASS' if ok else 'FAIL'} | {v} |" for k, (ok, v) in c.items()]
    (OUT / "round5_tka.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(", ".join(f"{k}:{'PASS' if ok else 'FAIL'}" for k, (ok, _v) in c.items()))
    return 0 if all(ok for ok, _v in c.values()) else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
