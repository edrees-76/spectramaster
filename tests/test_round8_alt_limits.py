"""Round-8 review, Codex H1 / Gemini H1: a nuclide whose primary result comes from another line than
its key line reports that line's limits; a "curved" primary result is marked like an interfered one
(docs/baseline/round8_alt_limits_protocol.md)."""
from __future__ import annotations

import pytest

from spectramaster.analysis import activity as act
from spectramaster.validation import round8_alt_limits as r8


@pytest.mark.parametrize("method", ["key", "mean"])
@pytest.mark.parametrize("mda_method", ["currie", "iso11929"])
def test_substituted_line_gives_the_limits(method, mda_method):
    c = r8._case(r8.HPGE, ("peak", 1176.5), 0, method, mda_method)
    nr, key, alt = c["nuclide"], r8._key(c), r8._alt(c)
    assert key["primary_method"] == "interfered" and alt is not key
    assert (nr["decision_threshold"], nr["mda"]) == (alt["decision_threshold"], alt["mda"])
    assert nr["mda"] < key["mda"] and nr["primary"] == alt["primary"]
    assert nr["specific_mda"] == pytest.approx(alt["mda"] / r8.QUANTITY, rel=1e-12)
    assert f"limits from the {alt['energy']:.1f} keV line" in nr["note"]


def test_usable_key_line_keeps_its_limits():
    c = r8._case(r8.HPGE, ("peak", 1180.0), 0, "key", "currie")
    nr, key = c["nuclide"], r8._key(c)
    assert key["primary_method"] == "window"
    assert (nr["decision_threshold"], nr["mda"]) == (key["decision_threshold"], key["mda"])
    assert "limits from" not in nr["note"]


@pytest.mark.parametrize("lang", ["en", "ar"])
def test_curved_primary_result_is_marked(lang):
    pytest.importorskip("PySide6")
    from spectramaster.gui import i18n, quant_panel

    def tr(k, **kw):
        return i18n.tr_in(lang, "quant_" + k, **kw)
    r = act.NuclideResult(nuclide="Co-60", primary=-1.5, primary_u=0.7)
    texts = {}
    for m in ("window", "interfered", "curved"):
        r.primary_method = m
        texts[m] = quant_panel._primary_text(r, tr)
    assert tr("res_interfered") in texts["interfered"]
    assert tr("res_curved") in texts["curved"] and tr("res_interfered") not in texts["curved"]
    assert tr("res_curved") != "res_curved" and tr("res_curved") not in texts["window"]
