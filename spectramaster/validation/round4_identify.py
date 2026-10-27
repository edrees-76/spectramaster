"""Round-4 review, identification findings (docs/baseline/round4_identify_protocol.md).

    python -m spectramaster.validation.round4_identify [--data DIR] [--skip-crm]

Synthetic spectra, plus the public CRM spectra of Zenodo 23093533 (crm_zenodo.DEFAULT_DATA) when
present: only counts of identifications are written.  Writes ``round4_identify.json`` and
``round4_identify.md`` to docs/baseline/after_R4B.
"""
from __future__ import annotations

import argparse
import importlib
import inspect
import json
import math
import sys
from datetime import datetime, timedelta
from pathlib import Path

import numpy as np

from spectramaster.analysis import find_peaks
from spectramaster.analysis.library import application_library, load_library
from spectramaster.model import Spectrum
from spectramaster.validation import synthetic as syn

idm = importlib.import_module("spectramaster.analysis.identify")   # the package rebinds the name

OUT = Path(__file__).resolve().parents[2] / "docs" / "baseline" / "after_R4B"
START = datetime(2024, 3, 1, 10, 0, 0)
DAY = 86400.0
HALF_LIVES_LIMIT = 10.0                  # the protocol's rule: more than 10 half-lives since sampling
CRM_AGE_DAYS = 30.0                      # lower bound of the age of every CRM material at its measurement
MEDICAL = ("Mo-99", "Tc-99m", "F-18", "Ga-67", "Ga-68", "In-111", "Tl-201", "Lu-177", "I-123", "I-125")
SEED = 4242

# engine 1.15.0 (1aa179d), before the change: the protocol's reference values
BEFORE: dict = {}


def _identify(spectrum, peaks, sampled=None, application="all"):
    kw = {"application": application}
    if sampled is not None:
        if "sampled" not in inspect.signature(idm.identify).parameters:
            return None                     # engine without the rule
        kw["sampled"] = sampled
    return idm.identify(spectrum, peaks, **kw)


# ------------------------------------------------------------------ C1: first_channel
def _codex_fwhm() -> float:
    s = Spectrum(counts=[10.0] * 3000, live_time=100.0, energy_coeffs=[0.0, 0.5], fwhm_coeffs=[1.0, 0.001],
                 first_channel=1000)
    ctx = idm._Context(s, [], "HPGe")
    return float(ctx._fwhm_kev(1000.0))


def _fwhm_coeffs(det) -> list:
    ch = np.arange(det.n_channels, dtype=float)
    return [float(c) for c in np.polynomial.polynomial.polyfit(ch, det.fwhm_kev(det.energy(ch)), 2)]


def _crop_case() -> dict:
    det = syn.HPGE
    lines = [(122.06, 6000), (344.28, 9000), (661.66, 20000), (778.9, 4000), (964.1, 3500), (1112.1, 3000),
             (1173.23, 8000), (1332.49, 7000), (1408.0, 5000), (1460.82, 3000)]
    cont = syn.Continuum(exp_amp=300.0, exp_scale_kev=300.0, flat=8.0)
    full = syn.make_spectrum(det, [syn.TruePeak(e, a) for e, a in lines], cont, SEED).spectrum
    full.fwhm_coeffs = _fwhm_coeffs(det)
    full.start_time = START
    cut = 150
    crop = Spectrum(counts=list(full.counts[cut:]), live_time=full.live_time, real_time=full.real_time,
                    energy_coeffs=list(full.energy_coeffs), fwhm_coeffs=list(full.fwhm_coeffs), first_channel=cut,
                    start_time=START, sample_id="crop")
    pk = [p for p in find_peaks(full) if p.energy is not None and p.energy > full.energy_of(cut + 20)]
    grid = [150.0, 300.0, 662.0, 1000.0, 1332.0, 1800.0]
    fw = []
    for s in (full, crop):
        ctx = idm._Context(s, pk, "HPGe")
        fw.append([float(ctx._fwhm_kev(e)) for e in grid])
    truth = [float(det.fwhm_kev(e)) for e in grid]
    res = []
    for s in (full, crop):
        import copy
        r = idm.identify(s, copy.deepcopy(pk), correct_drift=False)
        res.append({m.nuclide: m.confidence for m in r})
    return {"grid_kev": grid, "fwhm_full": fw[0], "fwhm_crop": fw[1], "fwhm_true": truth,
            "ident_full": res[0], "ident_crop": res[1]}


# ------------------------------------------------------------------ C2/C3/C5: synthetic sampling cases
def _lines(nuc, area_strongest, emin=60.0):
    nd = load_library(None)[nuc]
    g = [ln for ln in nd.lines if ln.kind == "g" and ln.energy > emin and ln.intensity >= 1.0]
    top = max(ln.intensity for ln in g)
    return [(ln.energy, area_strongest * ln.intensity / top * float(syn.HPGE.fwhm_kev(0) > 0)) for ln in g]


def _eff(e):
    return float(idm.efficiency_shape(e, "HPGe"))


def _sampling_spectrum(mn56_area=6000.0, with_mo=True, seed=SEED, mn56_only_846=False) -> Spectrum:
    det = syn.HPGE
    peaks = []
    for nuc, a in (("Cs-137", 40000.0), ("K-40", 6000.0)):
        peaks += [syn.TruePeak(e, ar * _eff(e) / _eff(661.66 if nuc == "Cs-137" else 1460.8)) for e, ar in _lines(nuc, a)]
    for e, ar in _lines("Mn-56", mn56_area):
        if mn56_only_846 and abs(e - 846.77) > 1:
            continue
        peaks.append(syn.TruePeak(e, ar * _eff(e) / _eff(846.77)))
    if with_mo:
        for nuc, a in (("Mo-99", 8000.0), ("Tc-99m", 30000.0)):
            ref = 739.5 if nuc == "Mo-99" else 140.51
            peaks += [syn.TruePeak(e, ar * _eff(e) / _eff(ref)) for e, ar in _lines(nuc, a)]
    cont = syn.Continuum(exp_amp=400.0, exp_scale_kev=300.0, flat=10.0)
    s = syn.make_spectrum(det, [p for p in peaks if 30 < p.energy < 2040], cont, seed).spectrum
    s.start_time = START
    return s


def _sampling_cases() -> dict:
    s = _sampling_spectrum()
    pk = find_peaks(s)
    import copy
    out = {}
    for label, dt in (("none", None), ("1h", 3600.0), ("3d", 3 * DAY), ("30d", 30 * DAY)):
        r = _identify(s, copy.deepcopy(pk), None if dt is None else START - timedelta(seconds=dt))
        out[label] = None if r is None else {m.nuclide: {"conf": m.confidence, "note": m.note} for m in r}
    try:
        _identify(s, copy.deepcopy(pk), START + timedelta(days=1))
        out["after_start"] = "accepted"
    except ValueError as exc:
        out["after_start"] = f"ValueError: {exc}"
    # single weak line: only the 847 keV line of Mn-56, 150 counts (the others would be below L_D)
    w = _sampling_spectrum(mn56_area=150.0, with_mo=False, seed=SEED + 1, mn56_only_846=True)
    rw = idm.identify(w, find_peaks(w))
    out["weak"] = {m.nuclide: {"conf": m.confidence, "note": m.note, "n_matched": len(m.matched)} for m in rw}
    return out


# ------------------------------------------------------------------ C4: prior of the medical nuclides
def _priors() -> dict:
    lib = load_library(None)
    s = Spectrum(counts=[10.0] * 4096, live_time=100.0, energy_coeffs=[0.0, 0.5], start_time=START)
    out = {}
    for app in ("all", "environmental", "medical"):
        libd = application_library(lib, app)
        ctx = idm._Context(s, [], "HPGe")
        ctx.application = app
        row = {}
        for n in MEDICAL + ("I-131", "Cs-137"):
            if n in libd:
                nd = libd[n]
                lines = [idm._ELine(ln.energy, 1.0, 50.0, "g", [ln]) for ln in nd.lines[:3]]
                row[n] = idm._prior(nd, ctx, {i: None for i in range(len(lines))}, lines)
        out[app] = row
    return out


# ------------------------------------------------------------------ C6/C7: CRM spectra
def _crm(data: Path) -> dict:
    from spectramaster.validation.crm_zenodo import Dataset
    lib = load_library(None)
    ds = Dataset(data)

    def short(n):
        nd = lib[n]
        return (not nd.series and nd.half_life_s is not None
                and CRM_AGE_DAYS * DAY / nd.half_life_s > HALF_LIVES_LIMIT)

    def kept(n):
        nd = lib[n]
        return bool(nd.series) or (nd.half_life_s or 0) >= 30 * DAY

    tot = {"spectra": 0, "short_none": 0, "short_aged": 0, "medical_none": 0, "kept_none": 0, "kept_aged": 0,
           "lost_kept_aged": 0, "single_note": 0}
    by = {}
    names0, names1 = {}, {}
    for m in ds.meta:
        s = ds.spectrum(m["ID"])
        pk = find_peaks(s)
        import copy
        r0 = {x.nuclide: x for x in idm.identify(s, copy.deepcopy(pk))}
        r1 = _identify(s, copy.deepcopy(pk), s.start_time - timedelta(days=CRM_AGE_DAYS))
        r1 = None if r1 is None else {x.nuclide: x for x in r1}
        tot["spectra"] += 1
        names0[m["ID"]] = sorted(r0)
        if r1 is not None:
            names1[m["ID"]] = sorted(r1)
        tot["short_none"] += sum(short(n) for n in r0)
        tot["medical_none"] += sum(n in MEDICAL for n in r0)
        tot["kept_none"] += sum(kept(n) for n in r0)
        tot["single_note"] += sum("one line matched" in (x.note or "") for x in r0.values())
        for n in r0:
            if short(n):
                by[n] = by.get(n, 0) + 1
        if r1 is not None:
            tot["short_aged"] += sum(short(n) for n in r1)
            tot["kept_aged"] += sum(kept(n) for n in r1)
            tot["lost_kept_aged"] += sum(1 for n in r0 if kept(n) and n not in r1)
        else:
            tot["short_aged"] = tot["kept_aged"] = tot["lost_kept_aged"] = None
    tot["short_by_nuclide"] = dict(sorted(by.items(), key=lambda kv: -kv[1]))
    tot["names_no_date"] = names0
    tot["names_aged"] = names1 or None
    return tot


def run(data=None, skip_crm=False) -> dict:
    from spectramaster.lab.session import ENGINE_VERSION
    res: dict = {"engine": ENGINE_VERSION}
    res["C1"] = {"codex_fwhm_kev": _codex_fwhm(), "crop": _crop_case()}
    res["C2"] = _sampling_cases()
    res["C4"] = _priors()
    if not skip_crm:
        from spectramaster.validation.crm_zenodo import DEFAULT_DATA
        path = Path(data) if data else DEFAULT_DATA
        res["C6"] = _crm(path) if path.exists() else None
    return res


BEFORE_JSON = OUT / "round4_identify_before.json"
SHORT_LIMIT, LOST_LIMIT = 0.20, 0.01
NOTE_DECAYED, NOTE_SINGLE = "half-lives since sampling", "one line matched"


def _same(a, b) -> bool:
    return a is not None and b is not None and a == b


def _penalised(row, base) -> bool:
    """Not reported, or at most half the confidence without a date and with the half-life note."""
    return row is None or (row["conf"] <= 0.5 * base["conf"] and NOTE_DECAYED in row["note"])


def _lost(before: dict, after: dict, keep) -> int:
    return sum(1 for sid, names in before.items() for n in names if keep(n) and n not in after.get(sid, []))


def criteria(res: dict, before: dict) -> dict:
    c = {}
    c1 = res["C1"]
    cr = c1["crop"]
    ok = abs(c1["codex_fwhm_kev"] - 3.0) <= 3e-9 and all(
        abs(a - b) <= 1e-9 * abs(b) for a, b in zip(cr["fwhm_crop"], cr["fwhm_full"]))
    c["RB.C1"] = (ok, f"Codex's case {c1['codex_fwhm_kev']:.6f} keV (before {before['C1']['codex_fwhm_kev']:.6f}); "
                      "FWHM cropped / full " + ", ".join(f"{a:.6f}/{b:.6f}" for a, b in
                                                         zip(cr["fwhm_crop"], cr["fwhm_full"]))
                  + f"; identification full {cr['ident_full']}, cropped {cr['ident_crop']}")
    c2, none = res["C2"], res["C2"]["none"]
    ok = _same(c2["1h"], none)
    d3 = c2["3d"] or {}
    ok = ok and all(_same(d3.get(n), none.get(n)) for n in ("Cs-137", "K-40", "Mo-99", "Tc-99m"))
    ok = ok and _penalised(d3.get("Mn-56"), none["Mn-56"])
    d30 = c2["30d"] or {}
    ok = ok and all(_penalised(d30.get(n), none[n]) for n in ("Mn-56", "Mo-99", "Tc-99m"))
    ok = ok and all(d30.get(n) is not None and d30[n]["conf"] >= 0.9 for n in ("Cs-137", "K-40"))
    ok = ok and str(c2["after_start"]).startswith("ValueError")
    show = {k: {n: v["conf"] for n, v in (c2[k] or {}).items()} for k in ("none", "1h", "3d", "30d")}
    c["RB.C2"] = (ok, f"confidences {show}; date after start: {c2['after_start']}")
    w = c2["weak"]
    ok = all(NOTE_SINGLE in w.get(n, {}).get("note", "") for n in ("Co-56", "Ba-133"))
    ok = ok and all(n in w and NOTE_SINGLE not in w[n]["note"] for n in ("Cs-137", "K-40"))
    ok = ok and NOTE_SINGLE not in none["Mo-99"]["note"]
    bw = before["C2"]["weak"]
    ok = ok and {n: v["conf"] for n, v in w.items()} == {n: v["conf"] for n, v in bw.items()}
    c["RB.C3"] = (ok, "; ".join(f"{n} {v['conf']} ({v['n_matched']} line(s))"
                                f"{' [note]' if NOTE_SINGLE in v['note'] else ''}" for n, v in w.items()))
    ok = True
    for app, row in res["C4"].items():
        for n, v in row.items():
            b = before["C4"][app][n]
            want = 0.8 * b if (n in MEDICAL and app != "medical") else b
            ok = ok and abs(v - want) <= 1e-12
    c["RB.C4"] = (ok, "; ".join(f"{app}: " + ", ".join(f"{n} {v:.2f}" for n, v in row.items())
                                for app, row in res["C4"].items()))
    c6, b6 = res.get("C6"), before.get("C6")
    if c6 and b6:
        lib = load_library(None)

        def keep(n):
            nd = lib.get(n)
            return nd is not None and (bool(nd.series) or (nd.half_life_s or 0) >= 30 * DAY)
        lost_aged = _lost(c6["names_no_date"], c6["names_aged"] or {}, keep)
        ok = (c6["short_aged"] is not None and c6["short_aged"] <= SHORT_LIMIT * b6["short_none"]
              and lost_aged <= LOST_LIMIT * b6["kept_none"])
        c["RB.C5"] = (ok, f"short-lived identifications {b6['short_none']} -> {c6['short_aged']} with the date "
                          f"(limit {SHORT_LIMIT * b6['short_none']:.1f}); long-lived / series lost {lost_aged} "
                          f"of {c6['kept_none']} (limit {LOST_LIMIT * b6['kept_none']:.1f})")
        lost = _lost(b6["names_no_date"], c6["names_no_date"], keep)
        ok = c6["medical_none"] <= b6["medical_none"] and lost <= LOST_LIMIT * b6["kept_none"]
        c["RB.C6"] = (ok, f"medical identifications {b6['medical_none']} -> {c6['medical_none']}; long-lived / "
                          f"series lost {lost} of {b6['kept_none']}; short-lived without date "
                          f"{b6['short_none']} -> {c6['short_none']}; single-line notes {c6['single_note']}")
    return {k: {"pass": bool(v[0]), "detail": v[1]} for k, v in c.items()}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default=None)
    ap.add_argument("--skip-crm", action="store_true")
    ap.add_argument("--out", default=str(OUT))
    a = ap.parse_args(argv)
    res = run(a.data, a.skip_crm)
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    if BEFORE_JSON.exists():
        res["criteria"] = criteria(res, json.loads(BEFORE_JSON.read_text(encoding="utf-8")))
        n_pass = sum(v["pass"] for v in res["criteria"].values())
        res["summary"] = {"pass": n_pass, "fail": len(res["criteria"]) - n_pass}
        lines = ["# Round-4 identification findings (after_R4B)", "",
                 "Protocol: `docs/baseline/round4_identify_protocol.md`. Synthetic spectra and the public CRM "
                 "spectra of Zenodo 23093533 (counts and nuclide names only).", "",
                 f"**{n_pass} PASS / {res['summary']['fail']} FAIL** (RB.C1-C6; RB.C7 is the test suite and "
                 "the benchmark, reported in the protocol)", "", "| ID | result | detail |", "|---|---|---|"]
        lines += [f"| {k} | {'PASS' if v['pass'] else 'FAIL'} | {v['detail']} |" for k, v in res["criteria"].items()]
        (out / "round4_identify.md").write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
        print(json.dumps(res["summary"]))
    (out / "round4_identify.json").write_text(json.dumps(res, indent=1, default=str), encoding="utf-8", newline="\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
