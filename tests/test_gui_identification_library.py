"""GUI: identification library choice and the calibration-drift note (Release E, E5)."""
from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import time

import pytest

pytest.importorskip("PySide6")

from PySide6.QtCore import QSettings
from PySide6.QtWidgets import QApplication

from spectramaster.gui import i18n


@pytest.fixture(scope="module")
def qapp():
    from spectramaster.gui.app import create_app
    yield create_app(["test"])


@pytest.fixture()
def settings(tmp_path):
    from spectramaster.gui.settings import Settings
    return Settings(QSettings(str(tmp_path / "settings.ini"), QSettings.IniFormat))


@pytest.fixture(autouse=True)
def english():
    old = i18n.language()
    i18n.set_language("en")
    yield
    i18n.set_language(old)


def _wait(cond, timeout=20.0):
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        QApplication.processEvents()
        if cond():
            return True
        time.sleep(0.01)
    return cond()


def _spectrum():
    from spectramaster.validation.synthetic import HPGE, Continuum, TruePeak, make_spectrum
    return make_spectrum(HPGE, [TruePeak(661.657, 2e4)], Continuum(300, 400, 10), 3).spectrum


def _drift_spectrum():
    from spectramaster.validation.scenarios import identification
    from spectramaster.validation.synthetic import HPGE
    return next(sc for sc in identification(HPGE, 1) if sc.meta.get("drift") == 0.003).spectrum


def test_gui_default_is_environmental_and_choice_is_persisted(qapp, settings):
    from spectramaster.analysis.library import APPLICATIONS
    from spectramaster.gui.analysis_panel import AnalysisPanel
    from spectramaster.gui.identification_library import CHOICES, SETTINGS_KEY
    assert set(CHOICES) == set(APPLICATIONS)
    p = AnalysisPanel(settings=settings)
    assert p.application() == "environmental"
    assert "recommended" in p.library_combo.currentText()
    p.set_application("safeguards")
    assert settings.get(SETTINGS_KEY) == "safeguards"
    p2 = AnalysisPanel(settings=settings)
    assert p2.application() == "safeguards"
    settings.set(SETTINGS_KEY, "nonsense")
    assert AnalysisPanel(settings=settings).application() == "environmental"


def test_worker_passes_the_library_to_identify(qapp, monkeypatch):
    from spectramaster import analysis
    from spectramaster.gui.worker import AnalysisWorker
    seen = {}

    def fake_identify(spec, peaks, **kw):
        seen.update(kw)
        return []
    monkeypatch.setattr(analysis, "identify", fake_identify)
    w = AnalysisWorker(_spectrum(), 1, application="medical")
    got = []
    w.done.connect(lambda *a: got.append(a))
    w.run()
    assert got and seen["application"] == "medical"


def test_window_analysis_uses_the_chosen_library_and_shows_it(qapp, settings, monkeypatch):
    from spectramaster import analysis
    from spectramaster.analysis import NuclideMatch
    from spectramaster.gui import analysis_panel
    from spectramaster.gui.app import MainWindow
    seen = []

    def fake_identify(spec, peaks, **kw):
        seen.append(kw.get("application"))
        return [NuclideMatch("Cs-137", 0.9, [], [], "30.1 y", "fission", "")]
    monkeypatch.setattr(analysis, "identify", fake_identify)
    monkeypatch.setattr(analysis_panel, "engine_status", lambda: None)
    spec = _spectrum()
    w = MainWindow(settings)
    try:
        w.show_error = lambda *a: None
        w.show_info = lambda *a: None
        w.current_spectrum = lambda: spec
        w.refresh_analysis_available()
        panel = w.analysis_panel
        assert panel.application() == "environmental"          # GUI default
        assert w.run_analysis()
        assert _wait(lambda: not w.analysis_running() and panel.analysed)
        assert seen == ["environmental"]
        assert "Library: Environmental" in panel.summary.text()
        assert not panel.drift_label.isVisible() and panel.drift_label.text() == ""
        panel.set_application("calibration")
        assert "run the analysis again" in panel.summary.text()
        assert w.run_analysis()
        assert _wait(lambda: not w.analysis_running() and len(seen) == 2)
        _wait(lambda: "Calibration sources" in panel.summary.text(), 2)
        assert seen[-1] == "calibration" and "Library: Calibration sources" in panel.summary.text()
        assert settings.get("analysis/library") == "calibration"
    finally:
        w.close()
        w.deleteLater()
        QApplication.processEvents()
    w2 = MainWindow(settings)                                   # persisted across sessions
    try:
        assert w2.analysis_panel.application() == "calibration"
    finally:
        w2.close()
        w2.deleteLater()
        QApplication.processEvents()


def test_report_analysis_passes_the_library(monkeypatch):
    from spectramaster import analysis
    from spectramaster.gui import report as rp
    seen = []
    monkeypatch.setattr(analysis, "identify", lambda s, p, **kw: seen.append(kw.get("application")) or [])
    rp.analyse_spectrum(_spectrum(), application="safeguards")
    assert seen == ["safeguards"]


def test_drift_note_is_shown_above_the_nuclide_table(qapp):
    from spectramaster.gui.analysis_panel import AnalysisPanel, nuclide_row
    from spectramaster.gui.worker import AnalysisWorker
    spec = _drift_spectrum()
    w = AnalysisWorker(spec, 1, application="environmental")
    got = []
    w.done.connect(lambda *a: got.append(a))
    w.run()
    assert got
    _tok, peaks, matches, identified = got[0]
    assert any("calibration drift detected" in m.note for m in matches)
    p = AnalysisPanel()
    p.show()
    p.set_results(peaks, matches, identified, "environmental")
    assert not p.drift_label.isHidden()
    text = p.drift_label.text()
    assert text.startswith("⚠ Calibration drift detected") and "gain" in text and "0.30 %" in text
    assert "identification only" in text
    # shown once above the table, not repeated on every row
    assert all("calibration drift" not in nuclide_row(m)[-1][0] for m in matches)
    assert "Library: Environmental" in p.summary.text()

    i18n.set_language("ar")
    p.retranslate()
    ar = i18n.STRINGS["ar"]
    assert p.library_label.text() == ar["idl_label"]
    assert p.library_combo.itemText(0) == ar["idl_environmental"]
    assert p.drift_label.text().startswith("⚠ " + ar["idl_drift"].split("(")[0])
    assert ar["idl_short_environmental"] in p.summary.text()
    assert not p.grab().isNull()
    p.close()


def test_every_new_string_has_arabic():
    from spectramaster.gui import identification_library as idl
    assert set(idl.EN) == set(idl.AR)
