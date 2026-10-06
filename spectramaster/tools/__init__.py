"""Expert tools: archive catalogue & rescue, spectrum arithmetic, re-calibration.

Public API (stable; intended for the CLI and the GUI)
====================================================

Archive (``spectramaster.tools.archive``) -- never writes inside the archive root
----------------------------------------------------------------------------------
``index_archive(root, out_xlsx=None, recursive=True, progress=None, all_files=False, files=None) -> IndexResult``
    Catalogue every recognised spectrum under `root`; writes an Excel workbook
    (Catalog / Summary / Duplicates / Mirrored folders / Errors) if `out_xlsx`.
    ``IndexResult``: ``entries`` (list[CatalogEntry]), ``duplicates``
    (list[DuplicateGroup]), ``mirrored_folders`` [(folder_a, folder_b, n)],
    ``errors``, ``duplicate_files``, ``files_scanned``, ``files_skipped``, ``elapsed``.
``scan_file(path, root=None) -> list[CatalogEntry]``     one file (for a live GUI table)
``find_spectrum_files(root, recursive=True, all_files=False) -> list[Path]``
``rescue_archive(root, out_root, formats=("n42_2012", "ci_cnf"), keep_tree=True, verify=True,
                 resume=False, recursive=True, skip_duplicates=False, progress=None, files=None,
                 report_xlsx=None, manifest_csv=None, energy_tol=0.05, time_tol=0.02, energy_fail=1.0) -> RescueResult``
    Converts into ``out_root/<format>/<tree>``, re-reads and verifies every
    output, writes ``manifest.csv`` (journal, resumable) and
    ``verification_report.xlsx``.  ``RescueResult.entries`` (list[RescueEntry]
    with ``status`` VERIFIED / VERIFIED (warnings) / FAILED / ERROR / DUPLICATE /
    WRITTEN, ``details``, ``verification``, ``skipped``), ``counts()``.
``verify_output(src, out, ...) -> Verification``          compare two Spectrum objects
``sha256_file(path) -> str``, ``spectrum_fingerprint(spectrum) -> str``

progress callbacks: ``progress(done: int, total: int, path: Path) -> bool | None``;
return ``False`` to cancel (partial results are still returned / written).

Arithmetic (``spectramaster.tools.arithmetic``) -- pure functions, return new Spectrum
-------------------------------------------------------------------------------------
``sum_spectra(spectra, align="auto"|"channel"|"energy", reference=None) -> Spectrum``
``subtract_background(sample, background, scale=None, align="auto", clip_negative=False) -> (Spectrum, sigma: list[float])``
``scale_spectrum(spec, factor, scale_times=False) -> Spectrum``
``rebin(spec, factor: int) -> Spectrum``                    counts conserved, calibration rewritten
``truncate(spec, start, stop=None, renumber=False) -> Spectrum``
``truncate_energy(spec, e_low, e_high, renumber=False) -> Spectrum``
``align_to(spec, reference) -> Spectrum``                  energy rebinning onto reference grid
``same_calibration(a, b, tol_kev=0.01) -> bool``

Calibration (``spectramaster.tools.calibrate``)
-----------------------------------------------
``fit_energy_calibration(pairs[(ch, keV)], order=1..3, weights=None, labels=()) -> CalibrationFit``
``fit_fwhm_calibration(pairs[(ch, fwhm_keV)], order=1, ...) -> CalibrationFit``
    ``CalibrationFit``: ``coeffs``, ``residuals``, ``rms``, ``max_abs_residual``, ``report()``.
``find_peaks(spectrum_or_counts, min_significance=5.0, max_peaks=60, fwhm_guess=None) -> list[Peak]``
``calibrate_from_source(spec, "Eu-152" | ["Co-60", "Cs-137"], order=None, initial_coeffs=None, ...) -> SourceCalibration``
    ``SourceCalibration``: ``coeffs``, ``fit``, ``fwhm_fit``, ``matches``, ``unmatched``, ``report()``.
``apply_calibration(spec, energy_coeffs=None, fwhm_coeffs=None, note="") -> Spectrum``
``apply_calibration_batch(paths, out_dir, energy_coeffs=None, fwhm_coeffs=None, source=None, order=None,
                          out_fmt=None, only_uncalibrated=False, progress=None) -> list[BatchCalibrationResult]``
``NUCLIDE_LINES``: {nuclide: [(keV, intensity %), ...]};  ``parse_pairs("ch:keV, ...")``.
"""
from __future__ import annotations

from .archive import (CatalogEntry, IndexResult, RescueEntry, RescueResult, Verification,
                      find_spectrum_files, index_archive, rescue_archive, scan_file, sha256_file,
                      spectrum_fingerprint, verify_output)
from .arithmetic import (SpectrumMathError, align_to, rebin, same_calibration, scale_spectrum,
                         subtract_background, sum_spectra, truncate, truncate_energy)
from .calibrate import (NUCLIDE_LINES, CalibrationFit, Peak, SourceCalibration, apply_calibration,
                        apply_calibration_batch, calibrate_from_source, find_peaks,
                        fit_energy_calibration, fit_fwhm_calibration, parse_pairs)

__all__ = [
    "CatalogEntry", "IndexResult", "RescueEntry", "RescueResult", "Verification",
    "find_spectrum_files", "index_archive", "rescue_archive", "scan_file", "sha256_file",
    "spectrum_fingerprint", "verify_output",
    "SpectrumMathError", "align_to", "rebin", "same_calibration", "scale_spectrum",
    "subtract_background", "sum_spectra", "truncate", "truncate_energy",
    "NUCLIDE_LINES", "CalibrationFit", "Peak", "SourceCalibration", "apply_calibration",
    "apply_calibration_batch", "calibrate_from_source", "find_peaks", "fit_energy_calibration",
    "fit_fwhm_calibration", "parse_pairs",
]
