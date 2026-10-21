# Gamma-line library: wrong, duplicated and lost lines (pre-registered)

Written 2026-10-21, **before** any change to `build_library.py` and before any benchmark run of it.
The rules and limits below must not be changed after results are known. A result outside a limit is
reported as a failure.

## Motivation

The certified-reference-material check (`crm_validation_protocol.md`, defect D1) found that the
library gives Ac-228 674.75 keV an emission probability of 2.1 %. SandiaDecay gives 0.109 % and
LNHB/DDEP 0.105 %, and the measured RGTh-1 spectra agree with the small value. The existing
`ddep_check` did not see it: it compares a library line only with a DDEP line within 0.1 keV, and
the DDEP line is at 674.63 keV.

A wider diagnosis (2026-10-21, before this protocol) found two more defects in `build_library.py`.
The library is rebuilt from the sources in the repository, and an unchanged rebuild reproduces
`gamma_library.json` byte for byte (SHA-256 `8a1d05ef...816387`).

**Duplicated lines.** A Sandia line is kept as "Sandia only" when it is not paired with an IAEA
line. Pairing requires the same kind (gamma / X-ray) and 0.3 keV for gammas. The same transition is
therefore listed twice, and its intensity counted twice, when:

- the two evaluations' energies differ by more than 0.3 keV, for example Sb-124 1325.0 and
  1325.504 keV, Pa-234 1393.57 and 1393.9 keV (DDEP lists one line), Sb-126 278.6 and 278.2 keV,
  Hf-175 432.7 and 433.0 keV, Ba-140 / La-140 951.4 and 950.987 keV;
- Sandia lists an X-ray as a gamma, for example Ta-182 69.34 keV (DDEP: the W K'beta2 X-ray at
  69.27 keV only), Np-237 94.66, 98.44 and 111.3 keV (9.6, 17.4 and 5.9 %; DDEP has a 0.66 % gamma
  at 94.64 keV);
- Sandia lists the same transition under a daughter isomer. Hf-181 482.0 keV (Ta-181m, 99.3 %)
  comes on top of 482.18 keV (80.5 %), so the library holds about 180 % at 482 keV.

**Lost IAEA lines.** IAEA lines of a daughter are added only when "the parent does not list a line
within 0.5 keV". The code compares with every line added before, including the daughter's own
lines, so a daughter line within 0.5 keV of another line of the same daughter is dropped. Eight
lines of 0.05 % or more are lost this way:

- Np-239 228.183 keV (10.73 %, in Am-243);
- I-132 727.0, 621.2 and 29.78 keV (in Te-132);
- La-140 34.72 keV (in Ba-140);
- Cu-62 7.46 keV, Ga-68 8.64 keV and Rb-82 12.65 keV.

Most of them are replaced by the Sandia value of the same line.

## Change

- **R1, lost lines.** A daughter's IAEA line is compared only with the lines of the members before
  it (the parent and earlier daughters), not with its own lines.
- **R2, duplicates.** For an entry with IAEA data, a Sandia line that is not paired with an IAEA
  line is dropped when an IAEA line of the entry, gamma or X-ray, lies within 1.0 keV with an
  intensity between 0.5 and 2 times its own. Then it is the same transition. A Sandia line with no
  such IAEA neighbour is kept as before. The dropped lines are counted in the build output.
- **R3, a correction table** in `build_library.py`, for IAEA values contradicted by two
  independent sources. A line enters the table only when:
  - the IAEA intensity differs by more than a factor 2 from SandiaDecay and from DDEP;
  - SandiaDecay and DDEP agree within 20 %.

  Only one line meets this: Ac-228 674.75 keV, which becomes 0.105 % +- 0.010 % (DDEP/LNHB Ac-228
  LARA file). The energy is kept. The entry's provenance records the old value and the source.
- **R4, the DDEP check.** `ddep_check` reports two new lists:
  - Gross differences: each library gamma of 1 % or more, of an entry with a LARA file and no
    included daughters, is matched to the nearest DDEP gamma within 0.5 keV. It is listed when the
    intensity ratio is outside [0.67, 1.5] and, where both uncertainties exist, |z| > 3.
  - Unmatched lines: those with no DDEP gamma or X-ray within 0.5 keV.

The other IAEA/Sandia disagreements of a factor > 2 were checked before this protocol. The library
already uses the IAEA value, and that value is the plausible one: W-187 (Sandia about 3 times
higher on every line), Zr-97 (Sandia 193.5 % at 743 keV), Hf-181 133 keV, and Th-231 89.95 keV
(DDEP 1.01 %, as IAEA). These stay unchanged. Cs-138 1147 keV, Sb-126 297 keV and Lu-177m 71.6 keV
have no DDEP file and stay unchanged; they are listed as unverified.

## Criteria

| id | criterion | limit |
|---|---|---|
| LB.C1 | benchmark `after_LB1` vs `after_BP1` | no PASS -> FAIL |
| LB.C2 | `ddep_check` lines within 2 combined standard uncertainties | >= 94.8 % (now) |
| LB.C3 | `ddep_check` lines within 3 combined standard uncertainties | >= 97.2 % (now) |
| LB.C4 | R4 gross differences | none, except Yb-169 63.01 keV (below) |
| LB.C5 | R4 unmatched lines | only the four Sb-127 lines (below) |
| LB.C6 | library diff | every changed line explained by R1, R2 or R3 |
| LB.C7 | CRM calibration, Ac-228 674.75 keV point, cylinder and Marinelli | residual within +-30 % (now -97 % and -96 %) |

Stated in advance as unresolved and not changed:

- Yb-169 63.01 keV, 2.16 %. It is in IAEA, without an uncertainty, and is paired with a Sandia line.
  DDEP has only 63.12 keV (44 %).
- Sb-127 685.7, 698.5, 722.2 and 783.7 keV. The IAEA energies are 0.6-1.1 keV above DDEP's
  (685.09 keV ...), with the same intensities. This is an energy disagreement between evaluations.

**Reported, not criteria:**

- The full list of changed lines.
- The CRM criteria re-run (`crm_validation_protocol.md`, unchanged). The model error should drop
  sharply, since the Ac-228 point caused it. D2 itself is not fixed here.
- The test suite.

Before: `docs/baseline/after_BP1`. After: `docs/baseline/after_LB1`; the name was checked to be free.
The change touches only the library and its build and check scripts.

## Results (2026-10-21)

The protocol's SHA-256 was recorded before `build_library.py` was changed (`a6b6683a...6e5991`); the
sections above are unchanged. The library has 2719 lines (2743 before) and 229 provenance flags
(232). 42 duplicated Sandia lines were dropped. Line-by-line diff:
`after_LB1/library_diff.txt`.

| id | value | limit | status |
|---|---|---|---|
| LB.C1 | after_BP1 154 PASS / 13 FAIL / 60 REPORT -> after_LB1 154 / 13 / 60, no PASS -> FAIL | no PASS -> FAIL | PASS |
| LB.C2 | 94.8 % of 364 lines | >= 94.8 % | PASS |
| LB.C3 | 97.3 % | >= 97.2 % | PASS |
| LB.C4 | Yb-169 63.01 keV only | none except Yb-169 63.01 keV | PASS |
| LB.C5 | the four Sb-127 lines only (Sb-124 1325.0 keV, listed before, is gone) | only the Sb-127 lines | PASS |
| LB.C6 | every changed line is explained, see below | R1, R2 or R3 | PASS |
| LB.C7 | the point no longer exists | residual within +-30 % | **NOT EVALUABLE** |

**LB.C6.**

- R1 restored IAEA lines: Np-239 228.183 keV (replacing the Sandia 228.18 keV), Np-239 57.294 keV
  (merged with 57.3 keV), I-132 727.0 and 621.2 keV (IAEA instead of Sandia values), La-140
  34.72 keV and Rb-82 12.649 keV.
- R2 removed the duplicated Sandia lines.
- R3 corrected Ac-228 674.75 keV.
- Nine lines entered only because a removed line freed one of the 40 places per entry: Ac-228
  199.4, Co-56 1198.9, Eu-156 434.4, Kr-88 2186.5, Np-237 106.12, Pa-234 203.12 keV and Pd-112
  946.9, 1063.5 and 2051.5 keV. This is the existing cap, applied after R2/R3.
- One R2 decision is wrong: Pa-234 824.2 keV is a separate line (DDEP lists 824.2 keV 1.25 % and
  825.1 keV 1.9 %). It was outside the 40-line cap before and after, so only its provenance flag
  changes, from "Sandia only" to "same transition". The rule is not changed after the fact.

**LB.C7 cannot be evaluated as written.** At 0.105 %, Ac-228 674.75 keV falls below the 40-line cap
and is no longer in the library. Even if it stayed, the efficiency calibration uses lines of 2 % or
more, so it would no longer be a calibration point. The criterion assumed the point would remain. Its
aim, no wrong Ac-228 point in the calibration, is met.

**Effect on the CRM check** (re-run unchanged, `after_LB1/crm_validation_results.md`):

| | before | after |
|---|---|---|
| efficiency model error, cylinder | 58.5 % | 8.1 % |
| model error, Marinelli | 54.8 % | 10.0 % |
| CRM.C1 | 19/19 | 19/19 |
| CRM.C2 | 19/19 | 19/19 |
| CRM.C4 rms z | 0.158 | **0.945** |
| CRM.C3 Ra-228 / Cs-137 | 1.147 / 1.114 FAIL | unchanged FAIL |

The ratios do not change, because the curve does not change. The uncertainties are now realistic:
rms z is near 1, with every pair still within |z| <= 2.58. D2, the weak outlier handling of the
model error, is not fixed here. Another outlier would inflate the uncertainties in the same way.

**Benchmark values that changed (no status changed):**

| criterion | before | after |
|---|---|---|
| NaI.id.false_per_spectrum | 2.17 | 1.92 (still FAIL) |
| NaI.drift.corrected | 0.80 | 0.90 (still FAIL) |
| IDB.HPGe.implausible_per_spectrum | 8.08 | 8.19 (still FAIL) |
| NaI.id.recall_drift_0.3 | 0.88 | 0.90 |

Small changes also occurred in the NaI background and blank criteria, with every PASS kept.

**Weakness of R4, seen after the fact.** The gross list skips a line when |z| <= 3. Ac-228
674.75 keV has an ENSDF uncertainty of 0.7 %, which gives z = 2.85, so R4 would not have caught the
very error that motivated it. A ratio test alone (factor > 2) would have. This is noted for the next
change and not changed here.

Full test suite: 1227 passed, 68 skipped.

**Engine version.** `ENGINE_VERSION` goes from 1.1.0 to 1.2.0 in the same change. The library change
can alter results. PR #35 had already changed peak-mode results without a bump (Gemini, round 3,
L2). Sessions computed before this change are now reported as computed with an older engine.
`after_LB1/baseline.json` and the CRM re-run were generated just before the bump and record 1.1.0.
