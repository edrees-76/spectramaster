"""Round-4 review, format findings (docs/baseline/round4_formats_protocol.md).

    python -m spectramaster.validation.round4_formats [--collect FILE]

Synthetic files, the test corpus and, when present, the EML/Sanderson reference spectra
(SPECTRAMASTER_REFDATA, see validation.reference): only file names, sums and flags are written.
``--collect FILE`` writes the raw observations only (used for the "before" values); without it the
criteria are evaluated against ``docs/baseline/after_R4C/round4_formats_before.json``.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import shutil
import sys
import tempfile
from datetime import datetime
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
OUT = REPO / "docs" / "baseline" / "after_R4C"
BEFORE_JSON = OUT / "round4_formats_before.json"
REFDATA = Path(os.environ.get("SPECTRAMASTER_REFDATA",
                              "D:/الاسس و المفاهيم العامة فى استخدام برامج الطيف الجامى/اطياف مرجعية"))


def _outcome(fn) -> str:
    try:
        r = fn()
    except Exception as exc:
        return f"{type(exc).__name__}: {exc}"
    return f"returned {r!r}"[:300]


# ------------------------------------------------------------------ C1 non-finite counts
def _nonfinite() -> dict:
    import numpy as np
    from spectramaster.analysis import find_peaks
    from spectramaster.model import Spectrum
    out = {}
    for label, bad in (("nan", float("nan")), ("inf", float("inf"))):
        c = [50.0] * 2048
        for i in range(-12, 13):
            c[1000 + i] += 5000.0 * math.exp(-0.5 * (i / 2.5) ** 2)
        c[300] = bad
        s = Spectrum(counts=c, live_time=100.0, energy_coeffs=[0.0, 0.5])
        out[label] = _outcome(lambda: len(find_peaks(s)))
    good = [50.0] * 2048
    for i in range(-12, 13):
        good[1000 + i] += 5000.0 * math.exp(-0.5 * (i / 2.5) ** 2)
    s = Spectrum(counts=good, live_time=100.0, energy_coeffs=[0.0, 0.5])
    out["finite"] = [round(p.energy, 6) for p in find_peaks(s)]
    try:
        from spectramaster.convert import counts_note
        out["note_nan"] = counts_note([Spectrum(counts=[1.0, float("nan")] * 10, live_time=1.0)])
        out["note_finite"] = counts_note([s])
    except ImportError:
        out["note_nan"] = out["note_finite"] = "no counts_note"
    return out


# ------------------------------------------------------------------ C2 EML / Sanderson
def _sanderson() -> dict:
    from spectramaster.formats.canberra_legacy import read_sanderson
    out = {"gemini": None, "own_writer": None, "eml": {}}
    tmp = Path(tempfile.mkdtemp(prefix="r4c_"))
    try:
        # Gemini's case: LT=100, channel 0 holds 100 counts by chance, channel 1 500 counts
        counts = [100, 500] + [10, 20] * 509
        lines = ["GEMINI CASE            LT=   100 ST= 1-JAN-24 10:00:00"]
        for k in range(0, len(counts), 10):
            lines.append("".join(f"{v:8d}" for v in counts[k:k + 10]))
        p = tmp / "gemini.dat"
        p.write_text("\r\n".join(lines) + "\r\n", encoding="latin-1")
        s = read_sanderson(p)[0]
        out["gemini"] = {"counts_0_4": list(s.counts[:4]), "live_time": s.live_time, "real_time": s.real_time,
                         "time_channels": bool(s.extra.get("time_channels")),
                         "note": s.extra.get("time_channels_note", "")}
        # our own IAEA ASCII .dat writer: live / real time in channels 0 / 1
        from spectramaster.convert import read_spectra, resolve_format, write_spectrum
        from spectramaster.model import Spectrum
        sp = Spectrum(counts=[0, 0] + [5] * 1022, live_time=1000.0, real_time=1100.0, sample_id="W")
        q = tmp / "own.dat"
        write_spectrum(sp, q, resolve_format("iaea_ascii_dat"))
        r, used = read_spectra(q)
        out["own_writer"] = {"read_as": used.key, "live_time": r[0].live_time, "real_time": r[0].real_time,
                             "sum": float(sum(r[0].counts))}
        folder = REFDATA / "2- Sanderson"
        if folder.is_dir():
            for f in sorted(folder.rglob("*"), key=lambda x: x.name):
                if not f.is_file() or f.suffix.upper() != ".DAT":
                    continue
                try:
                    s = read_sanderson(f)[0]
                except Exception as exc:
                    out["eml"][f.name] = "ERR " + type(exc).__name__
                    continue
                h = hashlib.sha256(json.dumps([float(c) for c in s.counts]).encode()).hexdigest()[:16]
                out["eml"][f.name] = [len(s.counts), float(sum(s.counts)), s.live_time, s.real_time,
                                      bool(s.extra.get("time_channels")), h]
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    return out


# ------------------------------------------------------------------ C3 CHN with E = 1 keV x channel
def _chn_unit_gain() -> dict:
    from spectramaster.convert import read_spectra, resolve_format, write_spectrum
    from spectramaster.model import Spectrum
    tmp = Path(tempfile.mkdtemp(prefix="r4c_"))
    out = {}
    try:
        for coeffs in ([0.0, 1.0], [0.0, 0.5]):
            s = Spectrum(counts=[5] * 1024, live_time=100.0, real_time=110.0, energy_coeffs=coeffs,
                         start_time=datetime(2024, 1, 1, 10))
            p = tmp / "x.chn"
            w = write_spectrum(s, p, resolve_format("ortec_chn"))
            r = read_spectra(p)[0][0]
            out[str(coeffs)] = {"warnings": w, "read_coeffs": list(r.energy_coeffs)}
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    return out


# ------------------------------------------------------------------ C4 detection
def _detection() -> dict:
    from spectramaster.convert import read_spectra, resolve_format, write_spectrum
    from spectramaster.formats.base import detect
    from spectramaster.model import Spectrum
    tmp = Path(tempfile.mkdtemp(prefix="r4c_"))
    out = {}
    try:
        s = Spectrum(counts=[i % 31 for i in range(1024)], live_time=100.0, real_time=110.0,
                     energy_coeffs=[0.0, 0.5], start_time=datetime(2024, 1, 1, 10))
        zero_start = Spectrum(counts=[0, 0] + [i % 31 for i in range(2, 1024)], live_time=100.0, real_time=110.0)
        for label, spec, key, name in (("specutils_txt as .txt", s, "specutils_txt", "a.txt"),
                                       ("tka as .xyz", s, "tka", "a.xyz"),
                                       ("ascii1 starting with zeros as .xyz", zero_start, "ascii1", "z.xyz")):
            p = tmp / ("src" + resolve_format(key).default_ext)
            write_spectrum(spec, p, resolve_format(key))
            q = tmp / name
            shutil.copyfile(p, q)
            f, how, cands = detect(q)
            row = {"detected": f.key if f else None, "how": how, "candidates": [c.key for c in cands]}
            try:
                r, used = read_spectra(q)
                row["read"] = [used.key, len(r[0].counts), float(sum(r[0].counts)), r[0].live_time, r[0].real_time]
            except Exception as exc:
                row["read"] = f"{type(exc).__name__}: {exc}"[:200]
            out[label] = row
            p.unlink()
            q.unlink()
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    from spectramaster.validation import any_extension
    out["any_extension"] = any_extension.collect()
    return out


def collect() -> dict:
    from spectramaster.lab.session import ENGINE_VERSION
    return {"engine": ENGINE_VERSION, "C1": _nonfinite(), "C2": _sanderson(), "C3": _chn_unit_gain(),
            "C4": _detection()}


EXPECTED_DETECTION_CHANGES = {("write:specutils_txt", "own"), ("write:tka", "probe.xyz"), ("write:tka", "probe")}


def criteria(res: dict, before: dict) -> dict:
    c = {}
    c1 = res["C1"]
    ok = all(c1[k].startswith("ValueError") and "non-finite" in c1[k] for k in ("nan", "inf"))
    ok = ok and c1["finite"] == before["C1"]["finite"]
    ok = ok and isinstance(c1["note_nan"], str) and "non-finite" in c1["note_nan"] and c1["note_finite"] is None
    c["RC.C1"] = (ok, f"NaN: {c1['nan']} (before: {before['C1']['nan']}); inf: {c1['inf']}; finite spectrum "
                      f"peaks {c1['finite']}; note {c1['note_nan']!r}")
    c2, b2 = res["C2"], before["C2"]
    g = c2["gemini"]
    ok = (g["counts_0_4"] == [100, 500, 10, 20] and g["live_time"] == 100.0 and g["real_time"] == 100.0
          and not g["time_channels"] and "channel 1" in g["note"])
    ok = ok and c2["own_writer"] == b2["own_writer"] and c2["own_writer"]["real_time"] == 1100.0
    ok = ok and c2["eml"] == b2["eml"] and len(c2["eml"]) > 0
    c["RC.C2"] = (ok, f"Gemini's case {g} (before {b2['gemini']}); own IAEA .dat writer {c2['own_writer']}; "
                      f"{len(c2['eml'])} EML/Sanderson files {'identical' if c2['eml'] == b2['eml'] else 'CHANGED'}, "
                      f"{sum(1 for v in c2['eml'].values() if isinstance(v, list) and v[4])} with time channels")
    c3, b3 = res["C3"], before["C3"]
    w = " ".join(c3["[0.0, 1.0]"]["warnings"])
    ok = "1 keV per channel" in w and c3["[0.0, 0.5]"] == b3["[0.0, 0.5]"]
    ok = ok and c3["[0.0, 1.0]"]["read_coeffs"] == b3["[0.0, 1.0]"]["read_coeffs"]
    c["RC.C3"] = (ok, f"E = 1 keV x channel: warnings {c3['[0.0, 1.0]']['warnings']} (before "
                      f"{b3['[0.0, 1.0]']['warnings']}); 0.5 keV/ch unchanged")
    c4, b4 = res["C4"], before["C4"]
    st = c4["specutils_txt as .txt"]
    tk = c4["tka as .xyz"]
    a1 = c4["ascii1 starting with zeros as .xyz"]
    ok = (isinstance(st["read"], list) and st["read"][0] == "specutils_txt" and st["read"][3:] == [100.0, 110.0]
          and st["read"][2] == 15345.0)
    ok = ok and tk["how"] == "ambiguous" and set(tk["candidates"]) == {"tka", "ascii1"}
    ok = ok and a1 == b4["ascii1 starting with zeros as .xyz"]
    ra = {r["file"]: r for r in c4["any_extension"]["rows"]}
    rb = {r["file"]: r for r in b4["any_extension"]["rows"]}
    changed = []
    for f, r in rb.items():
        a = ra.get(f, {})
        for k in ("own", "own_sig", "probe.xyz", "probe.xyz_sig", "probe", "probe_sig"):
            if a.get(k) != r.get(k) and (f, k.replace("_sig", "")) not in EXPECTED_DETECTION_CHANGES:
                changed.append((f, k, r.get(k) if k.endswith(("own", "xyz", "probe")) else "...",
                                a.get(k) if k.endswith(("own", "xyz", "probe")) else "..."))
    neg_b = [x for x in b4["any_extension"]["negatives"] if x["detected"]]
    neg_a = [x for x in c4["any_extension"]["negatives"] if x["detected"]]
    ok = ok and not changed and len(neg_a) <= len(neg_b)
    c["RC.C4"] = (ok, f"SpecUtils TXT as .txt: {st['read']} (before {b4['specutils_txt as .txt']['read']}); TKA as "
                      f".xyz: {tk['how']} {tk['candidates']} (before {b4['tka as .xyz']['how']} "
                      f"{b4['tka as .xyz']['candidates']}); one-column file starting with zeros {a1['detected']}; "
                      f"other detection changes {changed or 'none'}; negative files detected {len(neg_b)} -> {len(neg_a)}")
    return {k: {"pass": bool(v[0]), "detail": v[1]} for k, v in c.items()}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--collect", default=None, help="write the raw observations to this file and stop")
    a = ap.parse_args(argv)
    res = collect()
    if a.collect:
        Path(a.collect).write_text(json.dumps(res, indent=1, default=str), encoding="utf-8", newline="\n")
        return 0
    before = json.loads(BEFORE_JSON.read_text(encoding="utf-8"))
    res["criteria"] = criteria(res, before)
    n_pass = sum(v["pass"] for v in res["criteria"].values())
    res["summary"] = {"pass": n_pass, "fail": len(res["criteria"]) - n_pass}
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "round4_formats.json").write_text(json.dumps(res, indent=1, default=str), encoding="utf-8", newline="\n")
    lines = ["# Round-4 format findings (after_R4C)", "",
             "Protocol: `docs/baseline/round4_formats_protocol.md`. Synthetic files, the test corpus and the "
             "EML/Sanderson reference spectra (names, sums and flags only).", "",
             f"**{n_pass} PASS / {res['summary']['fail']} FAIL** (RC.C1-C4; RC.C5 is the test suite and the "
             "benchmark, reported in the protocol)", "", "| ID | result | detail |", "|---|---|---|"]
    lines += [f"| {k} | {'PASS' if v['pass'] else 'FAIL'} | {v['detail']} |" for k, v in res["criteria"].items()]
    (OUT / "round4_formats.md").write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps(res["summary"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
