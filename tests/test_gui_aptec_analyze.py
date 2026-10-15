"""Aptec-style Analyze menu: Setup, Peak Search (P), Identify (I), Background Subtract (B),
Quantify (Q) in the main window (headless)."""
from __future__ import annotations

import math
import os
from datetime import datetime

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import numpy as np
import pytest

pytest.importorskip("PySide6")

from PySide6.QtCore import QSettings, Qt
from PySide6.QtGui import QKeySequence
from PySide6.QtWidgets import QApplication

from spectramaster.gui import i18n
from spectramaster.gui.roi_panel import COLS
from spectramaster.model import Spectrum


@pytest.fixture(scope="module")
def qapp():
    from spectramaster.gui.app import create_app
    return create_app(["test"])


@pytest.fixture()
def window(qapp, tmp_path):
    from spectramaster.gui.app import MainWindow
    from spectramaster.gui.settings import Settings
    i18n.set_language("en")
    w = MainWindow(Settings(QSettings(str(tmp_path / "s.ini"), QSettings.IniFormat)))
    w.errors = []
    w.show_error = w.errors.append
    w.show_info = w.errors.append
    ctl = w.aptec_analysis
    ctl.messages = []
    ctl.message = ctl.messages.append
    yield w
    w.close()
    w.deleteLater()
    QApplication.processEvents()
    i18n.set_language("en")


def _spectrum(scale=1.0, live=1000.0, seed=3):
    rng = np.random.default_rng(seed)
    n = 4096
    x = np.arange(n)
    mu = 20.0 + 200.0 * np.exp(-x / 800.0)
    for kev, area, s in ((661.66, 20000.0, 3.0), (1460.82, 6000.0, 4.0)):
        mu = mu + scale * area / (s * math.sqrt(2 * math.pi)) * np.exp(-0.5 * ((x - kev / 0.5) / s) ** 2)
    return Spectrum(counts=[float(v) for v in rng.poisson(mu)], energy_coeffs=[0.0, 0.5], live_time=live,
                    real_time=live * 1.01, start_time=datetime(2024, 5, 1, 9), sample_id="S1",
                    extra={"quantity": 0.5, "quantity_units": "kg"})


def _show(window, spec=None):
    window.display([spec or _spectrum()], None, None)
    window.plot.resize(1000, 400)
    return window.plot


def test_menu_order_and_keys(window):
    acts = window.menu_analyze.actions()
    assert acts[0].menu() is window.menu_a_setup
    assert acts[1] is window.act_analyze and acts[2:5] == [window.act_a_ident, window.act_a_bkg, window.act_a_quant]
    setup = window.menu_a_setup.actions()
    assert setup[0] is window.act_roi_props and setup[1:5] == [window.act_a_setup_peak, window.act_a_setup_ident,
                                                                window.act_a_setup_bkg, window.act_a_setup_quant]
    for a, k in ((window.act_analyze, "P"), (window.act_a_ident, "I"), (window.act_a_bkg, "B"),
                 (window.act_a_quant, "Q"), (window.act_a_setup_peak, "Shift+P"), (window.act_a_setup_ident, "Shift+I"),
                 (window.act_a_setup_bkg, "Shift+B"), (window.act_a_setup_quant, "Shift+Q")):
        assert a.shortcut() == QKeySequence(k)
    assert window.act_analyze.text().replace("&", "") == "Peak Search"
    assert window._aana_engine["aptec"].isChecked()


def test_peak_identify_quantify(window):
    plot = _show(window)
    ctl = window.aptec_analysis
    window.act_analyze.trigger()
    cen = sorted(r.stats.centroid_energy for r in plot.rois)
    assert any(abs(c - 661.66) < 1 for c in cen) and any(abs(c - 1460.8) < 1.5 for c in cen)
    assert not window.roi_dock.isHidden()
    assert ctl.run_identify()
    ids = {r.aptec_id.line.isotope for r in plot.rois if getattr(r, "aptec_id", None)}
    assert {"Cs-137", "K-40"} <= ids
    cs = next(r for r in plot.rois if getattr(r, "aptec_id", None) and r.aptec_id.line.isotope == "Cs-137")
    row = plot.rois.index(cs)
    assert window.roi_panel.table.item(row, COLS.index("aana_col_iso")).text() == "Cs-137"
    ctl.efficiency_at = lambda spec: (lambda e: (0.02, 2.0))
    ctl.quant.activity_units = "Bq"
    assert ctl.run_quant()
    q = cs.aptec_q
    y = cs.aptec_id.line.yield_
    assert q.activity == pytest.approx(cs.stats.count_rate / (0.02 * y) / 0.5, rel=1e-9)
    assert ctl.units_label() == "Bq/kg"
    assert window.roi_panel.table.item(row, COLS.index("aana_col_act")).text() != ""


def test_background_subtract(window, tmp_path):
    from spectramaster.convert import write_spectrum
    from spectramaster.formats import get_format
    plot = _show(window)
    ctl = window.aptec_analysis
    bkg = tmp_path / "bkg.spe"
    write_spectrum(_spectrum(scale=0.2, seed=9), bkg, get_format("spe"))
    ctl.run_peak()
    assert ctl.run_bkg() is False                       # no identification yet
    ctl.run_identify()
    assert ctl.run_bkg() is False                       # no background file chosen
    ctl.bkg_file = str(bkg)
    assert ctl.run_bkg()
    cs = next(r for r in plot.rois if getattr(r, "aptec_id", None) and r.aptec_id.line.isotope == "Cs-137")
    assert cs.aptec_bkg is not None and cs.aptec_bkg[0] > 0
    ctl.efficiency_at = lambda spec: (lambda e: (0.02, 0.0))
    ctl.run_quant()
    assert "b" in cs.aptec_q.flags
    net = cs.stats.count_rate - cs.aptec_bkg[0]
    assert cs.aptec_q.activity == pytest.approx(net / (0.02 * cs.aptec_id.line.yield_) / 0.5, rel=1e-9)


def test_quantify_needs_efficiency_and_ident(window):
    _show(window)
    ctl = window.aptec_analysis
    assert ctl.run_quant() is False
    ctl.run_peak()
    ctl.run_identify()
    assert ctl.run_quant() is False and ctl.messages          # no efficiency calibration


def test_engine_spectramaster_runs_existing_analysis(window):
    _show(window)
    called = []
    window.run_analysis = lambda silent=False: called.append(1) or True
    window._aana_engine["spectramaster"].trigger()
    assert window.aptec_analysis.engine == "spectramaster"
    assert not window.act_a_ident.isVisible()
    window.act_analyze.trigger()
    assert called == [1]
    assert window.settings.get("aptec/analyze/engine") == "spectramaster"


def test_defaults_save_recall_factory(window):
    ctl = window.aptec_analysis
    ctl.peak.max_error = 12.5
    assert ctl.defaults("save")
    ctl.peak.max_error = 50.0
    assert ctl.defaults("recall") and ctl.peak.max_error == 12.5
    assert ctl.defaults("factory") and ctl.peak.max_error == 30.0


@pytest.mark.parametrize("lang", ["en", "ar"])
def test_dialogs_build(window, lang):
    from spectramaster.gui import aptec_analyze_ui as u
    from spectramaster.analysis import aptec_analyze as aa
    window.apply_language(lang, save=False)
    d1 = u.PeakSearchDialog(aa.PeakSearchSetup(max_error=25, partial=True, start=10, stop=900), 4096, window, window)
    assert d1.setup().max_error == 25 and d1.setup().partial and d1.start.isEnabled()
    d2 = u.IdentifyDialog(aa.IdentifySetup(fraction_limit=55))
    assert d2.setup().fraction_limit == 55 and d2.setup().library == ""
    d2.add_library(r"C:\x\isotope.lib")
    assert d2.setup().library.endswith("isotope.lib")
    d3 = u.QuantifyDialog(aa.QuantifySetup("pCi", use_quantity=True, use_total_quantity=True))
    assert d3.setup().activity_units == "pCi" and d3.setup().use_total_quantity
    d4 = u.BackgroundDialog("b.spe")
    assert d4.path.text() == "b.spe"
    for d in (d1, d2, d3, d4, u.DefaultsDialog()):
        assert d.layoutDirection() == (Qt.RightToLeft if lang == "ar" else Qt.LeftToRight)
        d.deleteLater()
    if lang == "ar":
        assert window.act_a_ident.text().replace("&", "") == "التعرّف على القمم"
