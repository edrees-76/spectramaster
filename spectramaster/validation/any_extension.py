"""Reading spectrum files with any extension: criteria AX.C1-AX.C4.

    python -m spectramaster.validation.any_extension [--src CODE_ROOT] [--before before.json] [--out DIR]

Protocol and limits: ``docs/baseline/any_extension_protocol.md``.  ``--src`` runs the collection
with another copy of the code (the "before" export of origin/main); the collection then runs in
a child process with that root first on ``sys.path``.
"""
from __future__ import annotations

import argparse
import csv
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
CONTENT_SET = {"ascii1", "ascii2", "chandata_csv", "eml_sanderson", "iaea_ascii_dat", "npl_ascii",
               "wallac_ascii", "laval_ascii", "jcac_vax"}
EXCEL = "excel_xlsx"
KNOWN_MISDETECTED = {"write:iaea_ascii_dat"}          # own-name detection is eml_sanderson
NAMES = ("probe.xyz", "probe")


def _signature(read_spectra, path, fmt):
    import numpy as np
    try:
        spectra, _ = read_spectra(path, fmt)
    except Exception as exc:
        return "ERR " + type(exc).__name__
    return [[len(s.counts), float(np.sum(s.counts)), [round(float(c), 6) for c in s.energy_coeffs],
             s.live_time] for s in spectra]


def _files(tmp: Path):
    import numpy as np
    from spectramaster.convert import write_spectrum
    from spectramaster.formats import writable_formats
    from spectramaster.model import Spectrum
    out = []
    with open(REPO / "test_corpus" / "catalog.csv", encoding="utf-8") as fh:
        for r in csv.DictReader(fh):
            p = REPO / "test_corpus" / r["path"]
            if p.is_file():
                out.append(("corpus:" + r["path"], p))
    sp = Spectrum(counts=list(np.arange(1024, dtype=float) % 97), energy_coeffs=[0.5, 0.3], live_time=100.0,
                  real_time=101.0, sample_id="S1")
    for f in writable_formats():
        p = tmp / ("w_" + f.key + f.default_ext)
        try:
            write_spectrum(sp, p, f)
        except Exception:
            continue
        out.append(("write:" + f.key, p))
    return out


def collect() -> dict:
    """Own-name and renamed detection/signature of every file, and the negative set (current code)."""
    from spectramaster.convert import read_spectra
    from spectramaster.formats import detect_format, load_all
    load_all()
    tmp = Path(tempfile.mkdtemp(prefix="anyext_"))
    try:
        rows = []
        for label, p in _files(tmp):
            f0 = detect_format(p)
            row = {"file": label, "own": f0.key if f0 else None,
                   "own_sig": _signature(read_spectra, p, f0) if f0 else None}
            for name in NAMES:
                d = tmp / "renamed"
                d.mkdir(exist_ok=True)
                q = d / name
                shutil.copyfile(p, q)
                f1 = detect_format(q)
                row[name] = f1.key if f1 else None
                try:
                    _, used = read_spectra(q)
                    row[name + "_read"] = used.key
                    row[name + "_sig"] = _signature(read_spectra, q, used)
                except Exception as exc:
                    row[name + "_read"] = "ERR " + type(exc).__name__ + ": " + str(exc)[:200]
                    row[name + "_sig"] = None
                q.unlink()
            rows.append(row)
        neg = []
        for p in sorted([*(REPO / "spectramaster").rglob("*.py"), *(REPO / "docs").rglob("*.md")]):
            q = tmp / "neg.xyz"
            shutil.copyfile(p, q)
            f = detect_format(q)
            neg.append({"file": p.relative_to(REPO).as_posix(), "detected": f.key if f else None})
        return {"rows": rows, "negatives": neg}
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def collect_with(src: Path) -> dict:
    with tempfile.TemporaryDirectory() as td:
        out = Path(td) / "c.json"
        code = ("import sys, json, runpy; sys.path.insert(0, sys.argv[1]); "
                "m = runpy.run_path(sys.argv[2]); "
                "json.dump(m['collect'](), open(sys.argv[3], 'w', encoding='utf-8'))")
        subprocess.run([sys.executable, "-c", code, str(src), __file__, str(out)], check=True, cwd=td)
        return json.loads(out.read_text(encoding="utf-8"))


def evaluate(before: dict, after: dict) -> dict:
    b = {r["file"]: r for r in before["rows"]}
    a = {r["file"]: r for r in after["rows"]}
    c1 = [f for f in b if f not in a or (b[f]["own"], b[f]["own_sig"]) != (a[f]["own"], a[f]["own_sig"])]
    c2, c2_excluded, c4, reported = [], [], [], []
    for f, r in a.items():
        own = r["own"]
        if f in KNOWN_MISDETECTED:
            c2_excluded.append({"file": f, "own": own, **{n: r[n] for n in NAMES}})
            continue
        if own in CONTENT_SET or own == EXCEL:
            for n in NAMES:
                if r[n] != own or r[n + "_read"] != own or r[n + "_sig"] != r["own_sig"]:
                    c2.append({"file": f, "name": n, "own": own, "detected": r[n], "read": r[n + "_read"]})
        elif own is not None:
            for n in NAMES:
                if f in b and r[n] != b[f][n]:
                    c4.append({"file": f, "name": n, "before": b[f][n], "after": r[n]})
        else:
            for n in NAMES:
                if r[n] is not None:
                    reported.append({"file": f, "name": n, "detected": r[n], "read": r[n + "_read"]})
    c3 = [x for x in after["negatives"] if x["detected"] is not None]
    excluded_formats = sorted({(r["own"], r["probe.xyz"]) for r in a.values()
                               if r["file"].startswith("write:") and r["own"] not in CONTENT_SET | {EXCEL}
                               and r["own"] is not None}, key=str)
    n_c2 = sum(1 for f, r in a.items() if f not in KNOWN_MISDETECTED and (r["own"] in CONTENT_SET or r["own"] == EXCEL))
    return {
        "C1": {"id": "AX.C1", "value": len(c1), "limit": "0", "pass": not c1, "items": c1, "n": len(b)},
        "C2": {"id": "AX.C2", "value": len(c2), "limit": "0", "pass": not c2, "items": c2, "n": n_c2,
               "excluded": c2_excluded},
        "C3": {"id": "AX.C3", "value": len(c3), "limit": "0", "pass": not c3, "items": c3,
               "n": len(after["negatives"])},
        "C4": {"id": "AX.C4", "value": len(c4), "limit": "0", "pass": not c4, "items": c4},
        "reported_undetected_own_name": reported,
        "reported_other_formats_xyz": [{"own": o, "xyz": x} for o, x in excluded_formats],
    }


def report(ev: dict) -> str:
    out = ["# Any-extension reading: AX.C1-AX.C4", "",
           "Protocol: `docs/baseline/any_extension_protocol.md`.", "",
           "| ID | Value | Limit | Result | Scope |", "|---|---|---|---|---|"]
    for k, scope in (("C1", "files, own name"), ("C2", "content-set and Excel files"),
                     ("C3", "negative files as .xyz"), ("C4", "")):
        c = ev[k]
        out.append(f"| {c['id']} | {c['value']} | {c['limit']} | {'PASS' if c['pass'] else 'FAIL'} | "
                   f"{c.get('n', '')} {scope} |")
    for k in ("C1", "C2", "C3", "C4"):
        if ev[k]["items"]:
            out += ["", f"## {ev[k]['id']} failures", ""] + [f"- {json.dumps(x)}" for x in ev[k]["items"]]
    out += ["", "## AX.C2 excluded (known own-name misdetection)", ""]
    out += [f"- {json.dumps(x)}" for x in ev["C2"]["excluded"]] or ["- none"]
    out += ["", "## Reported: undetected under their own name, detected renamed", ""]
    out += [f"- {json.dumps(x)}" for x in ev["reported_undetected_own_name"]] or ["- none"]
    out += ["", "## Reported: written files of formats outside the content set, as .xyz", "",
            "| Own-name format | Detected as .xyz |", "|---|---|"]
    out += [f"| {x['own']} | {x['xyz']} |" for x in ev["reported_other_formats_xyz"]]
    return "\n".join(out) + "\n"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--src", type=Path, default=None, help="code root to collect with (default: this code)")
    ap.add_argument("--before", type=Path, default=None, help="collection of the code before the change")
    ap.add_argument("--out", type=Path, default=None)
    a = ap.parse_args(argv)
    data = collect_with(a.src) if a.src else collect()
    if a.out:
        a.out.mkdir(parents=True, exist_ok=True)
    if a.before is None:
        text = json.dumps(data, indent=1)
        if a.out:
            (a.out / "any_extension_before.json").write_text(text, encoding="utf-8")
        else:
            sys.stdout.write(text)
        return 0
    ev = evaluate(json.loads(a.before.read_text(encoding="utf-8")), data)
    text = report(ev)
    if a.out:
        (a.out / "any_extension_results.md").write_text(text, encoding="utf-8")
        (a.out / "any_extension_results.json").write_text(json.dumps({"after": data, "evaluation": ev}, indent=1),
                                                          encoding="utf-8")
    else:
        sys.stdout.write(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
