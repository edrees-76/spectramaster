"""Round-6 review, Gemini M3: channel binning bias of the acceptance test widths, noted not corrected
(round6_fwhm_protocol.md)."""
import math

from spectramaster.analysis import detector_test as dt
from spectramaster.validation import round6_fwhm as r6


def test_range_contains_the_measured_bias():
    for fw, f in ((3.0, 0.5), (4.0, 0.0), (4.0, 0.25), (6.0, 0.5)):
        w = dt.peak_width(r6.build(fw, f))
        lo, hi = w.fwhm_bin_bias
        bias = w.fwhm_kev / (fw * r6.KEV_PER_CH) - 1.0
        assert lo - 5e-4 <= bias <= hi + 5e-4
        assert "channel binning" in w.note and "not corrected" in w.note


def test_wide_peak_has_no_note_and_values_unchanged():
    w = dt.peak_width(r6.build(12.0, 0.0))
    assert "binning" not in w.note and max(w.fwhm_bin_bias) < dt.BIN_NOTE_BIAS
    assert math.isclose(dt.peak_width(r6.r5.build([0.0, 0.5])).fwhm_kev, r6.r5.BEFORE["linear"][1],
                        rel_tol=0, abs_tol=0)


def test_binning_bias_is_the_fixed_point_of_the_binned_width():
    for level in (0.5, 0.1):
        r = math.sqrt(math.log(1 / level) / math.log(2))
        for frac, b in zip((0.0, 0.5), dt.binning_bias(4.0 * r, level)):
            assert math.isclose(dt._binned_width(4.0 / (1 + b), frac, level), 4.0 * r, rel_tol=1e-9)
