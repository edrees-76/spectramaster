"""Command-line interface.

DataMaster-compatible form (format numbers from DataMaster Table 1, 0 = auto-detect)::

    python -m spectramaster -13 CHERN.S0 -1 "C:\\Spectra\\Converted Chern.chn"

Modern form::

    python -m spectramaster convert INPUTS... --to chn [--from aptec_s0|auto]
                                   [--out DIR] [--recursive] [--keep-tree] [--no-overwrite]
    python -m spectramaster info FILE [--from KEY]
    python -m spectramaster formats
    python -m spectramaster peaks FILE... [--min-sig 3]
    python -m spectramaster identify FILE... [--min-sig 3] [--lib LIB.json|LIB.csv] [--peaks]
    python -m spectramaster gui [FILES...]

Expert tools (see spectramaster/tools/cli_tools.py)::

    python -m spectramaster index ROOT -o catalog.xlsx
    python -m spectramaster rescue ROOT -o OUTDIR --to n42_2012 --to ci_cnf [--resume]
    python -m spectramaster sum | subtract | rebin | calibrate ...

With no arguments at all the graphical interface is started.
"""
from __future__ import annotations

import argparse
import glob
import os
import re
import sys
from pathlib import Path
from typing import Optional, Sequence

from . import convert as engine
from .formats import FormatSpec, all_formats, get_format, load_all, readable_formats

_DM_CODE = re.compile(r"^-(\d{1,3})$")
_GLOB_CHARS = set("*?[")


# ----------------------------------------------------------------- utilities
def _setup_console() -> None:
    """UTF-8 output so Arabic (and any other) file names print on Windows."""
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError, OSError):
            pass


def _err(msg: str) -> None:
    print(msg, file=sys.stderr)


def _resolve(value: str) -> FormatSpec:
    load_all()
    try:
        return get_format(value)
    except KeyError:
        raise SystemExit(_usage_error(f"unknown format {value!r} (see 'formats')"))


def _usage_error(msg: str) -> int:
    _err(f"error: {msg}")
    return 2


def _is_readable_candidate(path: Path, in_fmt: Optional[FormatSpec]) -> bool:
    """Should a file found while walking a folder be converted?

    With an explicit input format: extension match (DataMaster behaviour).
    Auto mode: a content sniffer must recognise the file, or its extension must
    belong to a readable format that has no sniffer (plain-text formats).  This keeps
    reports, CSV tables, binary look-alikes ... out of batch conversions.
    """
    if in_fmt is not None:
        return path.suffix.lower() in in_fmt.extensions
    try:
        with open(path, "rb") as fh:
            head = fh.read(4096)
    except OSError:
        return False
    ext = path.suffix.lower()
    for f in readable_formats():
        if f.sniffer is not None:
            try:
                if f.sniffer(path, head):
                    return True
            except Exception:
                pass
    return any(ext in f.extensions and f.sniffer is None for f in readable_formats())


def collect_inputs(inputs: Sequence[str], in_fmt: Optional[FormatSpec], recursive: bool
                   ) -> list[tuple[Path, Optional[Path]]]:
    """Expand files / folders / globs into (file, tree_root) pairs.

    tree_root is the folder the file was found under (for --keep-tree), or None for
    files named explicitly.
    """
    out: list[tuple[Path, Optional[Path]]] = []
    seen: set[str] = set()

    def add(p: Path, root: Optional[Path]):
        key = os.path.normcase(str(p.resolve()))
        if key not in seen:
            seen.add(key)
            out.append((p, root))

    for raw in inputs:
        if any(ch in raw for ch in _GLOB_CHARS) and not Path(raw).exists():
            matches = sorted(glob.glob(raw, recursive=recursive))
            if not matches:
                _err(f"warning: no files match {raw}")
            base = _glob_base(raw)
            for m in matches:
                p = Path(m)
                if p.is_file():
                    add(p, base)
                elif p.is_dir():
                    for f in _walk(p, in_fmt, recursive):
                        add(f, p)
            continue
        p = Path(raw)
        if p.is_dir():
            for f in _walk(p, in_fmt, recursive):
                add(f, p)
        elif p.is_file():
            add(p, None)
        else:
            _err(f"warning: {raw} not found")
    return out


def _glob_base(pattern: str) -> Optional[Path]:
    parts = Path(pattern).parts
    base = []
    for part in parts:
        if any(ch in part for ch in _GLOB_CHARS):
            break
        base.append(part)
    return Path(*base) if base else Path(".")


def _walk(folder: Path, in_fmt: Optional[FormatSpec], recursive: bool) -> list[Path]:
    it = folder.rglob("*") if recursive else folder.iterdir()
    files = sorted((p for p in it if p.is_file()), key=lambda p: str(p).lower())
    return [p for p in files if _is_readable_candidate(p, in_fmt)]


def _fmt_num(v, unit: str = "", digits: int = 3) -> str:
    if v is None:
        return "-"
    if isinstance(v, float):
        s = f"{v:.{digits}f}".rstrip("0").rstrip(".") if abs(v) < 1e7 else f"{v:.6g}"
    else:
        s = str(v)
    return s + unit


# ------------------------------------------------------------------ commands
def cmd_formats(args) -> int:
    load_all()
    rows = [("Code", "Key", "Name", "Extensions", "Read", "Write")]
    for f in all_formats():
        rows.append((str(f.code), f.key, f.name, " ".join("*" + e for e in f.extensions),
                     "Yes" if f.can_read else "No", "Yes" if f.can_write else "No"))
    widths = [max(len(r[i]) for r in rows) for i in range(len(rows[0]))]
    for n, r in enumerate(rows):
        print("  ".join(c.ljust(w) for c, w in zip(r, widths)).rstrip())
        if n == 0:
            print("  ".join("-" * w for w in widths))
    return 0


def cmd_info(args) -> int:
    load_all()
    in_fmt = None if args.in_fmt in (None, "auto") else _resolve(args.in_fmt)
    status = 0
    for name in args.files:
        path = Path(name)
        try:
            spectra, fmt = engine.read_spectra(path, in_fmt)
        except Exception as exc:
            _err(f"{path}: {exc}")
            status = 1
            continue
        for i, s in enumerate(spectra, start=1):
            title = f"{path}" + (f"  [spectrum {i}/{len(spectra)}]" if len(spectra) > 1 else "")
            print(title)
            print("=" * min(len(title), 100))
            rows = [
                ("Format", f"{fmt.name} ({fmt.key}, code {fmt.code})"),
                ("Sample ID", s.sample_id or "-"),
                ("Description", (s.description or "-").replace("\n", " | ")),
                ("Detector", s.detector or "-"),
                ("Start time", s.start_time.isoformat(sep=" ") if s.start_time else "-"),
                ("Live time", _fmt_num(s.live_time, " s")),
                ("Real time", _fmt_num(s.real_time, " s")),
                ("Dead time", _fmt_num(s.dead_time_percent, " %", 2)),
                ("Channels", f"{s.num_channels} (first {s.first_channel})"),
                ("Total counts", _fmt_num(s.total_counts, "", 1)),
            ]
            note = engine.content_note([s], fmt)
            if note:
                rows.insert(1, ("Note", note))
            cal_note = engine.calibration_note([s])
            if cal_note:
                rows.insert(1, ("Note", cal_note))
            if s.energy_coeffs:
                e = s.energies() or [0.0]
                rows.append(("Energy cal.", ", ".join(f"{c:.7g}" for c in s.energy_coeffs)))
                rows.append(("Energy range", f"{e[0]:.3f} .. {e[-1]:.3f} keV"))
            else:
                rows.append(("Energy cal.", "none"))
            if s.fwhm_coeffs:
                rows.append(("FWHM cal.", ", ".join(f"{c:.7g}" for c in s.fwhm_coeffs)))
            for k, v in s.extra.items():
                rows.append((k, str(v).replace("\n", " | ")))
            w = max(len(r[0]) for r in rows)
            for k, v in rows:
                print(f"  {k.ljust(w)} : {v}")
            print()
    return status


def _print_result(r: engine.ConvertResult, quiet: bool) -> None:
    if r.ok:
        if not quiet:
            outs = ", ".join(str(o) for o in r.outputs)
            print(f"ok      {r.source} -> {outs}")
        for w in r.warnings:
            print(f"  warning: {w}")
    else:
        print(f"FAILED  {r.source}: {r.error}")


def _summary(results: list[engine.ConvertResult]) -> int:
    ok = sum(1 for r in results if r.ok)
    failed = len(results) - ok
    outputs = sum(len(r.outputs) for r in results)
    print(f"\n{len(results)} file(s): {ok} converted ({outputs} output file(s)), {failed} failed.")
    return 1 if failed or not results else 0


def cmd_convert(args) -> int:
    load_all()
    out_fmt = _resolve(args.to)
    if not out_fmt.can_write:
        return _usage_error(f"{out_fmt.name} cannot be written")
    in_fmt = None if args.in_fmt in (None, "auto") else _resolve(args.in_fmt)
    if in_fmt is not None and not in_fmt.can_read:
        return _usage_error(f"{in_fmt.name} cannot be read")
    items = collect_inputs(args.inputs, in_fmt, args.recursive)
    if not items:
        _err("no input files found")
        return 1
    out_dir = Path(args.out) if args.out else None
    results: list[engine.ConvertResult] = []
    for src, root in items:
        target_dir = out_dir
        if out_dir is not None and args.keep_tree and root is not None:
            try:
                target_dir = out_dir / src.parent.relative_to(root)
            except ValueError:
                target_dir = out_dir
        r = engine.convert_file(src, out_fmt, target_dir, in_fmt, overwrite=not args.no_overwrite)
        _print_result(r, args.quiet)
        results.append(r)
    return _summary(results)


def _analysis_targets(args):
    load_all()
    in_fmt = None if args.in_fmt in (None, "auto") else _resolve(args.in_fmt)
    for name in args.files:
        path = Path(name)
        try:
            spectra, _fmt = engine.read_spectra(path, in_fmt)
        except Exception as exc:
            _err(f"{path}: {exc}")
            yield path, None, None
            continue
        for i, s in enumerate(spectra, start=1):
            title = f"{path}" + (f"  [spectrum {i}/{len(spectra)}]" if len(spectra) > 1 else "")
            yield path, title, s


def _print_table(rows: list[tuple], header: tuple, left: Sequence[int] = ()) -> None:
    """Numbers right-aligned, text left-aligned; columns listed in ``left`` always left-aligned."""
    rows = [tuple(str(c) for c in r) for r in rows]
    widths = [max(len(str(h)), *(len(r[i]) for r in rows)) if rows else len(str(h))
              for i, h in enumerate(header)]
    print("  " + "  ".join(str(h).ljust(w) for h, w in zip(header, widths)).rstrip())
    print("  " + "  ".join("-" * w for w in widths))
    for r in rows:
        print("  " + "  ".join(c.rjust(w) if i not in left and (c[:1].isdigit() or c[:1] == "-" and c[1:2].isdigit())
                               else c.ljust(w) for i, (c, w) in enumerate(zip(r, widths))).rstrip())


def _peak_rows(peaks, with_id=False):
    rows = []
    for k, p in enumerate(peaks, start=1):
        row = [k, f"{p.centroid:.2f}", "-" if p.energy is None else f"{p.energy:.2f}",
               "-" if p.fwhm_kev is None else f"{p.fwhm_kev:.2f}", f"{p.net_area:.0f}",
               f"{100 * p.net_area_unc / p.net_area:.1f}" if p.net_area > 0 else "-",
               "-" if p.count_rate is None else f"{p.count_rate:.4g}", f"{p.significance:.1f}"]
        if with_id:
            row.append(p.nuclide or "")
            row.append("" if p.line_energy is None else f"{p.line_energy:.2f}")
        row.append(p.note)
        rows.append(tuple(row))
    return rows


def cmd_peaks(args) -> int:
    from .analysis import find_peaks
    from .analysis.background import not_poisson_note
    status = 0
    for path, title, s in _analysis_targets(args):
        if s is None:
            status = 1
            continue
        peaks = find_peaks(s, min_sig=args.min_sig)
        print(title)
        print("=" * min(len(title), 100))
        if not s.energy_coeffs:
            print("  (spectrum is not energy calibrated: energies not available)")
        note = not_poisson_note(s)
        if note:
            _err(f"warning: {title}: {note}")
        print(f"  {len(peaks)} peak(s), significance >= {args.min_sig:g}")
        _print_table(_peak_rows(peaks), ("#", "Channel", "keV", "FWHM keV", "Net", "Unc %", "cps", "Sig", "Note"))
        print()
    return status


def cmd_identify(args) -> int:
    from datetime import datetime
    from .analysis import find_peaks, identify
    sampled = None
    if args.sampled:
        try:
            sampled = datetime.fromisoformat(args.sampled)
        except ValueError:
            _err(f"error: --sampled {args.sampled!r} is not an ISO date/time (e.g. 2024-03-01T10:00)")
            return 2
    status = 0
    for path, title, s in _analysis_targets(args):
        if s is None:
            status = 1
            continue
        print(title)
        print("=" * min(len(title), 100))
        if not s.energy_coeffs:
            print("  spectrum is not energy calibrated: nuclide identification needs an energy calibration")
            print()
            continue
        peaks = find_peaks(s, min_sig=args.min_sig)
        if sampled is not None and s.start_time is not None and sampled > s.start_time:
            _err(f"error: {title}: the sampling date is after the start of the acquisition")
            status = 1
            continue
        try:
            matches = identify(s, peaks, library=args.lib, min_confidence=args.min_conf, sampled=sampled)
        except (OSError, ValueError) as exc:
            _err(f"error: cannot use library {args.lib}: {exc}")
            return 2
        rows = []
        for m in matches:
            lines = ", ".join(f"{e:.1f}" for e, _p in m.matched[:8]) + (" ..." if len(m.matched) > 8 else "")
            rows.append((m.nuclide, f"{m.confidence:.2f}", m.half_life or "-", m.category or "-", lines, m.note))
        print(f"  {len(peaks)} peak(s), {len(matches)} nuclide(s)")
        if rows:
            _print_table(rows, ("Nuclide", "Conf.", "Half-life", "Category", "Matched lines keV", "Note"), left=(4,))
        if args.peaks:
            print()
            _print_table(_peak_rows(peaks, True), ("#", "Channel", "keV", "FWHM keV", "Net", "Unc %", "cps",
                                                   "Sig", "Nuclide", "Line keV", "Note"))
        print()
    return status


def cmd_gui(args) -> int:
    return _launch_gui(list(args.files))


GUI_HINT = ("This is the command-line converter; the graphical interface is SpectraMaster.exe "
            "(installed next to smconvert.exe).")


def gui_available() -> bool:
    """False in the command-line-only build (smconvert.exe is frozen without PySide6)."""
    import importlib.util
    try:
        return importlib.util.find_spec("PySide6") is not None
    except (ImportError, ValueError):
        return False


def _launch_gui(files: list[str]) -> int:
    if not gui_available():
        _err(GUI_HINT)
        return 2
    try:
        from .gui.app import main as gui_main
    except ImportError as exc:
        _err(f"The graphical interface is not available ({exc}).")
        _err(GUI_HINT)
        return 2
    return int(gui_main([sys.argv[0]] + files) or 0)


def run_datamaster(argv: list[str]) -> int:
    """`-i INPUT -j OUTPUT` exactly like ORTEC DataMaster (0 = auto-detect input)."""
    if len(argv) != 4 or not _DM_CODE.match(argv[0]) or not _DM_CODE.match(argv[2]):
        return _usage_error("DataMaster syntax is:  -i InputFileName -j OutputFileName")
    load_all()
    i, j = int(argv[0][1:]), int(argv[2][1:])
    src, dst = Path(argv[1]), Path(argv[3])
    try:
        in_fmt = None if i == 0 else get_format(i)
        out_fmt = get_format(j)
    except KeyError as exc:
        return _usage_error(str(exc).strip("'\""))
    if in_fmt is not None and not in_fmt.can_read:
        return _usage_error(f"format {i} ({in_fmt.name}) cannot be read")
    if not out_fmt.can_write:
        return _usage_error(f"format {j} ({out_fmt.name}) cannot be written")
    if not src.is_file():
        _err(f"error: input file not found: {src}")
        return 1
    r = engine.convert_file(src, out_fmt, in_fmt=in_fmt, out_path=dst)
    _print_result(r, False)
    return 0 if r.ok else 1


# ------------------------------------------------------------------- parser
def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="spectramaster",
        description="Gamma-spectrum file converter (DataMaster compatible).",
        epilog="DataMaster form:  spectramaster -i INPUT -j OUTPUT   "
               "(i, j = format codes from 'spectramaster formats'; i = 0 auto-detects)")
    sub = p.add_subparsers(dest="command", metavar="COMMAND")

    c = sub.add_parser("convert", help="convert files, folders or glob patterns")
    c.add_argument("inputs", nargs="+", help="input files, folders or glob patterns")
    c.add_argument("--to", "-t", required=True, help="output format key, alias or code")
    c.add_argument("--from", "-f", dest="in_fmt", default="auto",
                   help="input format key/code, or 'auto' (default)")
    c.add_argument("--out", "-o", help="output folder (default: next to each input)")
    c.add_argument("--recursive", "-r", action="store_true", help="walk sub-folders")
    c.add_argument("--keep-tree", action="store_true",
                   help="recreate the input sub-folder structure inside --out")
    c.add_argument("--no-overwrite", action="store_true", help="skip existing outputs (reported as failures)")
    c.add_argument("--quiet", "-q", action="store_true", help="only print failures and the summary")
    c.set_defaults(func=cmd_convert)

    i = sub.add_parser("info", help="print the metadata of spectrum files")
    i.add_argument("files", nargs="+")
    i.add_argument("--from", "-f", dest="in_fmt", default="auto")
    i.set_defaults(func=cmd_info)

    f = sub.add_parser("formats", help="list supported formats and their codes")
    f.set_defaults(func=cmd_formats)

    pk = sub.add_parser("peaks", help="search and fit peaks, print a peak table")
    pk.add_argument("files", nargs="+")
    pk.add_argument("--from", "-f", dest="in_fmt", default="auto")
    pk.add_argument("--min-sig", type=float, default=3.0, help="significance threshold (default 3)")
    pk.set_defaults(func=cmd_peaks)

    idn = sub.add_parser("identify", help="identify nuclides (peak search + library matching)")
    idn.add_argument("files", nargs="+")
    idn.add_argument("--from", "-f", dest="in_fmt", default="auto")
    idn.add_argument("--min-sig", type=float, default=3.0, help="peak significance threshold (default 3)")
    idn.add_argument("--lib", default=None, help="nuclide library (JSON like the bundled one, or CSV "
                                                 "nuclide,energy_keV,intensity_%%[,half_life,category])")
    idn.add_argument("--min-conf", type=float, default=0.25, help="minimum confidence 0..1 (default 0.25)")
    idn.add_argument("--peaks", action="store_true", help="also print the peak table with assignments")
    idn.add_argument("--sampled", default=None, help="end of sampling (ISO date/time): nuclides decayed by more "
                                                     "than 10 half-lives since then get a low plausibility")
    idn.set_defaults(func=cmd_identify)

    g = sub.add_parser("gui", help="start the graphical interface")
    g.add_argument("files", nargs="*")
    g.set_defaults(func=cmd_gui)

    # expert tools: index, rescue, sum, subtract, rebin, calibrate
    from .tools.cli_tools import add_tool_commands
    add_tool_commands(sub)
    from .tools.quant_cli import add_quant_commands
    add_quant_commands(sub)
    return p


def main(argv: Optional[Sequence[str]] = None) -> int:
    _setup_console()
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv:
        if gui_available():
            return _launch_gui([])
        build_parser().print_help()          # CLI-only build: usage, not a developer message
        print()
        print(GUI_HINT)
        return 0
    if _DM_CODE.match(argv[0]):
        return run_datamaster(argv)
    parser = build_parser()
    try:
        args = parser.parse_args(argv)
    except SystemExit as exc:
        return int(exc.code or 0)
    if not getattr(args, "func", None):
        parser.print_help()
        return 2
    try:
        return int(args.func(args) or 0)
    except SystemExit as exc:  # raised by _resolve
        return int(exc.code or 0) if isinstance(exc.code, int) else 2
    except KeyboardInterrupt:
        _err("interrupted")
        return 130


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
