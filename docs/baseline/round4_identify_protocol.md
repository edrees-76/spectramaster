# Round-4 review, identification findings (R4-B): evaluation protocol (pre-registered)

Written 2026-10-27, **before** the changes below were made. The reference values "before" were
computed with engine 1.15.0 (commit 1aa179d) by the harness of this protocol
(`python -m spectramaster.validation.round4_identify`); the per-spectrum lists of the CRM spectra
are kept in `docs/baseline/after_R4B/round4_identify_before.json`. The findings come from the fourth
external review (Codex M2 and section 5.9, Gemini M3) and were checked on the code first. The limits
must not be changed after results are known. A result outside a limit is reported as a failure.

## Findings and changes

1. **Resolution model with a channel offset (Codex M2).** `identify._Context._fwhm_kev` evaluates the
   FWHM calibration at the array index, not at the absolute channel (`first_channel + index`) used by
   the energy calibration and by the peak search. Codex's case (`first_channel` 1000, energy
   `[0, 0.5]`, FWHM `[1, 0.001]`): 2.0 keV at 1000 keV instead of 3.0 keV. Change: the absolute
   channel is used.
2. **Half-life against the time since sampling (Codex 5.9, Gemini M3).** Identification has no
   information on the age of the sample, so a weak line at 847 keV (Mn-56, 2.58 h), 740 keV (Mo-99,
   2.75 d) or 141 keV (Tc-99m) can be attributed to a nuclide that cannot be present any more. Change:
   `identify(..., sampled=datetime)` (end of sampling, or the time the material was taken). When more
   than 10 half-lives have elapsed between `sampled` and the acquisition start (activity below
   2^-10 = 0.1 % of the activity at sampling), the plausibility prior of the nuclide is multiplied by
   0.25 and, if it is still reported, its note says how many half-lives have elapsed. Not penalised:
   members of a natural series (supported by long-lived parents), and a nuclide included by a parent
   of the library (`includes`, e.g. Tc-99m with Mo-99) whose own elapsed time is at most 10
   half-lives. A sampling date after the acquisition start is refused (ValueError). Without `sampled`
   (or without an acquisition start) nothing changes. The GUI analysis passes the end (else the start)
   of sampling of the session's sample information when it exists; the CLI `identify` gets
   `--sampled`.
3. **Medical nuclides in the "common" list (Gemini M3).** Mo-99, Tc-99m, F-18, Ga-67, Ga-68, In-111,
   Tl-201, Lu-177, I-123 and I-125 had no "uncommon nuclide" prior penalty in every application.
   Change: they are common only with the medical application library; elsewhere they get the same
   prior as any other uncommon nuclide (0.8 for germanium, 0.65 for NaI).
4. **Single matched line (Codex 5.9).** A nuclide reported from one matched gamma line although its
   library has two or more gamma lines of at least 1 % in the spectrum's energy range now carries the
   note "one line matched (the other lines are below the detection limit): confirm". The confidence
   is not changed.

Engine version raised.

## Criteria

| ID | quantity | limit |
|---|---|---|
| RB.C1 | Codex's case; synthetic HPGe spectrum with a FWHM calibration, and the same spectrum without its first 150 channels (`first_channel` 150), same peak list | Codex's case 3.0 keV (relative 1e-9); the FWHM of the identification at 150, 300, 662, 1000, 1332, 1800 keV equal for the full and the cropped spectrum (relative 1e-9). The identifications of the two spectra are reported (no limit: the cropped spectrum has a different energy range) |
| RB.C2 | synthetic HPGe spectrum with Cs-137, K-40, Mn-56, Mo-99 and Tc-99m (seed 4242) identified without and with a sampling date | 1 h before the start: every result identical to "no date" (confidence and note). 3 days: Cs-137, K-40, Mo-99 and Tc-99m identical; Mn-56 not reported, or confidence at most half its "no date" value with the half-life note. 30 days: Mn-56, Mo-99 and Tc-99m each not reported or at most half the "no date" confidence with the note; Cs-137 and K-40 reported with confidence >= 0.9. A sampling date after the start raises ValueError |
| RB.C3 | synthetic spectrum with only the 847 keV line of Mn-56 (150 counts, seed 4243) | Co-56 and Ba-133 (one gamma line matched, several in the library) carry the single-line note; Cs-137 and K-40 do not; Mo-99 of RB.C2 (several lines matched) does not. Confidences of this spectrum identical to before |
| RB.C4 | plausibility prior of the ten medical nuclides, I-131 and Cs-137 (matched lines of 50 %) | applications "all" and "environmental": 0.8 x before for the medical nuclides; "medical": as before; I-131 and Cs-137 as before everywhere |
| RB.C5 | 255 HPGe spectra of certified reference materials (Zenodo 23093533; soils, sediments and their mixtures, measured 2013-2022, all prepared years before), identified with `sampled` = start - 30 days (a lower bound of the age of every material) | identifications of non-series nuclides with more than 10 half-lives in 30 days (half-life < 3 d): at most 20 % of the number without a date (118 before, so <= 23). Identifications of long-lived nuclides (half-life >= 30 d) or series members present without a date and lost with the date: at most 1 % of 3303 (<= 33) |
| RB.C6 | the same 255 spectra without a date, before and after the change | medical-nuclide identifications at most as many as before (41); long-lived or series identifications lost compared with before: at most 1 % (<= 33) |
| RB.C7 | existing tests and the benchmark report | full test suite passes; benchmark PASS/FAIL counts unchanged (154 / 13), no criterion PASS -> FAIL |

## Outputs

`docs/baseline/after_R4B/round4_identify.md` and `.json` (counts and nuclide names only; the CRM data
stay outside the repository).

## Limitations

- The 10 half-lives limit and the factor 0.25 are judgement, not a statistical test; a nuclide
  produced after sampling (activation, in-growth from a parent missing from the library) is
  penalised. The note gives the reason.
- RB.C5 uses one assumed lower bound of the age of public materials, not their sampling dates.
- The single-line note does not change the identification; the reviewer decides.

---

## Results (2026-10-27)

`python -m spectramaster.validation.round4_identify` (engine 1.16.0), output in
`docs/baseline/after_R4B/`. **7 PASS / 0 FAIL.**

| ID | result | detail |
|---|---|---|
| RB.C1 | PASS | Codex's case 2.0 -> 3.0 keV; FWHM of the cropped spectrum equal to the full one at every energy. Identifications still differ (full: Co-60, Cs-137, K-40, Co-57 0.744; cropped: Co-60 0.974, Cs-137, K-40, Eu-152 0.279): the cropped spectrum has no data below 75 keV, so lines there are not counted |
| RB.C2 | PASS | 1 h: identical. 3 d: Cs-137, K-40, Mo-99, Tc-99m identical, Mn-56 (28 half-lives) not reported. 30 d: Mn-56, Mo-99, Tc-99m not reported; Cs-137 0.973, K-40 0.976. Date after start refused. (Mo-99 and Tc-99m without a date 0.999 / 0.993 -> 0.799 / 0.794 from change 3.) |
| RB.C3 | PASS | Co-56 and Ba-133 (one line of several) carry the note; Cs-137, K-40 and Mo-99 do not; confidences identical |
| RB.C4 | PASS | medical nuclides 0.8 with "all" and "environmental", 1.0 with "medical"; I-131 and Cs-137 1.0 |
| RB.C5 | PASS | CRM spectra with `sampled` = start - 30 d: short-lived identifications 118 -> 0; long-lived / series identifications lost 3 of 3300 (Rn-219, Th-231, Pa-231: U-235 series members, one each) |
| RB.C6 | PASS | CRM spectra without a date: medical identifications 41 -> 21; long-lived / series lost 8 of 3303 (Th-234 5, U-235 1, I-125 1, Yb-169 1), gained Th-232 3, Th-230 1, Th-234 1, Cu-67 1; short-lived 118 -> 108; 293 single-line notes |
| RB.C7 | PASS | benchmark 154 PASS / 13 FAIL / 60 REPORT, no criterion changed status; changed values: IDB implausible identifications per spectrum HPGe 8.19 -> 8.03, CdTe 6.71 -> 5.43, LaBr3 5.61 -> 5.39, CZT 4.85 -> 4.74, and run times. Full test suite 1450 passed, 69 skipped, 0 failed |
