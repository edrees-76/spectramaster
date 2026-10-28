"""Round-6 review, H2: Laval and Wallac files named .txt (docs/baseline/round6_laval_wallac_protocol.md).

    python -m spectramaster.validation.round6_laval_wallac [--collect]

Synthetic files, the test corpus and, when present, the public spectra
(D:/SpectraMaster_public_data): only file names, formats and sums are written.  The laboratory
archives, when present, are only counted (no names, no contents).  ``--collect`` writes the raw
observations only, to ``docs/baseline/after_R6B/round6_laval_wallac_before.json`` (the "before"
values); without it the criteria are evaluated against that file.
"""
from __future__ import annotations

import argparse
import json
import shutil
import sys
import tempfile
from collections import Counter
from datetime import datetime
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
OUT = REPO / "docs" / "baseline" / "after_R6B"
BEFORE_JSON = OUT / "round6_laval_wallac_before.json"
PUBLIC = Path("D:/SpectraMaster_public_data")
TXT_ROOTS = (REPO / "test_corpus", REPO / "tests", PUBLIC)
# private laboratory archives: counted only
LAB_ROOTS = (Path("D:/\u0627\u0637\u064a\u0627\u0641"),
             Path("D:/\u0645\u062e\u062a\u0628\u0631 \u0627\u0644\u062a\u062d\u0627\u0644\u064a\u0644 "
                  "\u0648 \u0627\u0644\u0642\u064a\u0627\u0633\u0627\u062a \u0627\u0644\u0627\u0634\u0639\u0627\u0639\u064a\u0629"),
             Path("D:/specter mohamed"))


def _read(path, fmt=None):
    from spectramaster.convert import read_spectra
    try:
        r, used = read_spectra(path, fmt)
    except Exception as exc:
        return f"{type(exc).__name__}: {exc}"[:200]
    s = r[0]
    return [used.key, len(s.counts), float(sum(s.counts)), s.live_time, s.real_time,
            [round(c, 6) for c in (s.energy_coeffs or [])]]


def _synthetic() -> dict:
    from spectramaster.convert import resolve_format, write_spectrum
    from spectramaster.formats.base import detect
    from spectramaster.model import Spectrum
    s = Spectrum(counts=[i % 31 for i in range(1024)], live_time=100.0, real_time=110.0,
                 energy_coeffs=[0.0, 0.5], start_time=datetime(2024, 1, 1, 10))
    # one-column spectra: an ordinary one, one whose 4th count has six digits (the Laval date line)
    # and one with exactly 1027 counts (the Wallac line count)
    plain = Spectrum(counts=[i % 31 + 1 for i in range(1024)])
    six = Spectrum(counts=[5, 7, 9, 123456] + [i % 31 + 1 for i in range(4, 1024)])
    n1027 = Spectrum(counts=[0, 0, 3] + [i % 31 for i in range(3, 1027)])
    tmp = Path(tempfile.mkdtemp(prefix="r6b_"))
    out = {}
    try:
        for label, spec, key, name in (("laval as .txt", s, "laval_ascii", "a.txt"),
                                       ("laval as .de1", s, "laval_ascii", "a.de1"),
                                       ("wallac as .txt", s, "wallac_ascii", "w.txt"),
                                       ("wallac as .001", s, "wallac_ascii", "w.001"),
                                       ("ascii1 as .txt", plain, "ascii1", "p.txt"),
                                       ("ascii1 six-digit 4th count as .txt", six, "ascii1", "s.txt"),
                                       ("ascii1 1027 counts as .txt", n1027, "ascii1", "n.txt")):
            p = tmp / ("src" + resolve_format(key).default_ext)
            write_spectrum(spec, p, resolve_format(key))
            q = tmp / name
            shutil.copyfile(p, q)
            f, how, cands = detect(q)
            out[label] = {"detected": f.key if f else None, "how": how,
                          "candidates": sorted(c.key for c in cands), "read": _read(q),
                          "read_as_own": _read(q, resolve_format(key)),
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


def _lab_counts() -> dict:
    """Detection of the .txt files of the laboratory archives, as counts only."""
    from spectramaster.formats.base import detect
    tally: Counter = Counter()
    for root in LAB_ROOTS:
        if not root.is_dir():
            continue
        for p in root.rglob("*"):
            if p.is_file() and p.suffix.lower() == ".txt":
                f, how, cands = detect(p)
                tally[f"{f.key if f else None}|{how}|{'+'.join(sorted(c.key for c in cands))}"] += 1
    return dict(sorted(tally.items()))


def collect() -> dict:
    from spectramaster.formats import load_all
    from spectramaster.lab.session import ENGINE_VERSION
    from spectramaster.validation import any_extension
    load_all()
    return {"engine": ENGINE_VERSION, "synthetic": _synthetic(), "txt": _txt_files(),
            "lab_txt": _lab_counts(), "any_extension": any_extension.collect()}


def criteria(res: dict, before: dict) -> dict:
    c = {}
    sy, sb = res["synthetic"], before["synthetic"]
    for cid, label, native, key in (("RB.C1", "laval as .txt", "laval as .de1", "laval_ascii"),
                                    ("RB.C2", "wallac as .txt", "wallac as .001", "wallac_ascii")):
        t = sy[label]
        # read as chosen: identical to the same file read under its own extension
        ok = (t["detected"] is None and t["how"] == "ambiguous" and t["candidates"] == sorted(["ascii1", key])
              and isinstance(t["read"], str) and t["read"].startswith("FormatError")
              and "choose the input format" in t["read"] and t["read_as_own"] == sy[native]["read"])
        c[cid] = (ok, f"{label}: {t['how']} {t['candidates']}, read: {t['read']}; chosen {key}: "
                      f"{t['read_as_own']} (before: {sb[label]['how']}, {sb[label]['read']})")
    ok = all(sy[k] == sb[k] for k in ("laval as .de1", "wallac as .001", "ascii1 as .txt"))
    c["RB.C3"] = (ok, f".de1: {sy['laval as .de1']['how']} {sy['laval as .de1']['read']}; "
                      f".001: {sy['wallac as .001']['how']} {sy['wallac as .001']['read']}; "
                      f"one-column .txt: {sy['ascii1 as .txt']['how']} {sy['ascii1 as .txt']['read']}")
    parts, ok = [], True
    for label in ("ascii1 six-digit 4th count as .txt", "ascii1 1027 counts as .txt"):
        a = sy[label]
        same = a["read_as_ascii1"] == sb[label]["read_as_ascii1"]
        ok = ok and same and (a == sb[label] or a["how"] == "ambiguous")
        parts.append(f"{label}: {a['how']} {a['candidates']}, chosen ASCII-1 {'identical' if same else 'CHANGED'}")
    c["RB.C4"] = (ok, "; ".join(parts))
    changed = sorted(k for k in set(res["txt"]) | set(before["txt"]) if res["txt"].get(k) != before["txt"].get(k))
    c["RB.C5"] = (not changed and len(res["txt"]) == len(before["txt"]),
                  f"{len(res['txt'])} .txt files, detection changed for {len(changed)}: {changed[:10]}")
    ra = {r["file"]: r for r in res["any_extension"]["rows"]}
    rb = {r["file"]: r for r in before["any_extension"]["rows"]}
    diff = sorted(f for f in set(ra) | set(rb) if ra.get(f) != rb.get(f))
    c["RB.C6"] = (not diff, f"{len(ra)} files with own name, .xyz and no extension: changed {diff[:10]}")
    c["RB.R1"] = (None, f"laboratory .txt files (counts only), before {before['lab_txt']}, now {res['lab_txt']}")
    return c


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--collect", action="store_true", help="write the before values (fixed file)")
    a = ap.parse_args(argv)
    res = collect()
    if a.collect:
        OUT.mkdir(parents=True, exist_ok=True)
        BEFORE_JSON.write_text(json.dumps(res, indent=1, ensure_ascii=False, default=str), encoding="utf-8")
        return 0
    before = json.loads(BEFORE_JSON.read_text(encoding="utf-8"))
    c = criteria(res, before)
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "round6_laval_wallac.json").write_text(json.dumps({"result": res, "criteria": c}, indent=1,
                                                             ensure_ascii=False, default=str), encoding="utf-8")

    def state(ok):
        return "REPORT" if ok is None else ("PASS" if ok else "FAIL")
    lines = ["# Round-6 review, H2: Laval and Wallac files named .txt", "",
             "Protocol: `docs/baseline/round6_laval_wallac_protocol.md`.", "",
             "| ID | result | value |", "|---|---|---|"]
    lines += [f"| {k} | {state(ok)} | {v} |" for k, (ok, v) in c.items()]
    (OUT / "round6_laval_wallac.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(", ".join(f"{k}:{state(ok)}" for k, (ok, _v) in c.items()))
    return 0 if all(ok is not False for ok, _v in c.values()) else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
