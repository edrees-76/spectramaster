"""CLI subcommands for the expert tools (registered by spectramaster.cli).

    index     ROOT -o catalog.xlsx [--no-recursive] [--all-files]
    rescue    ROOT -o OUTDIR --to n42_2012 --to ci_cnf [--resume] [--flat] [--no-verify]
              [--skip-duplicates] [--limit N]
    sum       FILES... -o OUT [--to FMT] [--align auto|channel|energy]
    subtract  SAMPLE BACKGROUND -o OUT [--to FMT] [--scale K] [--clip] [--sigma-csv FILE]
    rebin     FILE -o OUT [--factor N] [--start CH] [--stop CH] [--to FMT]
    calibrate FILES... (--pairs ch:keV,... | --source Eu-152 | --coeffs c0,c1,..)
              [--order N] [--fwhm ch:keV,...] [-o OUTDIR] [--to FMT] [--only-uncalibrated]
"""
from __future__ import annotations

import csv
import sys
import time
from pathlib import Path

from ..formats import FormatSpec, get_format, load_all, writable_formats


def _err(msg: str) -> None:
    print(msg, file=sys.stderr)


def _out_format(to, out_path: Path, fallback=None) -> FormatSpec:
    load_all()
    if to:
        f = get_format(to)
    else:
        ext = Path(out_path).suffix.lower()
        cands = [f for f in writable_formats() if ext in f.extensions]
        if not cands:
            if fallback is not None:
                return fallback
            raise SystemExit(f"error: cannot infer the output format from {out_path.name!r}; use --to")
        f = cands[0]
    if not f.can_write:
        raise SystemExit(f"error: {f.name} cannot be written")
    return f


def _read_one(path: str):
    from ..convert import read_spectra
    spectra, fmt = read_spectra(Path(path))
    if len(spectra) > 1:
        _err(f"note: {path} holds {len(spectra)} spectra; using the first")
    return spectra[0], fmt


def _write(spec, out: Path, fmt: FormatSpec) -> None:
    from ..convert import write_spectrum
    for w in write_spectrum(spec, out, fmt):
        print(f"  warning: {w}")
    print(f"wrote {out}")


def _progress_printer(label: str, every: int = 100):
    t0 = time.perf_counter()

    def cb(i, n, path):
        if i == n or i % every == 0:
            el = time.perf_counter() - t0
            eta = el / i * (n - i) if i else 0
            print(f"  {label} {i}/{n}  ({el:.0f} s elapsed, ~{eta:.0f} s left)", flush=True)
        return None
    return cb


# ------------------------------------------------------------------ commands
def cmd_index(args) -> int:
    from .archive import index_archive
    root = Path(args.root)
    if not root.is_dir():
        _err(f"error: {root} is not a folder")
        return 1
    res = index_archive(root, Path(args.out), recursive=not args.no_recursive,
                        progress=None if args.quiet else _progress_printer("scanned"),
                        all_files=args.all_files)
    ok = len(res.entries) - len(res.errors)
    print(f"\n{res.files_scanned} candidate file(s) in {res.elapsed:.1f} s: {ok} spectra catalogued, "
          f"{len(res.errors)} error(s), {res.files_skipped} non-spectrum file(s) skipped, "
          f"{res.duplicate_files} redundant identical cop(ies).")
    print(f"catalogue: {res.output}")
    return 0


def cmd_rescue(args) -> int:
    from .archive import rescue_archive
    root = Path(args.root)
    if not root.is_dir():
        _err(f"error: {root} is not a folder")
        return 1
    files = None
    if args.limit:
        from .archive import find_spectrum_files
        files = find_spectrum_files(root, not args.no_recursive)[: args.limit]
    res = rescue_archive(root, Path(args.out), formats=args.to or ["n42_2012", "ci_cnf"],
                         keep_tree=not args.flat, verify=not args.no_verify, resume=args.resume,
                         recursive=not args.no_recursive, skip_duplicates=args.skip_duplicates,
                         files=files, progress=None if args.quiet else _progress_printer("processed"))
    c = res.counts()
    print(f"\n{res.files_total} file(s) in {res.elapsed:.1f} s: " + ", ".join(f"{v} {k}" for k, v in sorted(c.items())))
    for e in res.entries:
        if e.status in ("FAILED", "ERROR"):
            print(f"  {e.status}  {e.source_rel} [{e.format_key}]: {e.details}")
    print(f"manifest: {res.manifest}\nreport:   {res.report}")
    return 1 if any(e.status in ("FAILED", "ERROR") for e in res.entries) else 0


def fmt_seconds(v) -> str:
    """Times for console output: at most 3 decimals, no float noise (6261.040000000001 -> 6261.04 s)."""
    if v is None:
        return "-"
    return f"{float(v):.3f}".rstrip("0").rstrip(".") + " s"


def cmd_sum(args) -> int:
    from .arithmetic import sum_spectra
    loaded = [_read_one(p) for p in args.files]
    spectra, first_fmt = [x[0] for x in loaded], loaded[0][1]
    out = Path(args.out)
    res = sum_spectra(spectra, align=args.align)
    print(f"sum of {len(spectra)}: total counts {res.total_counts:.6g}, live {fmt_seconds(res.live_time)}, "
          f"real {fmt_seconds(res.real_time)}" + (f"  [{res.extra.get('operation')}]" if res.extra.get("operation") else ""))
    _write(res, out, _out_format(args.to, out, first_fmt if first_fmt.can_write else None))
    return 0


def cmd_subtract(args) -> int:
    from .arithmetic import subtract_background
    s, fmt = _read_one(args.sample)
    b, _ = _read_one(args.background)
    out = Path(args.out)
    net, sigma = subtract_background(s, b, scale=args.scale, clip_negative=args.clip)
    print(f"net = sample - {net.extra['background_scale']:.6g} x background; net counts {net.total_counts:.6g}"
          f" +- {sum(x * x for x in sigma) ** 0.5:.4g}")
    _write(net, out, _out_format(args.to, out, fmt if fmt.can_write else None))
    if args.sigma_csv:
        p = Path(args.sigma_csv)
        p.parent.mkdir(parents=True, exist_ok=True)
        e = net.energies()
        with open(p, "w", newline="", encoding="utf-8") as fh:
            w = csv.writer(fh)
            w.writerow(["channel", "energy_keV", "net_counts", "sigma"])
            for i, (c, u) in enumerate(zip(net.counts, sigma)):
                w.writerow([net.first_channel + i, "" if e is None else f"{e[i]:.4f}", f"{c:.6g}", f"{u:.6g}"])
        print(f"wrote {p}")
    return 0


def cmd_rebin(args) -> int:
    from .arithmetic import rebin, truncate
    s, fmt = _read_one(args.file)
    if args.start is not None or args.stop is not None:
        s = truncate(s, args.start or 0, args.stop, renumber=args.renumber)
    if args.factor > 1:
        s = rebin(s, args.factor)
    out = Path(args.out)
    print(f"{s.num_channels} channels, total counts {s.total_counts:.6g}, calibration "
          + (", ".join(f"{c:.7g}" for c in s.energy_coeffs) or "none"))
    _write(s, out, _out_format(args.to, out, fmt if fmt.can_write else None))
    return 0


def cmd_calibrate(args) -> int:
    from ..convert import read_spectra
    from .calibrate import (apply_calibration_batch, calibrate_from_source, fit_energy_calibration,
                            fit_fwhm_calibration, parse_pairs)
    modes = [m for m in (args.pairs, args.source, args.coeffs) if m]
    if len(modes) != 1:
        _err("error: give exactly one of --pairs, --source, --coeffs")
        return 2
    coeffs = fwhm = None
    if args.pairs:
        pairs = parse_pairs(args.pairs)
        fit = fit_energy_calibration(pairs, args.order or 1)
        print(fit.report())
        coeffs = fit.coeffs
    elif args.coeffs:
        coeffs = [float(x) for x in args.coeffs.replace(";", ",").split(",") if x.strip()]
    if args.fwhm:
        ff = fit_fwhm_calibration(parse_pairs(args.fwhm), args.fwhm_order)
        print(ff.report())
        fwhm = ff.coeffs
    status = 0
    if args.source and not args.out:
        for p in args.files:
            try:
                s = read_spectra(Path(p))[0][0]
                sc = calibrate_from_source(s, args.source, order=args.order)
                print(f"{p}\n{sc.report()}\n")
            except Exception as exc:
                _err(f"{p}: {exc}")
                status = 1
        return status
    if not args.out:
        if coeffs is not None:
            print("(no --out given: calibration not applied)")
        return 0
    res = apply_calibration_batch([Path(p) for p in args.files], Path(args.out), energy_coeffs=coeffs,
                                  fwhm_coeffs=fwhm, source=args.source, order=args.order, out_fmt=args.to,
                                  only_uncalibrated=args.only_uncalibrated)
    for r in res:
        if r.error:
            print(f"{'SKIP' if r.error.startswith('skipped') else 'FAILED'}  {r.source}: {r.error}")
            status = status or (0 if r.error.startswith("skipped") else 1)
        else:
            if r.report:
                print(r.report)
            print(f"ok      {r.source} -> {r.output}  [{', '.join(f'{c:.7g}' for c in r.coeffs)}]")
    return status


# --------------------------------------------------------------- registration
def add_tool_commands(sub) -> None:
    """Register the tool subcommands on the main parser's subparsers object."""
    p = sub.add_parser("index", help="catalogue a spectrum archive into an Excel workbook")
    p.add_argument("root", help="archive folder (read only)")
    p.add_argument("-o", "--out", required=True, help="catalogue .xlsx (outside the archive)")
    p.add_argument("--no-recursive", action="store_true", help="do not walk sub-folders")
    p.add_argument("--all-files", action="store_true", help="sniff every file, not only spectrum extensions")
    p.add_argument("--quiet", "-q", action="store_true")
    p.set_defaults(func=cmd_index)

    p = sub.add_parser("rescue", help="convert + verify a whole archive (resumable)")
    p.add_argument("root", help="archive folder (read only)")
    p.add_argument("-o", "--out", required=True, help="output folder (outside the archive)")
    p.add_argument("--to", "-t", action="append", help="output format (repeatable; default n42_2012 + ci_cnf)")
    p.add_argument("--resume", action="store_true", help="skip files already converted and verified")
    p.add_argument("--flat", action="store_true", help="do not recreate the folder tree")
    p.add_argument("--no-verify", action="store_true", help="skip read-back verification")
    p.add_argument("--no-recursive", action="store_true")
    p.add_argument("--skip-duplicates", action="store_true", help="convert byte-identical copies only once")
    p.add_argument("--limit", type=int, default=0, help="only the first N candidate files (trial run)")
    p.add_argument("--quiet", "-q", action="store_true")
    p.set_defaults(func=cmd_rescue)

    p = sub.add_parser("sum", help="sum spectra (energy-aligned if calibrations differ)")
    p.add_argument("files", nargs="+")
    p.add_argument("-o", "--out", required=True)
    p.add_argument("--to", "-t", help="output format (default: from the extension / first input)")
    p.add_argument("--align", choices=["auto", "channel", "energy"], default="auto")
    p.set_defaults(func=cmd_sum)

    p = sub.add_parser("subtract", help="subtract a live-time normalised background")
    p.add_argument("sample")
    p.add_argument("background")
    p.add_argument("-o", "--out", required=True)
    p.add_argument("--to", "-t")
    p.add_argument("--scale", type=float, help="background factor (default LT_sample / LT_background)")
    p.add_argument("--clip", action="store_true", help="set negative net channels to 0")
    p.add_argument("--sigma-csv", help="also write channel, energy, net, sigma to this CSV")
    p.set_defaults(func=cmd_subtract)

    p = sub.add_parser("rebin", help="compress channels (x2, x4 ...) and/or truncate the range")
    p.add_argument("file")
    p.add_argument("-o", "--out", required=True)
    p.add_argument("--factor", type=int, default=2)
    p.add_argument("--start", type=int, help="first channel to keep (truncate)")
    p.add_argument("--stop", type=int, help="channel after the last one kept")
    p.add_argument("--renumber", action="store_true", help="renumber truncated channels from 0")
    p.add_argument("--to", "-t")
    p.set_defaults(func=cmd_rebin)

    p = sub.add_parser("calibrate", help="fit / propose / apply an energy (and FWHM) calibration")
    p.add_argument("files", nargs="+")
    p.add_argument("--pairs", help="channel:keV pairs, e.g. 1893.7:661.66,3364:1173.23")
    p.add_argument("--source", help="calibration source nuclide(s), e.g. Eu-152 or Co-60,Cs-137")
    p.add_argument("--coeffs", help="apply these coefficients c0,c1[,c2,c3]")
    p.add_argument("--order", type=int, help="polynomial order 1-3")
    p.add_argument("--fwhm", help="channel:FWHM_keV pairs for a FWHM calibration")
    p.add_argument("--fwhm-order", type=int, default=1)
    p.add_argument("-o", "--out", help="write recalibrated copies into this folder")
    p.add_argument("--to", "-t", help="output format (default: input format if writable, else IAEA SPE)")
    p.add_argument("--only-uncalibrated", action="store_true", help="leave already calibrated files alone")
    p.set_defaults(func=cmd_calibrate)
