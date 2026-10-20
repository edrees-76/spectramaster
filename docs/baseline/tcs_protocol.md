# True-coincidence summing correction: evaluation protocol (pre-registered)

Written 2026-10-20, **before** the implementation of the correction and before any result. The
limits below must not be changed after results are known. A result outside a limit is reported as
a failure.

## Change

`ActivityOptions.tcs = {"peak_to_total": [a, b], "pt_rel_unc": u}`. The coincidence summing
correction (COI) of each line i of a cascade emitter uses:

- the bundled gamma-gamma coincidence table (`analysis/coincidence.py`, SandiaDecay);
- the peak efficiency of the curve, eps_p(E);
- the total efficiency eps_t(E) = eps_p(E) / PT(E), with a peak-to-total model
  PT(E) = min(1, a (E / 1000 keV)^b) supplied by the user. It is an assumption of the
  measurement and is reported as such.

First order, per decay transition:

```
COI_i = 1 - sum_j P(j | i) eps_t(E_j)                                  summing-out
          + sum_(a,b) I_a P(b | a) eps_p(E_a) eps_p(E_b) / I_i               summing-in
```

- The summing-in pairs are a above b with |E_a + E_b - E_i| <= 1 keV.
- A line emitted by several transitions takes their emission-weighted mean.
- The activity, threshold and MDA of the line are divided by COI_i.
- u_rel(COI_i) comes from the P/T uncertainty, |COI_i - 1| u_PT (first order). It is a line
  component of the budget ("coincidence summing").
- Lines of nuclides without cascades get COI = 1. The "not corrected" note is replaced by the COI
  and its assumptions.

Known limits of the method:

- Gamma-gamma only: no X-ray and no 511 keV coincidences.
- No angular correlation.
- First order: with several coincident gammas and large eps_t, the joint probabilities that the
  pairwise table lacks are neglected. The criteria below are graded by geometry because of this.

## Benchmark (new category `tcs`)

This is an independent event-by-event simulation (`validation/tcs_mc.py`). It is not the formula
above and does not use the coincidence table:

- **Level schemes.** Hand-coded from ENSDF level energies, with the gamma intensities of the
  bundled library (IAEA ENSDF):
  - Co-60 -> Ni-60: levels 0, 1332.5, 2505.8 keV.
  - Cs-134 -> Ba-134: levels 0, 604.7, 1168.0, 1400.6, 1643.3, 1969.9 keV.
  - Y-88 -> Sr-88: levels 0, 1836.1, 2734.1, 3584.8 keV.
- **Feeding.** The beta / EC feeding of each level is the intensity balance (out - in, >= 0),
  normalised. A level decays by its gammas in proportion to their intensities.
- **Detection.** Each photon independently gives a full-energy deposit (probability eps_p), a
  partial deposit (eps_t - eps_p) or nothing.
- **Counting.** An event counts in the peak of line i when it has no partial deposit and the sum
  of its full-energy deposits is within 0.5 keV of E_i. COI_MC = counts / (N I_i eps_p(E_i)),
  where I_i is the emission probability implied by the scheme.
- **Efficiencies.** eps_p(E) = e1000 (E / 1000)^-0.85 and PT(E) = min(1, 0.24 (E / 1000)^-0.63).
  These are the same inputs for the MC and the correction.
- **Geometries.** e1000 = 0.005 (far), 0.02 (Marinelli-like) and 0.05 (close point source).
- **Decays.** N = 2e7 per nuclide and geometry, with seeds `seed_of(det, "tcs/<nuclide>/<e1000>", 0)`.
  The detector is irrelevant; it is run once, under HPGe.
- **Lines.** All library lines with I >= 0.5 %: Co-60 1173, 1332; Cs-134 475, 563, 569, 605,
  796, 802, 1039, 1168, 1365; Y-88 898, 1836, 2734.

d_i = COI_formula / COI_MC - 1, and sigma_i is its MC standard deviation (binomial counts).

| id | metric | limit | rationale |
|---|---|---|---|
| tcs.far_max | max_i (\|d_i\| - 3 sigma_i), e1000 = 0.005 | <= 0.005 | first order is near exact far from the detector |
| tcs.mid_max | same, e1000 = 0.02 | <= 0.01 | Marinelli-like geometry: 1 % beyond MC noise |
| tcs.close_max | same, e1000 = 0.05 | report | first order expected to degrade (joint probabilities) |
| tcs.mid_uncorrected | max_i \|COI_MC - 1\|, e1000 = 0.02 | report | size of the effect without correction |
| tcs.mid_co60 | \|d\| of Co-60 1173 and 1332, e1000 = 0.02 | <= 0.005 | single coincidence: exact to first order |
| tcs.sum_in | \|d\| of Cs-134 1168 and 1365 (summing-in lines), e1000 = 0.02 | <= 0.02 + 3 sigma | crossover lines |

All existing pre-registered criteria apply unchanged. No PASS -> FAIL is allowed.

Amendment, before any result of the correction formula: N was raised from 4e6 to 2e7. A sanity
run of the MC alone took about 1 s per 1e6 decays, and the weak Cs-134 lines had MC sigma of
about 3 % at 4e6. No limit was changed.

Second amendment, after a 2e5-decay smoke run of the category code and before the full run. The
line list above had omitted Y-88 2734 keV (I = 0.71 %), which the rule (I >= 0.5 %) includes. The
list was corrected to follow the rule; no limit was changed.

Before: `docs/baseline/after_HW1`. After: `docs/baseline/after_TC1`. The name was checked to be
free.

## Results (after_TC1, 2026-10-20)

| id | value | limit | status |
|---|---|---|---|
| tcs.far_max | -0.0041 | <= 0.005 | PASS |
| tcs.mid_max | +0.0017 | <= 0.01 | PASS |
| tcs.close_max | +0.124 | report | |
| tcs.mid_uncorrected | 4.16 (Y-88 2734 keV, COI_MC = 5.16) | report | |
| tcs.mid_co60 | 0.0023 | <= 0.005 | PASS |
| tcs.sum_in | -0.0020 | <= 0.02 + 3 sigma | PASS |

Marinelli-like geometry (e1000 = 0.02), formula / MC:

- Co-60 1173: 0.9218 / 0.9227. Co-60 1332: 0.9196 / 0.9175.
- Cs-134 605: 0.8899 / 0.8909. Cs-134 796: 0.8905 / 0.8947.
- Cs-134 563: 0.8188 / 0.8280. Cs-134 569: 0.8201 / 0.8302. Cs-134 802: 0.8323 / 0.8404.
- Cs-134 1168: 1.175 / 1.185. Cs-134 1365: 1.286 / 1.254.
- Y-88 898: 0.9276 / 0.9294. Y-88 1836: 0.9200 / 0.9242. Y-88 2734: 5.00 / 5.16.

The Cs-134 lines fed from the 1970 keV level (563, 569, 802) are about 1 % low. These lines have
several strongly correlated coincidences, and first order counts their joint non-detection twice.

Close geometry (0.05):

- Co-60 and Y-88 stay within 0.3 %.
- The Cs-134 multi-coincidence lines are 7-9 % low.
- The summing-in lines are 12-14 % high.

That is the documented limit of the pairwise (first-order) data.

All other criteria are unchanged from `after_HW1`, with no PASS -> FAIL; 19 criteria fail, the
same as before.
