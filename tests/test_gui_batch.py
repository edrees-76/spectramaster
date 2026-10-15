"""GUI: batch analysis dialog grouped by measurement conditions (Release F, F3d)."""
from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import time

import pytest

pytest.importorskip("PySide6")

from PySide6.QtCore import QSettings
from PySide6.QtWidgets import QApplication

from spectramaster.convert import resolve_format, write_spectrum
from spectramaster.gui import i18n
from spectramaster.validation.synthetic import HPGE, NAI, Continuum, TruePeak, make_spectrum


@pytest.fixture(scope="module")
def qapp():
    from spectramaster.gui.app import create_app
    return create_app(["test"])


@pytest.fixture()
def settings(tmp_path):
    from spectramaster.gui.settings import Settings
    return Settings(QSettings(str(tmp_path / "s.ini"), QSettings.IniFormat))


@pytest.fixture(autouse=True)
def english():
    i18n.set_language("en")
    yield
    i18n.set_language("en")


def _files(folder):
    """Two HPGe spectra (one group), one NaI spectrum (another group) and an unreadable file."""
    folder.mkdir(parents=True, exist_ok=True)
    fmt = resolve_format("aptec_s0")
    out = []
    for i, det in enumerate([HPGE, HPGE, NAI]):
        s = make_spectrum(det, [TruePeak(661.657, 2e4), TruePeak(1460.8, 5e3)], Continuum(300, 400, 10), 40 + i).spectrum
        p = folder / f"s{i}.s0"
        write_spectrum(s, p, fmt)
        out.append(p)
    (folder / "broken.s0").write_bytes(b"not a spectrum")
    return out + [folder / "broken.s0"]


def wait_idle(dlg, timeout=180.0):
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        QApplication.processEvents()
        if not dlg.busy and not dlg.is_running():
            QApplication.processEvents()
            return True
        time.sleep(0.01)
    return False


def _dialog(settings, paths):
    from spectramaster.gui.batch_analysis import BatchAnalysisDialog
    dlg = BatchAnalysisDialog(None, settings, paths)
    dlg.message = lambda text: setattr(dlg, "last_error", text)
    return dlg


def test_unassigned_group_is_not_analysed(qapp, settings, tmp_path):
    from spectramaster.gui.workflow_strings import wtr
    dlg = _dialog(settings, _files(tmp_path / "data"))
    assert not dlg.btn_run.isEnabled()
    assert dlg.scan()
    assert wait_idle(dlg)
    assert len(dlg.groups) == 2 and dlg.group_table.rowCount() == 2
    assert dlg.error_list.count() == 1 and "broken.s0" in i18n.strip_bidi(dlg.error_list.item(0).text())
    assert all(dlg.group_table.item(r, 2).text() == wtr("setup_none") for r in range(2))
    hpge = max(dlg.groups, key=lambda g: len(g.items))
    nai = next(g for g in dlg.groups if g is not hpge)
    assert dlg.assign_setup(hpge.id, application="environmental")            # identification only
    assert wtr("setup_no_curve") in dlg.group_table.item(dlg.groups.index(hpge), 2).text()
    assert dlg.run()
    assert wait_idle(dlg)
    rows = dlg.rows
    assert rows and dlg.result_table.rowCount() == len(rows)
    na = [r for r in rows if r["group"] == nai.id]
    assert len(na) == 1 and na[0]["status"].startswith("not analysed")
    r_na = rows.index(na[0])
    col = dlg.keys.index("status")
    assert dlg.result_table.item(r_na, col).text() == wtr("st_not_analysed")
    assert all(not r["status"].startswith("not analysed") for r in rows if r["group"] == hpge.id)
    assert {r["file"] for r in rows if r["group"] == hpge.id} == {str(p) for p in hpge_paths(hpge)}
    out = dlg.save_csv(tmp_path / "batch.csv")
    lines = out.read_text(encoding="utf-8-sig").splitlines()
    assert lines[0].startswith("file,index,group") and len(lines) == len(rows) + 1
    assert "not analysed" in out.read_text(encoding="utf-8-sig")
    dlg.close()


def hpge_paths(group):
    return [it.path for it in group.items]


def test_setup_with_curve_and_bad_inputs(qapp, settings, tmp_path, monkeypatch):
    from spectramaster.validation.benchmark import _flat_curve
    monkeypatch.setenv("SPECTRAMASTER_EFF_DIR", str(tmp_path / "curves"))
    curve_path = _flat_curve().save(tmp_path / "curves" / "flat.json")
    dlg = _dialog(settings, _files(tmp_path / "data")[:2])
    dlg.scan()
    assert wait_idle(dlg) and len(dlg.groups) == 1
    gid = dlg.groups[0].id
    assert not dlg.assign_setup(gid, curve_path=tmp_path / "missing.json")
    assert "missing.json" in i18n.strip_bidi(dlg.last_error) and gid not in dlg.setups
    bad = tmp_path / "geo.json"
    bad.write_text("[1, 2]", encoding="utf-8")
    assert not dlg.assign_setup(gid, curve_path=curve_path, geometry_path=bad)
    assert dlg.assign_setup(gid, curve_path=curve_path, nuclides=["Cs-137", "K-40"])
    assert dlg.setups[gid].curve is not None and list(dlg.setups[gid].nuclides) == ["Cs-137", "K-40"]
    dlg.group_table.selectRow(0)
    dlg.unassign_selected()
    assert gid not in dlg.setups
    dlg.close()


def test_run_worker_cancel():
    from spectramaster.gui.batch_analysis import BatchRunWorker
    from spectramaster.lab.batch import BatchGroup, BatchItem
    s = make_spectrum(HPGE, [TruePeak(661.657, 2e4)], Continuum(300, 400, 10), 3).spectrum
    g = BatchGroup(1, "HPGe", len(s.counts), list(s.energy_coeffs), [BatchItem("x.s0", 0, s, "HPGe", len(s.counts), 1)])
    w = BatchRunWorker([g], {})
    got = []
    w.cancelled.connect(lambda: got.append("cancelled"))
    w.done.connect(lambda rows: got.append(rows))
    w.cancel()
    w.run()
    assert got == ["cancelled"]
    w2 = BatchRunWorker([g], {})
    w2.done.connect(lambda rows: got.append(rows))
    w2.run()
    assert got[-1][0]["status"].startswith("not analysed")


def test_status_labels_and_menu_action(qapp, settings):
    from spectramaster.gui.app import MainWindow
    from spectramaster.gui.batch_analysis import status_label
    from spectramaster.gui.session_io import open_batch_analysis
    assert status_label("refused: geometry") == "refused: geometry"
    i18n.set_language("ar")
    assert status_label("analysed") == i18n.STRINGS["ar"]["wf_st_analysed"]
    assert status_label("something else") == "something else"
    i18n.set_language("en")
    w = MainWindow(settings)
    try:
        assert w.act_batch_analysis in w.menu_analyze.actions()
        dlg = open_batch_analysis(w, show=False)
        assert dlg in w._analysis_batch_dialogs
        dlg.close()
    finally:
        w.close()
