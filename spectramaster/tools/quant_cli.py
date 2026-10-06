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


def cmd_activity(args) -> int:
    try:
        spec = _read(args.file)
        curve = eff.load_curve(args.eff)
        bkg = _read(args.bkg) if args.bkg else None
        nucl = [n.strip() for n in args.nuclides.split(",")] if args.nuclides else list(act.DEFAULT_NUCLIDES)
        opt = act.ActivityOptions(
            nuclides=nucl, method=args.method, ref_date=eff.parse_date(args.ref_date) if args.ref_date else None,
            quantity=args.mass, quantity_unit=args.unit, quantity_rel_unc=(args.mass_unc or 0.0) / 100.0,
            attenuation=args.attenuation, bkg_mode=args.bkg_mode, mda_method=args.mda)
        res = act.compute_activities(spec, curve, opt, background=bkg)
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


def add_quant_commands(sub) -> None:
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
    p.add_argument("--mass", type=float, help="sample quantity")
    p.add_argument("--unit", default="kg", help="kg, g, L, mL (default kg)")
    p.add_argument("--mass-unc", type=float, default=0.0, help="quantity uncertainty %%")
    p.add_argument("--ref-date", help="reference (sampling) date, default acquisition start")
    p.add_argument("--nuclides", help="comma separated, default " + ",".join(act.DEFAULT_NUCLIDES))
    p.add_argument("--method", choices=["key", "mean"], default="key", help="key line or weighted mean")
    p.add_argument("--mda", choices=["currie", "iso11929"], default="currie")
    p.add_argument("--attenuation", type=float, default=1.0, help="self-attenuation correction factor")
    p.add_argument("-o", "--out", help="write results .csv or .xlsx")
    p.set_defaults(func=cmd_activity)
