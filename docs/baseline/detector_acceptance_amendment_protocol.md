# Detector acceptance test, amendment 1: peak widths by log-parabolic interpolation (pre-registered)

Written 2026-10-27, after the first run of `detector_acceptance_protocol.md` (`after_DA1`, commit
ba60fa7: 5 PASS / 2 FAIL) and **before** the change below. The limits of the first protocol are
kept unchanged; this amendment only changes how the widths are measured.

## What the first run showed

DA.C1 and DA.C2 failed in one case only: FWHM 1.8 keV at 0.5 keV per channel (3.6 channels). The
FWTM came out 5.7 % above the true Gaussian value, noiseless and with Poisson noise alike. The FWHM
deviation was 1.9 %. Every other case was within 2.3 %, and within 1.4 % at 0.25 keV per channel. The
cause is the method, not the code. Near a tenth of the maximum a Gaussian is strongly curved, and a
straight line between two channels 1/3.6 FWHM apart crosses the level too far out. The other part,
about +1.8 % on both widths at 3.6 channels, comes from counting each channel's integral rather than
its centre value (variance sigma^2 + 1/12 channel^2). Every method that works on channel contents
has it.

## Change

`detector_test.peak_width` finds each crossing of the half and tenth maximum on the net counts of the
ROI (the same background and maximum as the Aptec ROI analysis) by a parabola through the
logarithms of three channels: the first channel below the level going outward, the channel above it,
and the next channel inward. For a Gaussian sampled at channel centres this gives the exact
crossing. The linear interpolation of the Aptec ROI analysis is used when one of the three net
values is not positive, or when the parabola has no root between the two bracketing channels. The
Aptec ROI analysis itself (Analyze > ROI, the ROI table) is not changed.

## Criteria

DA.C1 to DA.C8 of `detector_acceptance_protocol.md` with the same limits, run again by the same
harness. Also reported: the number of crossings where the linear interpolation was used.

## Outputs

`docs/baseline/after_DA2/detector_acceptance.md` and `.json`; `after_DA2/baseline.md` and `.json`.

---

## Results (`after_DA2`)

**7 PASS / 0 FAIL** for DA.C1 to DA.C7, and DA.C8 PASS.

| ID | value |
|---|---|
| DA.C1 | largest deviation FWHM 1.80 %, FWTM 1.78 % (0.5 keV/channel, FWHM 1.8 keV; first run 5.7 %) |
| DA.C2 | largest mean deviation FWHM 1.74 %, FWTM 1.75 % |
| DA.C3 | largest deviation 0.000 % |
| DA.C4 | mean z -0.038, fraction \|z\| <= 2 0.950 (200) |
| DA.C5 | engine equals the hand value (214.421) |
| DA.C6 | 10 counts 3.325 / 16.919, 20 counts 10.117 / 30.144 |
| DA.C7 | Poisson accepted 0.898, extra scatter rejected 0.995 |
| DA.C8 | dialog tests pass (`tests/test_detector_acceptance.py`); full suite 1479 passed, 69 skipped, 1 failed on the first run: the dialogs' attribute `result` hid `QDialog.result()` (`tests/test_widget_attribute_shadowing.py`); renamed `outcome`, that test and the dialog tests then passed (1480 passed in all); benchmark 154 PASS / 13 FAIL / 60 REPORT, no criterion changed state against `after_R4H` |

The linear interpolation was not used for any crossing (0 in every case). The remaining deviation at
3.6 channels per FWHM (+1.8 %) is the channel-integral part named above; at 0.25 keV per channel
(7.2 and 8.8 channels) the deviations are below 0.5 %.

Reported, not judged (synthetic HPGe Co-60 with a low-energy tail): FWHM 1.795 keV (model 1.770 keV),
FWTM 3.279 keV, FWTM/FWHM 1.827, P/C 1527.

Added after the criteria were judged, outside this protocol (no change to the engine or the results
above): the source activity can be entered in Bq, kBq, MBq, GBq, TBq, Ci, mCi, µCi, nCi or pCi in the
acceptance dialog, the efficiency certificate table and the QC reference activity
(`gui/activity_input.py`, factors of `analysis/decay_calc.py`; `tests/test_activity_units.py`).
