"""CLI commands ``effcal`` (efficiency calibration) and ``activity`` (activity / MDA)."""
from __future__ import annotations

import sys
from pathlib import Path

from ..analysis import activity as act
from ..analysis import efficiency as eff
from ..formats.base import FormatError


def _err(msg: str) -> None:
    print(f"error: {msg}", file=sys.stderr)


def _read(path: str):
    from ..convert import read_spectra
    spectra, _fmt = read_spectra(Path(path))
    if not spectra:
        raise ValueError(f"{path}: no spectrum")
    s = spectra[0]
    if not s.source_path:
        s.source_path = str(path)
    return s


def cmd_effcal(args) -> int:
    try:
        spec = _read(args.file)
        records = eff.aptec_source_records(args.file) if Path(args.file).suffix.lower() == ".s0" else []
        if args.cert:
            cert = eff.certificate_lines(eff.read_certificate_csv(args.cert), args.min_intensity)
            src = f"certificate {Path(args.cert).name}"
        elif records:
            cert = eff.certificate_from_aptec(records)
            src = "Aptec source records stored in the file"
        else:
            _err("no --cert given and the file holds no Aptec source records")
            return 2
        bkg = _read(args.bkg) if args.bkg else None
        pts = eff.measure_efficiency(spec, cert, background=bkg)
        crossover = args.crossover if args.crossover is not None else "auto"
        curve = eff.fit_efficiency(pts, args.model, order=args.order, crossover=crossover,
                                   order_high=args.order_high, u_sys_rel=args.u_sys,
                                   geometry=args.geometry or spec.extra.get("geometry_id", ""),
                                   detector=args.detector or spec.detector, source=str(args.file),
                                   name=args.name or Path(args.out).stem,
                                   date=spec.start_time.strftime("%Y-%m-%d %H:%M") if spec.start_time else "")
    except (ValueError, KeyError, OSError, FormatError) as exc:
        _err(str(exc))
        return 1
    print(f"standard: {args.file}  ({src}, {len(cert)} lines, {len(pts)} measured points)")
    print(f"model: {curve.describe()}   chi2/dof = {curve.reduced_chi2:.2f}   u_sys = {100 * curve.u_sys_rel:.2f} %")
    print(f"{'nuclide':8s} {'keV':>8s} {'net':>10s} {'eps':>10s} {'u %':>6s} {'fit':>10s} {'resid %':>8s}  note")
    for p, r, _z in curve.residuals():
        print(f"{p.nuclide:8s} {p.energy:8.2f} {p.net_area or 0:10.0f} {p.efficiency:10.5g} {100 * p.rel_unc:6.2f} "
              f"{curve.efficiency(p.energy):10.5g} {r:8.2f}  {'' if p.use else '[not used] '}{p.note}")
    if records and args.compare:
        print("\ncomparison with Aptec's stored efficiencies:")
        for c in eff.compare_with_aptec(pts, records):
            ours = "-" if c["ours"] is None else f"{c['ours']:.5g}"
            d = "-" if c["diff_pct"] is None else f"{c['diff_pct']:+.2f} %"
            print(f"  {c['nuclide']:8s} {c['energy']:8.2f}  Aptec {c['aptec']:.5g}  ours {ours}  {d}")
    curve.save(args.out)
    print(f"saved {args.out}")
    return 0


def _reference_peak(args) -> "dict | None":
    """--ref-peak with --ref-rate (pulser / known rate) or --ref-spectrum (measured once)."""
    if args.ref_peak is None:
        return None
    ref = {"energy": args.ref_peak, "rate_rel_unc": (args.ref_rate_unc or 0.0) / 100.0,
           "half_life_s": args.ref_half_life}
    if args.ref_spectrum:
        rs = _read(args.ref_spectrum)
        rate, u = act.reference_rate(rs, args.ref_peak)
        ref.update(rate=rate, rate_rel_unc=u / rate, ref_date=rs.start_time)
    elif args.ref_rate:
        ref["rate"] = args.ref_rate
    else:
        raise ValueError("--ref-peak needs --ref-rate or --ref-spectrum")
    return ref


def _tcs(args) -> "dict | None":
    """--tcs-pt A,B: true-coincidence summing correction with PT(E) = min(1, A (E/1000 keV)^B)."""
    if not args.tcs_pt:
        return None
    a, b = (float(v) for v in args.tcs_pt.split(","))
    out = {"peak_to_total": [a, b], "pt_rel_unc": (args.tcs_pt_unc or 0.0) / 100.0}
    if getattr(args, "tcs_curve_summing_free", False):
        out["curve_summing_free"] = True
    return out


def _self_attenuation(args):
    """--self-att-density with --cal-density and --self-att-height-mm: energy-dependent correction
    (analysis.attenuation.SelfAttenuation); None without --self-att-density."""
    if getattr(args, "self_att_density", None) is None:
        return None
    if args.cal_density is None or args.self_att_height_mm is None:
        raise ValueError("--self-att-density needs --cal-density and --self-att-height-mm")
    from ..analysis.attenuation import SelfAttenuation
    return SelfAttenuation(args.self_att_matrix, args.self_att_density, args.cal_matrix or args.self_att_matrix,
                           args.cal_density, args.self_att_height_mm, (args.self_att_unc or 0.0) / 100.0)


def cmd_activity(args) -> int:
    try:
        spec = _read(args.file)
        curve = eff.load_curve(args.eff)
        bkg = _read(args.bkg) if args.bkg else None
        nucl = [n.strip() for n in args.nuclides.split(",")] if args.nuclides else list(act.DEFAULT_NUCLIDES)
        opt = act.ActivityOptions(
            nuclides=nucl, method=args.method, ref_date=eff.parse_date(args.ref_date) if args.ref_date else None,
            quantity=args.mass, quantity_unit=args.unit, quantity_rel_unc=(args.mass_unc or 0.0) / 100.0,
            attenuation=args.attenuation, bkg_mode=args.bkg_mode, mda_method=args.mda,
            decision=args.decision, reference_peak=_reference_peak(args), tcs=_tcs(args),
            self_attenuation=_self_attenuation(args))
        blank = None
        if args.blank:      # the reagent blank, analysed exactly like the sample
            blank = act.compute_activities(_read(args.blank), curve, opt, background=bkg)
        res = act.compute_activities(spec, curve, opt, background=bkg, blank=blank)
    except (ValueError, KeyError, OSError, FormatError) as exc:
        _err(str(exc))
        return 1
    print(f"sample: {spec.sample_id or Path(args.file).name}   live {spec.live_time:g} s   "
          f"reference date: {res.ref_date or '-'}   efficiency: {curve.name} ({curve.describe()})")
    print(act.format_table(res))
    for r in res.nuclides:
        if r.note:
            print(f"  {r.nuclide}: {r.note}")
    for n in res.notes:
        print(f"  note: {n}")
    if args.out:
        act.export_results(args.out, res)
        print(f"saved {args.out}")
    return 0


def cmd_batch(args) -> int:
    """Group the spectra; analyse only the chosen group with the given calibration."""
    import glob
    import json
    from ..lab.batch import BatchSetup, group_items, run_batch, scan, write_csv
    from ..lab.detector import MeasurementGeometry
    paths = []
    for pat in args.paths:
        hits = sorted(glob.glob(pat, recursive=True)) or [pat]
        for h in hits:
            hp = Path(h)
            paths.extend(sorted(q for q in hp.rglob("*") if q.is_file()) if hp.is_dir() else [hp])
    items = scan(paths)
    groups = group_items(items, energy_tol_kev=args.energy_tol)
    for g in groups:
        print(g.describe())
    bad = [it for it in items if it.error]
    if bad:
        print(f"{len(bad)} file(s) not read (first: {bad[0].path}: {bad[0].error})")
    if args.group is None:
        print("choose a group with --group N and its efficiency calibration with --eff (nothing analysed)")
        return 0
    if not any(g.id == args.group for g in groups):
        _err(f"no group {args.group}")
        return 1
    try:
        curve = eff.load_curve(args.eff) if args.eff else None
        geom = (MeasurementGeometry.from_dict(json.loads(Path(args.geometry).read_text(encoding="utf-8")))
                if args.geometry else None)
    except (OSError, ValueError, KeyError) as exc:
        _err(str(exc))
        return 1
    setup = BatchSetup(curve=curve, geometry=geom, allow_geometry_mismatch=args.allow_geometry_mismatch,
                       application=args.application,
                       nuclides=[n.strip() for n in (args.nuclides or "").split(",") if n.strip()])
    sel = [g for g in groups if g.id == args.group]
    rows = run_batch(sel, {args.group: setup},
                     progress=lambda i, n: print(chr(13) + "%d/%d" % (i, n), end="", file=sys.stderr))
    print(file=sys.stderr)
    write_csv(args.out, rows)
    print(f"{len(rows)} row(s) written to {args.out}")
    return 0


def add_quant_commands(sub) -> None:
    b = sub.add_parser("batch", help="group spectra by detector/channels/calibration; analyse one group")
    b.add_argument("paths", nargs="+", help="files, folders or glob patterns")
    b.add_argument("--group", type=int, help="group to analyse (see the list printed first)")
    b.add_argument("--eff", help="efficiency curve JSON for this group (omit: identification only)")
    b.add_argument("--geometry", help="sample geometry JSON (lab.detector.MeasurementGeometry)")
    b.add_argument("--allow-geometry-mismatch", action="store_true",
                   help="use a calibration of another geometry anyway (reported in every row)")
    b.add_argument("--application", default="environmental",
                   help="identification library: all, environmental, calibration, safeguards, medical")
    b.add_argument("--nuclides", help="comma-separated nuclides for activities (default: those identified)")
    b.add_argument("--energy-tol", type=float, default=1.0, help="calibration agreement for grouping, keV")
    b.add_argument("-o", "--out", default="batch_results.csv")
    b.set_defaults(func=cmd_batch)

    p = sub.add_parser("effcal", help="efficiency calibration from a certified standard spectrum")
    p.add_argument("file", help="calibration (standard) spectrum")
    p.add_argument("--cert", help="certificate CSV: nuclide,activity_bq,unc_percent,ref_date[,half_life_s,"
                                  "energy_kev,intensity_percent]  (default: Aptec records in an .S0 file)")
    p.add_argument("-o", "--out", required=True, help="efficiency curve JSON")
    p.add_argument("--model", choices=["loglog", "two_branch"], default="two_branch")
    p.add_argument("--order", type=int, default=3, help="log-log order, or low-branch order (default 3)")
    p.add_argument("--order-high", type=int, default=2, help="high-branch order (two_branch)")
    p.add_argument("--crossover", type=float, help="crossover keV (two_branch; default: automatic)")
    p.add_argument("--u-sys", type=float, default=None, help="correlated relative uncertainty (fraction)")
    p.add_argument("--bkg", help="background spectrum (peak-by-peak subtraction)")
    p.add_argument("--min-intensity", type=float, default=2.0, help="library lines >= this %% (default 2)")
    p.add_argument("--geometry", default="")
    p.add_argument("--detector", default="")
    p.add_argument("--name", default="")
    p.add_argument("--compare", action="store_true", help="compare with Aptec's stored efficiencies")
    p.set_defaults(func=cmd_effcal)

    p = sub.add_parser("activity", help="activity, specific activity and MDA of a sample spectrum")
    p.add_argument("file")
    p.add_argument("--eff", required=True, help="efficiency curve JSON (from 'effcal')")
    p.add_argument("--bkg", help="background spectrum")
    p.add_argument("--bkg-mode", choices=["peak", "spectrum"], default="peak")
    p.add_argument("--ref-peak", type=float, help="reference peak correction: energy keV of a pulser "
                                                   "or fixed reference source peak")
    p.add_argument("--ref-rate", type=float, help="its expected rate, counts per live second")
    p.add_argument("--ref-rate-unc", type=float, default=0.0, help="its relative uncertainty %%")
    p.add_argument("--ref-spectrum", help="reference (low-rate) measurement giving the expected rate")
    p.add_argument("--ref-half-life", type=float, help="half-life (s) of a reference source (decay correction)")
    p.add_argument("--tcs-pt", metavar="A,B",
                   help="true-coincidence summing correction with the peak-to-total ratio "
                        "PT(E) = min(1, A (E/1000 keV)^B) of this detector and geometry (an assumption)")
    p.add_argument("--tcs-pt-unc", type=float, default=10.0, help="relative uncertainty of PT, %% (default 10)")
    p.add_argument("--tcs-curve-summing-free", action="store_true",
                   help="declare the efficiency curve free of true-coincidence summing (needed for a curve "
                        "without calibration points; not checked)")
    p.add_argument("--blank", help="reagent blank spectrum (prepared and counted like the samples); "
                                   "its activities are subtracted line by line")
    p.add_argument("--mass", type=float, help="sample quantity")
    p.add_argument("--unit", default="kg", help="kg, g, L, mL (default kg)")
    p.add_argument("--mass-unc", type=float, default=0.0, help="quantity uncertainty %%")
    p.add_argument("--ref-date", help="reference (sampling) date, default acquisition start")
    p.add_argument("--nuclides", help="comma separated, default " + ",".join(act.DEFAULT_NUCLIDES))
    p.add_argument("--method", choices=["key", "mean"], default="key", help="key line or weighted mean")
    p.add_argument("--mda", choices=["currie", "iso11929"], default="currie")
    p.add_argument("--decision", choices=["search", "iso11929"], default="search",
                   help="detected: a search peak above the decision threshold (default), or also a window "
                        "result above it (ISO 11929, about 5 %% false detections per line)")
    p.add_argument("--attenuation", type=float, default=1.0, help="self-attenuation correction factor")
    from ..analysis.attenuation import MATRICES
    p.add_argument("--self-att-density", type=float,
                   help="sample density g/cm3: energy-dependent correction to the calibration density (slab model)")
    p.add_argument("--self-att-matrix", choices=MATRICES, default="water", help="sample matrix (default water)")
    p.add_argument("--cal-density", type=float, help="density of the calibration source g/cm3")
    p.add_argument("--cal-matrix", choices=MATRICES, help="calibration matrix (default: the sample's)")
    p.add_argument("--self-att-height-mm", type=float, help="fill height of sample and calibration source, mm")
    p.add_argument("--self-att-unc", type=float, default=0.0, help="model uncertainty of the factor, %%")
    p.add_argument("-o", "--out", help="write results .csv or .xlsx")
    p.set_defaults(func=cmd_activity)
