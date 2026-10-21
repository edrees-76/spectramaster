# True-coincidence summing: daughters, unestimable partners, calibration refit (pre-registered)

Written 2026-10-21, **before** the implementation. The rules and limits below must not be changed after
results are known. A result outside a limit is reported as a failure.

## Motivation (third external review, verified on `4fb5b2a`)

1. **Daughter cascades (Gemini H5).** The gamma library folds short-lived daughters into their parent
   (`includes`, `include_factors` of `gamma_library.json`: Bi-207 -> Pb-207m 0.840, Ti-44 -> Sc-44,
   Ba-140 -> La-140, Ce-144 -> Pr-144, Te-132 -> I-132, Am-243 -> Np-239 ...). The coincidence
   table keeps those daughters as separate nuclides, and `coincidence.coi` looks only at the parent.
   Checked: Bi-207 569.7 keV is refused (16 % in the table, 97.75 % in the library: only the 1770 keV
   branch is a Bi-207 cascade) and Bi-207 1063.7 keV is not corrected at all, without a note.
   Bi-207 is a common calibration source.
2. **Partners below the efficiency curve (Gemini H5).** Partners below 0.8 x e_min get eps = 0 and
   are only reported. Checked: Ba-133 with a curve from 122 keV ignores the 81 keV partner; COI(356)
   = 1.000 (37 % of the coincidences ignored) instead of 0.952 with a curve from 50 keV; 302.9 keV:
   1.000 instead of 0.921. The result is reported as corrected.
3. **Calibration points the correction cannot treat (Gemini H5).** `summing_free_curve` skips a
   cascade point when `coi` does not describe it, still marks the curve summing-corrected, and with
   no factor != 1 writes "points () corrected ... (lowest COI 1.0000)".
4. **Convergence (Codex H4).** `summing_free_curve` stops after 3 fixed-point iterations without a
   check. Codex: Co-60, true efficiency 0.11, PT 0.24: corrected efficiency 0.0947, activity +3.9 %.
5. **Curves without points (Codex H5).** A curve with no calibration points (an imported Aptec
   `lnpoly` curve) is returned unchanged before the check that refuses non-refittable models. Whether
   its efficiencies include summing losses is unknown; the sample is corrected again. Codex: +8.3 %.

## Change

- **R1.** `coincidence.coi` and `has_cascades` also use the transitions of the daughters the bundled
  library folds into the nuclide, each daughter transition weighted by its `include_factor` (its
  branching x equilibrium activity ratio, from the library build). Gammas of the parent's decay and
  of the daughter's decay are not coincident (different decays). The library is the bundled one, as
  for the table.
- **R2.** When the partners left out (eps = 0, below 0.8 x e_min) carry `ignored` >= IGNORED_MAX =
  0.05 of the line's coincidences, the correction cannot be estimated: `coi` returns a reason, and the
  activity line gets **no result** with that reason (as for COI <= 0), instead of an uncorrected
  value presented as corrected. Below 0.05 the existing note stays.
- **R3.** `summing_free_curve` refuses (ValueError naming the points) a used cascade calibration point
  whose line the correction cannot treat (a reason from `coi`, or COI outside its validity). The note
  lists the corrected points; when no factor differs from 1 it says so (no empty parentheses).
- **R4.** `summing_free_curve` iterates until the corrected efficiencies of the cascade points change
  by less than 1e-7 (relative) between two iterations, at most 200 iterations; otherwise it refuses
  (not converged). The number of iterations is recorded in the note.
- **R5.** A curve that is not marked summing-corrected and has no used calibration points is refused
  with TCS on, unless the user declares it free of summing (`tcs["curve_summing_free"] = True`, CLI
  `--tcs-curve-summing-free`); the declaration is written in the notes.

## Criteria

All with the mid geometry of the TCS benchmark (`tcs_mc.eps_peak(e, 0.02)`, `tcs_mc.peak_to_total`)
unless stated.

| id | criterion | limit |
|---|---|---|
| TF.C1 | Bi-207, e_min 59.5 keV, library intensities | 569.7 and 1063.7 keV corrected (found); COI(569.7) equals the branch-weighted value computed by hand from the table's Bi-207 and Pb-207m data (difference < 1e-9); 1770.2 keV unchanged (< 1e-12) |
| TF.C2 | every library line of every nuclide with no daughter in the table | COI, found and reason identical to the previous code |
| TF.C3 | Ba-133, curve from 122 keV | lines with ignored >= 0.05 give no result with a reason; with a curve from 50 keV results identical to the previous code |
| TF.C4 | calibration with a Bi-207 point / with a point the correction cannot treat | Bi-207 569.7 keV point corrected; the other refused with its name; no note contains "()" |
| TF.C5 | Codex H4 case: Co-60 points with apparent efficiencies made with the first-order COI from a true curve (0.11 at 1173-1332 keV), PT 0.24 | corrected Co-60 efficiencies within 1e-4 (relative) of the true ones; the activity of a Co-60 sample within 0.1 % of the truth |
| TF.C6 | a fixed-point case that does not converge | ValueError, nothing returned as corrected |
| TF.C7 | Codex H5 case: lnpoly curve without points, TCS on | ValueError; with `curve_summing_free` the calculation runs and the notes record the declaration |
| TF.C8 | benchmark `after_TF1` vs `after_MF1` | no PASS -> FAIL |

The TCS benchmark uses Co-60, Cs-134, Y-88 ... without e_min or intensity, none with daughters in the
table, so it is not expected to change. Every value that changes will be listed.

**Engine version.** Activity results change (R1, R2, R5) and curves refitted for summing change (R3,
R4): `ENGINE_VERSION` goes from 1.3.0 to 1.4.0.

Results: appended below; `after_TF1` (the name was checked to be free).

## Results (2026-10-21)

The protocol's SHA-256 was recorded before the implementation (`0da669e8...35ef68`); the sections above
are unchanged. Tests: `tests/test_tcs_fixes.py`. All seven fail on the previous code and pass now.

| id | result | status |
|---|---|---|
| TF.C1 | Bi-207, mid geometry: COI(569.7) 0.9359 and COI(1063.7) 0.9078 (before: refused, and 1.0 without a note), equal to the hand calculation from the raw table records (< 1e-9); 1770.2 keV unchanged | PASS |
| TF.C2 | 3770 line evaluations (every library gamma of the nuclides without a daughter in the table, without and with e_min 59.5 keV): COI, found and reason identical | PASS |
| TF.C3 | R2 withdrawn (below) | NOT EVALUATED |
| TF.C4 | Bi-207 569.7 and 1063.7 keV calibration points corrected; an Ir-192 484.6 keV point refused with its name; the note of a curve with no factor != 1 says so, no "()" | PASS |
| TF.C5 | Codex H4 case: corrected Co-60 efficiencies equal the true ones (relative difference < 1e-7, 21 refits; before: -2.3 % and -2.6 % after 3); Co-60 activity within 0.1 % | PASS |
| TF.C6 | true efficiency 0.15 with PT 0.24 (eps_t 0.63): "did not converge in 200 refits", nothing returned | PASS |
| TF.C7 | lnpoly curve without points: refused; with `curve_summing_free` the calculation runs and the note records the declaration | PASS |
| TF.C8 | `after_TF1` vs `after_MF1`: 154 PASS / 13 FAIL / 60 REPORT, no PASS -> FAIL; only the engine version and the runtimes differ | PASS |

**R2 withdrawn.** Applying R2 as registered showed consequences the protocol had not considered. The
rule refuses a line when partners below 0.8 x e_min carry 5 % or more of its coincidences, without
regard to whether those partners can reach the detector at all:

- U-235 185.7 keV: its 19.6 keV partner carries 79 % of the coincidences. With any calibration starting
  above 24.5 keV the line would get no result with summing correction on.
- Co-57 122.1 keV: its 14.4 keV partner carries 10 %. Every calibration containing a Co-57 point and
  starting above 18 keV would be refused with summing correction on (three existing tests failed).

The 14.4 and 19.6 keV photons are almost entirely absorbed by the detector entrance window and the
sample, so leaving them out (eps = 0) is physically right there. The 81 keV partner of Ba-133 is not
absorbed, and the rule was meant for that case. The rule cannot tell the two cases apart, so it was
withdrawn rather than changed after seeing the results. The Ba-133 defect stays open (the existing note
reports the share of coincidences left out). It goes to a separate pre-registered protocol in which the
user states the detector's low-energy threshold: partners below it get eps = 0 as known; partners
between it and the calibration's lower end cannot be estimated.

**Other changes found by TF.C2's comparison** (nuclides with daughters, e_min 59.5 keV, 219 line
evaluations changed). Most are lines now corrected that were silently left at COI 1 (Bi-207, Ti-44,
Te-132/I-132, Ba-140/La-140, Kr-88/Rb-88, Am-243/Np-239 ...). Three lines were "corrected" before and
are now refused with a reason: Hf-181 133.0 and 482.2 keV, and Sb-125 35.5 keV. For these the table
lists the same gammas under the parent and the isomeric daughter, so with the daughter added the table
intensity is about twice the library's. Before, they were given COI 1.0 although 133 and 482 keV are in
cascade through the Ta-181 isomer. They are still not corrected, but now the note says so. Removing the
duplication is left for a later change of the table.

**Engine version** 1.3.0 -> 1.4.0.
