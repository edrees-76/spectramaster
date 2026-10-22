# Placeholder energy calibration E = channel: pre-registered protocol

Written 2026-10-22, before implementation. This is the open finding of
`fwhm_plausibility_amendment_protocol.md`. Results are appended below the line after the run;
nothing above it changes after its SHA-256 is recorded.

## 1. Defect

Some binary MCA files store the polynomial E = 0 + 1 · channel when the spectrum was never
calibrated. Our readers take it as a real calibration of 1 keV per channel. Then:

* the default resolution is computed for the wrong energies, so the peak widths are wrong;
* identification compares the peaks with library lines at the wrong energies;
* the detector-type guess and the activity windows use them too.

## 2. Measurements made before writing this protocol

Read-only survey: 1993 spectra in `test_corpus/` and `D:/SpectraMaster_public_data`, with every
format we read.

* **46 spectra have exactly E = 0 + 1 · channel.**
  * 36 ORTEC `.Chn`: all IAEA 2002 files; one of them, `maricsmall.chn`, also stores FWHM = 1.0.
  * 2 Canberra `.CNF`: IAEA 2002 `MIX2NEQ6`, `MIX2NEQLONG`. They are shown as (1, 1) after our
    Genie channel shift, so the stored values are (0, 1).
  * 8 Amptek `.mca` (`muGPD`). These files have no `<<CALIBRATION>>` section.
* **No other spectrum of any format has this polynomial.** The other CHN and CNF files of the
  corpus have real calibrations, for example (-1.07, 0.429) and (-0.31, 0.795).
* **SpecUtils (Sandia) agrees for CHN.** It reports the (0, 1) CHN trailer as
  `UnspecifiedUsingDefaultPolynomial`, that is, not a calibration. Our own CHN reader takes it as
  real.
  * For the Amptek files, SpecUtils returns (0, 1) as `Polynomial`, but the file holds no
    calibration.
  * For the CNF files it returns `Polynomial` (0, 1).
* **The CHN copies match their `.spe` copies.** The IAEA 2002 `.spe` copies have no calibration.
  * 35 of the 36 `.Chn` files have counts identical to their `.spe` copy. `maricsmall.chn`
    differs.
  * Live and real times differ by up to 1 s (rounding).
* Our `ortec_chn` and `ci_cnf` writers write zeros, not (0, 1), for a spectrum without a
  calibration.

## 3. Change

1. **Readers.** In the `ortec_chn`, `ci_cnf` and `amptek_mca` readers, a stored energy polynomial
   that is exactly (0, 1) is not used:
   * every further term is exactly 0; for CNF the check is made before the Genie channel shift;
   * `energy_coeffs` becomes empty, and the stored values are kept in
     `extra["stored_energy_coeffs"]`;
   * a stored FWHM calibration, meaningless without energies, moves to
     `extra["stored_fwhm_coeffs"]`;
   * `extra["energy_calibration"] = "placeholder"`.
2. **Note.** `convert.calibration_note(spectra)` returns a note for such spectra. `spectramaster
   info` prints it as a "Note" row. The GUI shows it in the status bar after opening, in English
   and Arabic.
3. **Unchanged:**
   * every other format;
   * every other polynomial, including one within rounding of (0, 1);
   * the writers;
   * the engine. `ENGINE_VERSION` stays 1.10.0, because no analysis code changes.

**Known limit, stated now.** A spectrum that really is calibrated at exactly 0 + 1 keV · channel
will be read without a calibration when it comes from one of these three formats. The survey found
none.

## 4. Criteria (set before the run)

| id | what | limit |
|---|---|---|
| PE.C1 | the 35 IAEA 2002 `.Chn` files whose counts equal their `.spe` copy | no energy calibration; stored values kept; peaks found (`find_peaks`, centroid, net area, FWHM) identical to the `.spe` copy |
| PE.C2 | `maricsmall.chn`, the 2 CNF, the 8 Amptek files | no energy calibration, stored values kept, note returned. Reported: peaks found on `maricsmall.chn` |
| PE.C3 | every other spectrum of the §2 survey | energy and FWHM calibration identical to `main`: 0 differences |
| PE.C4 | standard benchmark against after_FP2 | identical except runtime fields (key order included); 154 / 13 / 60 |
| PE.C5 | IAEA 2002 harness against after_FP2; CRM against after_FP2 | identical |
| PE.C6 | new unit tests; full suite | pass; changed existing tests listed with reasons |

Outputs go to a new folder `docs/baseline/after_PE1/`. No IAEA or Amptek data is copied into the
repository.

---
## Results

(appended after the run)

Run 2026-10-22, engine 1.10.0. The text above the line is unchanged (SHA-256 of the pre-registered
part still e22f6a76a90e5b043dbf2d8c0ca4baea86148cad3fb242e51e82ee58d2dbb06b). Outputs:
`docs/baseline/after_PE1/`:
* `placeholder_calibration_results.json`: per-file flags, stored coefficients and peak counts. No
  spectrum data is stored.
* `baseline.*`.

| id | value | limit | result |
|---|---|---|---|
| PE.C1 35 IAEA `.Chn` | all read without energy calibration, stored (0, 1) kept; peak lists identical to the `.spe` copy in 35 of 35 | | PASS |
| PE.C2 the other 11 | `maricsmall.chn`: no calibration, stored energy (0, 1) and FWHM (1) kept, note returned, 79 peaks (its `.spe` copy: 79; on `main` 14, after #52 102). The 2 CNF: no calibration, stored (0, 1), note. The 8 Amptek: no calibration, stored (0, 1) | | PASS |
| PE.C3 survey | 1993 spectra; 46 placeholders (36 CHN, 2 CNF, 8 Amptek); 0 other spectra with a changed energy or FWHM calibration | 0 | PASS |
| PE.C4 benchmark | 0 differences from after_FP2 (key order included, runtime fields excepted); 154 / 13 / 60 | | PASS |
| PE.C5 IAEA 2002, CRM | identical to after_FP2 | | PASS |
| PE.C6 tests | new `tests/test_placeholder_calibration.py` (7) pass; full suite 1396 passed, 69 skipped; no existing test changed | | PASS |

**What ships.**
* A CHN, CNF or Amptek MCA file holding the uncalibrated default E = 0 + 1 · channel is read
  without energy calibration. The stored values are kept in `extra`.
* `spectramaster info` and the GUI status bar say so and ask for a calibration.
* All 36 IAEA 2002 `.Chn` files now analyse exactly like their uncalibrated `.spe` copies; 35 of
  them have identical counts.
* No other file, benchmark value, IAEA 2002 or CRM result changes.
* The F1 check (#52) still guards stored FWHM calibrations that are wrong for other reasons.
