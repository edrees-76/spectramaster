"""Conversion engine shared by the CLI and the GUI."""
from __future__ import annotations

from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Callable, Iterable, Optional

from .formats import FormatError, FormatSpec, detect_format, get_format, load_all
from .model import Spectrum


def read_spectra(path: Path, fmt: Optional[FormatSpec] = None) -> tuple[list[Spectrum], FormatSpec]:
    """Read a file. `fmt=None` means auto-detect."""
    load_all()
    path = Path(path)
    if fmt is None:
        fmt = detect_format(path)
        if fmt is None:
            raise FormatError(f"cannot recognise the format of {path.name}")
    if not fmt.can_read:
        raise FormatError(f"{fmt.name} cannot be read")
    spectra = fmt.reader(path)
    if not spectra:
        raise FormatError(f"no spectrum found in {path.name}")
    for s in spectra:
        s.source_path = str(path)
        s.source_format = fmt.key
    return spectra, fmt


# Formats whose files hold fewer energy-calibration coefficients than our model.
# Writers silently truncate extra terms (a dropped cubic term on an 8k APTEC
# spectrum is ~6 keV at the top end), so we refit before handing over.
MAX_CAL_TERMS = {
    "ortec_chn": 3,
    "ortec_spc": 3,
    "spc_float": 3,
    "ci_s100": 3,
    "ci_cnf": 3,
    "laval_ascii": 2,
    "aptec_ascii": 6,
    "nd66": 3,
    "norland5000": 2,
}


# Formats that store sample_id/description but only as ASCII (or a code page
# that cannot hold Arabic): non-ASCII text comes back as '????' or is dropped.
# Determined by round-tripping Arabic vs ASCII text through every writable
# format (see tests/test_convert_text.py, which re-checks this set).
ASCII_ONLY_TEXT = {
    "ortec_chn",     # sample description -> '????'
    "ortec_spc",     # integer SPC: non-ASCII sample id dropped
    "spc_float",     # float SPC: non-ASCII sample id dropped
    "ci_s100",       # '????'
    "ci_cnf",        # '????' in title and description
    "nd66",          # '????'
}


# Formats that store text in the Windows Arabic code page (cp1256): Arabic letters are
# kept but Arabic-Indic digits (U+0660..U+0669, U+06F0..U+06F9) are not; they are
# written as 0-9.  Re-checked by tests/test_format_fidelity.py.
CP1256_TEXT = {
    "iec1455", "ieee_asc", "aptec_s0", "aptec_ascii", "davidson_ascii", "iaea_ascii_dat",
    "rump_ascii", "wallac_ascii",
}

# Formats whose channels hold non-negative values only.  A negative count (a
# background-subtracted or stripped spectrum) is refused rather than set to 0;
# formats not listed here either keep the sign or refuse it in their own writer.
NO_NEGATIVE_COUNTS = {
    "ortec_chn", "ortec_spc", "ci_cnf", "exploranium_gr130", "exploranium_gr135", "npl_ascii",
    "spc_ascii",     # SpecUtils writes it, but cannot read the file back
}

# Formats whose channels hold integers: fractional counts are rounded.
INTEGER_COUNTS = {
    "ortec_chn", "ortec_spc", "iec1455", "ieee_asc", "aptec_s0", "ci_s100", "ci_cnf",
    "exploranium_gr130", "exploranium_gr135", "aptec_ascii", "chandata_csv", "davidson_ascii",
    "iaea_ascii_dat", "npl_ascii", "rump_ascii", "wallac_ascii", "laval_ascii", "oxford_ans",
    "nd66",
}

# Formats that always hold an acquisition date: an unknown start time is written
# as a placeholder date that reads back as a real one.  (ORTEC CHN reads its
# placeholder back as unknown.)
DATE_REQUIRED = {
    "ortec_spc", "ci_cnf", "spc_float", "exploranium_gr130", "exploranium_gr135",
    "davidson_ascii", "rump_ascii",
}

_ARABIC_DIGITS = {**{0x0660 + i: str(i) for i in range(10)}, **{0x06F0 + i: str(i) for i in range(10)}}


def _text_fields(spec: Spectrum):
    return (("sample ID", spec.sample_id), ("description", spec.description))


def text_warning(spec: Spectrum, fmt: FormatSpec) -> Optional[str]:
    """Warning if `fmt` cannot store the non-ASCII text of `spec`, else None."""
    if fmt.key in CP1256_TEXT:
        def lost(v):
            try:
                v.encode("cp1256")
                return False
            except UnicodeEncodeError:
                return True
        fields = [name for name, value in _text_fields(spec) if value and lost(value)]
        if not fields:
            return None
        return (f"{fmt.name} stores text in the Arabic code page (cp1256): characters it cannot hold "
                f"in the {' and '.join(fields)} are lost")
    if fmt.key not in ASCII_ONLY_TEXT:
        return None
    fields = [name for name, value in _text_fields(spec) if value and not value.isascii()]
    if not fields:
        return None
    return (f"{fmt.name} stores only ASCII text: non-ASCII (e.g. Arabic) characters in the "
            f"{' and '.join(fields)} are lost")


def _fit_for_format(spec: Spectrum, fmt: FormatSpec, warnings: list[str]) -> Spectrum:
    """Counts, start time and text of `spec` as `fmt` can hold them: what it cannot hold is
    refused or reported, never changed silently."""
    import numpy as np

    counts = [float(c) for c in spec.counts]       # also accepts a numpy array
    if len(counts) == 0:
        raise FormatError("spectrum has no channels")
    if not all(np.isfinite(counts)):
        raise FormatError("the spectrum has non-finite channel contents (NaN or infinity)")
    changes = {"counts": counts}
    neg = sum(1 for c in counts if c < 0)
    if neg and fmt.key in NO_NEGATIVE_COUNTS:
        raise FormatError(f"{fmt.name} cannot store negative counts ({neg} channels are negative, "
                          "e.g. after a background subtraction); write it to a format that keeps them "
                          "(IAEA SPE, N42, JSON, Excel)")
    if fmt.key in INTEGER_COUNTS:
        diff = [abs(c - round(c)) for c in counts]
        n_frac = sum(1 for d in diff if d > 1e-9)
        if n_frac:
            warnings.append(f"{fmt.name} stores whole counts: {n_frac} fractional channel contents rounded "
                            f"(largest change {max(diff):.3g} counts)")
    if spec.start_time is None and fmt.key in DATE_REQUIRED:
        warnings.append(f"{fmt.name} always stores an acquisition date: the unknown start time is written "
                        "as a placeholder date, which reads back as a real date")
    if fmt.key in CP1256_TEXT | ASCII_ONLY_TEXT:
        fields = [name for name, value in _text_fields(spec) if value and value != value.translate(_ARABIC_DIGITS)]
        if fields:
            changes["sample_id"] = spec.sample_id.translate(_ARABIC_DIGITS)
            changes["description"] = spec.description.translate(_ARABIC_DIGITS)
            warnings.append(f"{fmt.name} cannot store Arabic-Indic digits: written as 0-9 in the "
                            f"{' and '.join(fields)}")
    return replace(spec, **changes)


def fit_calibration(spec: Spectrum, terms: int) -> tuple[list[float], float]:
    """Least-squares polynomial with `terms` coefficients approximating spec's
    calibration over its stored channels. Returns (coeffs, max abs error keV)."""
    import numpy as np
    from numpy.polynomial import polynomial as P

    ch = np.arange(spec.first_channel, spec.first_channel + max(spec.num_channels, terms + 1), dtype=float)
    e = P.polyval(ch, spec.energy_coeffs)
    coeffs = P.polyfit(ch, e, terms - 1)
    err = float(np.abs(P.polyval(ch, coeffs) - e).max())
    return [float(c) for c in coeffs], err


def write_spectrum(spec: Spectrum, path: Path, fmt: FormatSpec) -> list[str]:
    """Write one spectrum. Returns human-readable warnings (possibly empty)."""
    load_all()
    if not fmt.can_write:
        raise FormatError(f"{fmt.name} cannot be written")
    warnings: list[str] = []
    spec = _fit_for_format(spec, fmt, warnings)
    limit = MAX_CAL_TERMS.get(fmt.key)
    coeffs = list(spec.energy_coeffs)
    while coeffs and coeffs[-1] == 0.0:
        coeffs.pop()
    if limit and len(coeffs) > limit:
        new, err = fit_calibration(spec, limit)
        spec = replace(spec, energy_coeffs=new,
                       extra={**spec.extra, "original_energy_coeffs": ", ".join(f"{c:.10g}" for c in spec.energy_coeffs)})
        warnings.append(f"{fmt.name} stores only {limit} calibration terms: energy calibration "
                        f"refitted (max deviation {err:.3f} keV)")
    tw = text_warning(spec, fmt)
    if tw:
        warnings.append(tw)
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    fmt.writer(spec, Path(path))
    return warnings


def output_name(input_path: Path, out_fmt: FormatSpec, index: Optional[int] = None) -> str:
    """DataMaster naming rule: CHERN.S0 -> CHERN_S0.chn (index adds _2, _3 ...)."""
    p = Path(input_path)
    stem = p.stem
    if p.suffix:
        stem += "_" + p.suffix.lstrip(".")
    if index is not None:
        stem += f"_{index}"
    return stem + out_fmt.default_ext


@dataclass
class ConvertResult:
    source: Path
    outputs: list[Path]
    error: Optional[str] = None
    warnings: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return self.error is None


def convert_file(src: Path, out_fmt: FormatSpec, out_dir: Optional[Path] = None,
                 in_fmt: Optional[FormatSpec] = None, out_path: Optional[Path] = None,
                 overwrite: bool = True) -> ConvertResult:
    """Convert one file. Multi-spectrum inputs produce one output per spectrum."""
    src = Path(src)
    try:
        spectra, _ = read_spectra(src, in_fmt)
        outputs: list[Path] = []
        warnings: list[str] = []
        for i, spec in enumerate(spectra, start=1):
            if out_path is not None and len(spectra) == 1:
                target = Path(out_path)
            else:
                base = Path(out_path).parent if out_path else (Path(out_dir) if out_dir else src.parent)
                target = base / output_name(src, out_fmt, i if len(spectra) > 1 else None)
            if target.exists() and not overwrite:
                raise FormatError(f"{target.name} already exists")
            for w in write_spectrum(spec, target, out_fmt):
                if w not in warnings:
                    warnings.append(w)
            outputs.append(target)
        return ConvertResult(src, outputs, warnings=warnings)
    except Exception as exc:  # report, never abort a batch
        return ConvertResult(src, [], f"{type(exc).__name__}: {exc}")


def convert_many(sources: Iterable[Path], out_fmt: FormatSpec, out_dir: Optional[Path] = None,
                 in_fmt: Optional[FormatSpec] = None, overwrite: bool = True,
                 keep_tree_from: Optional[Path] = None,
                 progress: Optional[Callable[[int, int, ConvertResult], bool]] = None) -> list[ConvertResult]:
    """Batch conversion.

    keep_tree_from: if given (and out_dir given), recreate the sub-folder structure of
    each source relative to this root inside out_dir.
    progress(i, n, result) is called after each file; returning False cancels.
    """
    sources = [Path(s) for s in sources]
    results: list[ConvertResult] = []
    n = len(sources)
    for i, src in enumerate(sources, start=1):
        target_dir = out_dir
        if out_dir is not None and keep_tree_from is not None:
            try:
                target_dir = Path(out_dir) / src.parent.relative_to(keep_tree_from)
            except ValueError:
                target_dir = Path(out_dir)
        r = convert_file(src, out_fmt, target_dir, in_fmt, overwrite=overwrite)
        results.append(r)
        if progress is not None and progress(i, n, r) is False:
            break
    return results


def resolve_format(value) -> FormatSpec:
    load_all()
    return get_format(value)
