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
