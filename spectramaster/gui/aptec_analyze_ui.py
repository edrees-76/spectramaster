"""Aptec-style Analyze menu: Setup (ROI Properties Shift+R, Peak Search Shift+P, Identification
Shift+I, Background Subtract Shift+B, Quantify Shift+Q, Analyze Defaults, analysis method),
Peak Search (P), Identify Peaks (I), Background Subtract (B) and Quantify (Q).

The calculations are in :mod:`spectramaster.analysis.aptec_analyze` (no Qt).  With the Aptec
method (default) P sets ROIs on the peaks, I identifies them, B subtracts the background count
rate of matching ROIs of a background spectrum and Q gives their activities; the results are
kept on the plot's ROIs and shown in the ROI list and on the plot.  With the SpectraMaster method
P runs SpectraMaster's own analysis (fitted peaks, identification scores) as before.
"""
from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Optional

from PySide6.QtCore import Qt
from PySide6.QtGui import QAction, QActionGroup, QKeySequence
from PySide6.QtWidgets import (QButtonGroup, QCheckBox, QComboBox, QDialog, QDialogButtonBox, QDoubleSpinBox,
                               QFileDialog, QFormLayout, QHBoxLayout, QLabel, QLineEdit, QMenu, QMessageBox,
                               QPushButton, QRadioButton, QSpinBox, QVBoxLayout)

from ..analysis import aptec_analyze as aa
from ..analysis import aptec_multifit as amf
from .aptec_analyze_strings import atr, engine_text

KEY = "aptec/analyze/"
ENGINE_APTEC = "aptec"
ENGINE_SM = "spectramaster"
UNITS = ("Bq", "kBq", "MBq", "mBq", "pCi", "nCi", "uCi", "mCi", "Ci", "dps", "dpm", "gamma/s", "gamma/m", "cps", "cpm")


def _rtl(w) -> None:
    from . import i18n
    w.setLayoutDirection(Qt.RightToLeft if i18n.is_rtl(i18n.language()) else Qt.LeftToRight)


def _ltr_widget(w):
    w.setLayoutDirection(Qt.LeftToRight)
    return w


def _hint(text: str) -> QLabel:
    lab = QLabel(text)
    lab.setWordWrap(True)
    return lab


def _buttons(dlg: QDialog, lay) -> QDialogButtonBox:
    bb = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
    bb.accepted.connect(dlg.accept)
    bb.rejected.connect(dlg.reject)
    lay.addWidget(bb)
    return bb


def _displayed(win):
    spectra = getattr(win, "_spectra", None)
    i = getattr(win, "_index", -1)
    if spectra is None or not 0 <= i < len(spectra):
        return None
    return spectra[i]


# ===================================================================== setup dialogs
class PeakSearchDialog(QDialog):
    def __init__(self, setup: aa.PeakSearchSetup, n_channels: int = 16384, parent=None, win=None):
        super().__init__(parent)
        _rtl(self)
        self.win = win
        self.setWindowTitle(atr("peak_title"))
        lay = QVBoxLayout(self)
        self.all = QRadioButton(atr("peak_all"))
        self.partial = QRadioButton(atr("peak_partial"))
        (self.partial if setup.partial else self.all).setChecked(True)
        lay.addWidget(self.all)
        lay.addWidget(self.partial)
        form = QFormLayout()
        self.start = _ltr_widget(QSpinBox())
        self.stop = _ltr_widget(QSpinBox())
        for sb, v in ((self.start, setup.start), (self.stop, setup.stop or n_channels - 1)):
            sb.setRange(0, max(1, n_channels - 1))
            sb.setValue(int(v))
        form.addRow(atr("peak_start"), self.start)
        form.addRow(atr("peak_stop"), self.stop)
        self.max_error = _ltr_widget(QDoubleSpinBox())
        self.max_error.setRange(0.1, 1000.0)
        self.max_error.setDecimals(2)
        self.max_error.setValue(float(setup.max_error))
        form.addRow(atr("peak_err"), self.max_error)
        lay.addLayout(form)
        if win is not None and hasattr(win, "act_roi_props"):
            b = QPushButton(atr("peak_props"))
            b.clicked.connect(win.act_roi_props.trigger)
            lay.addWidget(b)
        lay.addWidget(_hint(atr("peak_hint")))
        _buttons(self, lay)
        self.partial.toggled.connect(self._sync)
        self._sync()

    def _sync(self) -> None:
        on = self.partial.isChecked()
        self.start.setEnabled(on)
        self.stop.setEnabled(on)

    def setup(self) -> aa.PeakSearchSetup:
        return aa.PeakSearchSetup(max_error=self.max_error.value(), partial=self.partial.isChecked(),
                                  start=self.start.value(), stop=self.stop.value())


class IdentifyDialog(QDialog):
    def __init__(self, setup: aa.IdentifySetup, parent=None):
        super().__init__(parent)
        _rtl(self)
        self.setWindowTitle(atr("id_title"))
        lay = QVBoxLayout(self)
        form = QFormLayout()
        row = QHBoxLayout()
        self.library = QComboBox()
        self.library.addItem(atr("id_lib_sm"), "")
        if setup.library:
            self.library.addItem(Path(setup.library).name, setup.library)
            self.library.setCurrentIndex(1)
        browse = QPushButton(atr("id_lib_browse"))
        browse.clicked.connect(self._browse)
        row.addWidget(self.library, 1)
        row.addWidget(browse)
        form.addRow(atr("id_library"), row)
        lay.addLayout(form)
        self.by_fwhm = QRadioButton(atr("id_match_fwhm"))
        self.fixed = QRadioButton(atr("id_match_fixed"))
        (self.by_fwhm if setup.match_by_fwhm else self.fixed).setChecked(True)
        lay.addWidget(self.by_fwhm)
        lay.addWidget(self.fixed)
        form = QFormLayout()
        self.fwhm_fraction = self._spin(0.01, 10.0, setup.fwhm_fraction, 3)
        self.fixed_tolerance = self._spin(0.001, 1000.0, setup.fixed_tolerance, 3)
        self.fraction_limit = self._spin(0.0, 100.0, setup.fraction_limit, 1)
        self.hl_limit = self._spin(0.1, 1000.0, setup.half_life_limit, 1)
        self.hl_reject = QCheckBox(atr("id_hl_reject"))
        self.hl_reject.setChecked(bool(setup.half_life_reject))
        form.addRow(atr("id_fwhm_fract"), self.fwhm_fraction)
        form.addRow(atr("id_fixed"), self.fixed_tolerance)
        form.addRow(atr("id_fraction"), self.fraction_limit)
        hl = QHBoxLayout()
        hl.addWidget(self.hl_limit)
        hl.addWidget(self.hl_reject)
        form.addRow(atr("id_hl_limit"), hl)
        lay.addLayout(form)
        lay.addWidget(_hint(atr("id_hint")))
        _buttons(self, lay)

    @staticmethod
    def _spin(lo, hi, v, dec) -> QDoubleSpinBox:
        s = _ltr_widget(QDoubleSpinBox())
        s.setRange(lo, hi)
        s.setDecimals(dec)
        s.setValue(float(v))
        return s

    def _browse(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, atr("fd_library"), str(Path(self.library.currentData() or "").parent),
                                              "Aptec library (*.lib)")
        if path:
            self.add_library(path)

    def add_library(self, path: str) -> None:
        i = self.library.findData(path)
        if i < 0:
            self.library.addItem(Path(path).name, path)
            i = self.library.count() - 1
        self.library.setCurrentIndex(i)

    def setup(self) -> aa.IdentifySetup:
        return aa.IdentifySetup(library=self.library.currentData() or "", match_by_fwhm=self.by_fwhm.isChecked(),
                                fwhm_fraction=self.fwhm_fraction.value(), fixed_tolerance=self.fixed_tolerance.value(),
                                fraction_limit=self.fraction_limit.value(), half_life_limit=self.hl_limit.value(),
                                half_life_reject=self.hl_reject.isChecked())


class BackgroundDialog(QDialog):
    def __init__(self, path: str, parent=None, win=None):
        super().__init__(parent)
        _rtl(self)
        self.win = win
        self.setWindowTitle(atr("bkg_title"))
        lay = QVBoxLayout(self)
        form = QFormLayout()
        row = QHBoxLayout()
        self.path = _ltr_widget(QLineEdit(path))
        self.path.setPlaceholderText(atr("bkg_none"))
        sel = QPushButton(atr("bkg_select"))
        sel.clicked.connect(self._select)
        row.addWidget(self.path, 1)
        row.addWidget(sel)
        form.addRow(atr("bkg_file"), row)
        lay.addLayout(form)
        lay.addWidget(_hint(atr("bkg_hint")))
        _buttons(self, lay)

    def _select(self) -> None:
        if self.win is not None and hasattr(self.win, "_ask_open_file"):
            p = self.win._ask_open_file(atr("fd_bkg"), "background")
        else:
            p, _ = QFileDialog.getOpenFileName(self, atr("fd_bkg"))
        if p:
            self.path.setText(p)


class QuantifyDialog(QDialog):
    def __init__(self, setup: aa.QuantifySetup, eff_source: str = "", parent=None):
        super().__init__(parent)
        _rtl(self)
        self.setWindowTitle(atr("q_title"))
        lay = QVBoxLayout(self)
        form = QFormLayout()
        self.mode = QButtonGroup(self)
        box = QVBoxLayout()
        for k, key in enumerate(("q_activity", "q_conc", "q_total")):
            b = QRadioButton(atr(key))
            self.mode.addButton(b, k)
            box.addWidget(b)
        mode = 2 if setup.use_quantity and setup.use_total_quantity else 1 if setup.use_quantity else 0
        self.mode.button(mode).setChecked(True)
        form.addRow(atr("q_as"), box)
        self.units = QComboBox()
        self.units.setEditable(True)
        self.units.addItems(UNITS)
        self.units.setCurrentText(setup.activity_units or "Bq")
        _ltr_widget(self.units)
        form.addRow(atr("q_units"), self.units)
        self.use_w = QCheckBox(atr("q_use_w"))
        self.use_x = QCheckBox(atr("q_use_x"))
        self.use_y = QCheckBox(atr("q_use_y"))
        for cb, v in ((self.use_w, setup.use_w), (self.use_x, setup.use_x), (self.use_y, setup.use_y)):
            cb.setChecked(bool(v))
            form.addRow("", cb)
        self.true_time = QCheckBox(atr("q_true"))
        self.true_time.setChecked(bool(setup.true_time_decay))
        form.addRow("", self.true_time)
        self.eff = QComboBox()
        self.eff.addItem(atr("q_eff_spec"), "")
        try:
            from ..analysis.efficiency import list_curves
            for p in list_curves():
                self.eff.addItem(p.stem, str(p))
        except Exception:
            pass
        i = self.eff.findData(eff_source)
        self.eff.setCurrentIndex(max(i, 0))
        form.addRow(atr("q_eff"), self.eff)
        lay.addLayout(form)
        lay.addWidget(_hint(atr("q_hint")))
        _buttons(self, lay)

    def setup(self) -> aa.QuantifySetup:
        m = self.mode.checkedId()
        return aa.QuantifySetup(activity_units=self.units.currentText().strip() or "Bq", use_quantity=m >= 1,
                                use_total_quantity=m == 2, use_w=self.use_w.isChecked(), use_x=self.use_x.isChecked(),
                                use_y=self.use_y.isChecked(), true_time_decay=self.true_time.isChecked())

    def eff_source(self) -> str:
        return self.eff.currentData() or ""


class MultifitDialog(QDialog):
    """Aptec *Multifit Fitting Parameters* (Shift+M)."""

    def __init__(self, setup: amf.MultifitSetup, parent=None):
        super().__init__(parent)
        _rtl(self)
        self.setWindowTitle(atr("mf_title"))
        lay = QVBoxLayout(self)
        form = QFormLayout()

        def pair(key_a, key_b, first):
            box = QVBoxLayout()
            a, b = QRadioButton(atr(key_a)), QRadioButton(atr(key_b))
            (a if first else b).setChecked(True)
            box.addWidget(a)
            box.addWidget(b)
            grp = QButtonGroup(self)
            grp.addButton(a)
            grp.addButton(b)
            return box, a
        box, self.hpge = pair("mf_hpge", "mf_nai", setup.detector == "hpge")
        form.addRow(atr("mf_type"), box)
        box, self.separated = pair("mf_separated", "mf_overlapped", setup.centroid_search == "separated")
        form.addRow(atr("mf_search"), box)
        box, self.multiplets_only = pair("mf_multiplets", "mf_all", not setup.fit_singlets)
        form.addRow(atr("mf_peaks"), box)
        self.k = IdentifyDialog._spin(0.1, 10.0, setup.k_sigma, 3)
        form.addRow(atr("mf_k"), self.k)
        box, self.width_fixed = pair("mf_fixed", "mf_varying", setup.width_fixed)
        form.addRow(atr("mf_width"), box)
        box, self.bkg_fixed = pair("mf_fixed", "mf_varying", setup.background_fixed)
        form.addRow(atr("mf_bkg"), box)
        self.iterations = _ltr_widget(QSpinBox())
        self.iterations.setRange(1, 1000)
        self.iterations.setValue(int(setup.max_iterations))
        form.addRow(atr("mf_iter"), self.iterations)
        self.pct = IdentifyDialog._spin(0.001, 100.0, setup.percent_change, 3)
        form.addRow(atr("mf_pct"), self.pct)
        self.chi = IdentifyDialog._spin(0.0, 100.0, setup.min_reduced_chi2, 3)
        form.addRow(atr("mf_chi"), self.chi)
        self.overlaps = _ltr_widget(QSpinBox())
        self.overlaps.setRange(1, 32)
        self.overlaps.setValue(int(setup.max_overlaps))
        form.addRow(atr("mf_over"), self.overlaps)
        lay.addLayout(form)
        lay.addWidget(_hint(atr("mf_hint")))
        _buttons(self, lay)

    def setup(self) -> amf.MultifitSetup:
        return amf.MultifitSetup(detector="hpge" if self.hpge.isChecked() else "nai",
                                 centroid_search="separated" if self.separated.isChecked() else "overlapped",
                                 fit_singlets=not self.multiplets_only.isChecked(), k_sigma=self.k.value(),
                                 width_fixed=self.width_fixed.isChecked(), background_fixed=self.bkg_fixed.isChecked(),
                                 max_iterations=self.iterations.value(), percent_change=self.pct.value(),
                                 min_reduced_chi2=self.chi.value(), max_overlaps=self.overlaps.value())


class DefaultsDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        _rtl(self)
        self.setWindowTitle(atr("def_title"))
        self.choice = None
        lay = QVBoxLayout(self)
        lay.addWidget(_hint(atr("def_text")))
        for key in ("factory", "recall", "save"):
            b = QPushButton(atr("def_" + key))
            b.clicked.connect(lambda _=False, k=key: self._pick(k))
            lay.addWidget(b)
        bb = QDialogButtonBox(QDialogButtonBox.StandardButton.Cancel)
        bb.rejected.connect(self.reject)
        lay.addWidget(bb)

    def _pick(self, key: str) -> None:
        self.choice = key
        self.accept()


# ===================================================================== controller
class AptecAnalysis:
    """Setups and the four analysis steps of one main window.  ``message`` is replaced by tests."""

    def __init__(self, win):
        self.win = win
        s = getattr(win, "settings", None)
        self.engine = str(s.get(KEY + "engine", ENGINE_APTEC)) if s is not None else ENGINE_APTEC
        if self.engine not in (ENGINE_APTEC, ENGINE_SM):
            self.engine = ENGINE_APTEC
        self.peak = aa.PeakSearchSetup.from_dict(self._load("peak"))
        self.ident = aa.IdentifySetup.from_dict(self._load("ident"))
        self.quant = aa.QuantifySetup.from_dict(self._load("quant"))
        self.multifit = amf.MultifitSetup.from_dict(self._load("multifit"))
        self.bkg_file = str(self._load("bkg").get("file", "")) if isinstance(self._load("bkg"), dict) else ""
        self.eff_source = str(self._load("quant_eff").get("path", "")) if isinstance(self._load("quant_eff"), dict) else ""
        self._lib_cache: dict = {}

    # ---------------------------------------------------------------- persistence
    def _load(self, name: str):
        s = getattr(self.win, "settings", None)
        raw = s.get(KEY + name, "") if s is not None else ""
        try:
            return json.loads(raw) if raw else {}
        except (TypeError, ValueError):
            return {}

    def save(self) -> None:
        s = getattr(self.win, "settings", None)
        if s is None:
            return
        s.set(KEY + "engine", self.engine)
        s.set(KEY + "peak", json.dumps(self.peak.to_dict()))
        s.set(KEY + "ident", json.dumps(self.ident.to_dict()))
        s.set(KEY + "quant", json.dumps(self.quant.to_dict()))
        s.set(KEY + "multifit", json.dumps(self.multifit.to_dict()))
        s.set(KEY + "bkg", json.dumps({"file": self.bkg_file}))
        s.set(KEY + "quant_eff", json.dumps({"path": self.eff_source}))

    def _all(self) -> dict:
        return {"roi": self.win.plot.roi_props.to_dict(), "peak": self.peak.to_dict(), "ident": self.ident.to_dict(),
                "quant": self.quant.to_dict(), "multifit": self.multifit.to_dict(), "bkg": self.bkg_file,
                "quant_eff": self.eff_source}

    def _apply_all(self, d: dict) -> None:
        from ..analysis.aptec_roi import RoiProperties
        from .aptec_roi_ui import save_properties
        props = RoiProperties.from_dict(d.get("roi", {}))
        self.win.plot.set_roi_props(props)
        save_properties(getattr(self.win, "settings", None), props)
        self.peak = aa.PeakSearchSetup.from_dict(d.get("peak", {}))
        self.ident = aa.IdentifySetup.from_dict(d.get("ident", {}))
        self.quant = aa.QuantifySetup.from_dict(d.get("quant", {}))
        self.multifit = amf.MultifitSetup.from_dict(d.get("multifit", {}))
        self.bkg_file = str(d.get("bkg", "") or "")
        self.eff_source = str(d.get("quant_eff", "") or "")
        self.save()
        if hasattr(self.win, "roi_panel"):
            self.win.roi_panel.retranslate()

    def defaults(self, choice: Optional[str] = None) -> bool:
        if choice is None:
            d = DefaultsDialog(self.win)
            if d.exec() != QDialog.Accepted or d.choice is None:
                return False
            choice = d.choice
        s = getattr(self.win, "settings", None)
        if choice == "factory":
            self._apply_all({})
        elif choice == "save":
            if s is not None:
                s.set(KEY + "user_defaults", json.dumps(self._all()))
        else:
            raw = s.get(KEY + "user_defaults", "") if s is not None else ""
            if not raw:
                self.status(atr("def_none"))
                return False
            self._apply_all(json.loads(raw))
        self.status(atr("def_done_" + choice))
        return True

    def set_engine(self, engine: str) -> None:
        self.engine = engine if engine in (ENGINE_APTEC, ENGINE_SM) else ENGINE_APTEC
        self.save()
        sync_actions(self.win)

    # ---------------------------------------------------------------- setup dialogs
    def setup_peak(self) -> bool:
        spec = _displayed(self.win)
        d = PeakSearchDialog(self.peak, spec.num_channels if spec else 16384, self.win, self.win)
        if d.exec() != QDialog.Accepted:
            return False
        try:
            self.peak = d.setup().validate()
        except ValueError as exc:
            self.message(str(exc))
            return False
        self.save()
        return True

    def setup_ident(self) -> bool:
        d = IdentifyDialog(self.ident, self.win)
        if d.exec() != QDialog.Accepted:
            return False
        try:
            self.ident = d.setup().validate()
        except ValueError as exc:
            self.message(str(exc))
            return False
        self.save()
        return True

    def setup_bkg(self) -> bool:
        d = BackgroundDialog(self.bkg_file, self.win, self.win)
        if d.exec() != QDialog.Accepted:
            return False
        self.bkg_file = d.path.text().strip()
        self.save()
        return True

    def setup_multifit(self) -> bool:
        d = MultifitDialog(self.multifit, self.win)
        if d.exec() != QDialog.Accepted:
            return False
        try:
            self.multifit = d.setup().validate()
        except ValueError as exc:
            self.message(str(exc))
            return False
        self.save()
        return True

    def setup_quant(self) -> bool:
        d = QuantifyDialog(self.quant, self.eff_source, self.win)
        if d.exec() != QDialog.Accepted:
            return False
        self.quant = d.setup()
        self.eff_source = d.eff_source()
        self.save()
        return True

    # ---------------------------------------------------------------- helpers
    def status(self, text: str, ms: int = 10000) -> None:
        self.win.statusBar().showMessage(text, ms)

    def message(self, text: str) -> None:
        QMessageBox.warning(self.win, atr("err", msg="").rstrip(": "), text)

    def library_lines(self) -> tuple[list, str]:
        path = self.ident.library
        key = path or "<sm>"
        if key not in self._lib_cache:
            if path:
                lines, _units = aa.read_aptec_library(path)
                name = Path(path).name
            else:
                lines = aa.lines_from_library()
                name = atr("id_lib_sm")
            self._lib_cache[key] = (lines, name)
        return self._lib_cache[key]

    def _show_rois(self) -> None:
        """Bring the ROI table forward: it is tabbed with the analysis results, where the
        identification / quantification of the ROIs would otherwise stay out of sight."""
        dock = getattr(self.win, "roi_dock", None)
        if dock is None:
            return
        if dock.isHidden():
            dock.show()
        dock.raise_()

    def _refresh(self) -> None:
        plot = self.win.plot
        plot.repaint()              # now: the ROI labels show the identified isotopes at once
        if hasattr(self.win, "roi_panel"):
            self.win.roi_panel.refresh()

    # ---------------------------------------------------------------- P
    def run_peak(self) -> bool:
        win = self.win
        if self.engine == ENGINE_SM:
            return bool(win.run_analysis())
        spec = _displayed(win)
        if spec is None:
            self.status(atr("need_spectrum"))
            return False
        plot = win.plot
        try:
            found = aa.peak_search(spec.counts, self.peak, plot.roi_props, spec.live_time)
        except ValueError as exc:
            self.message(atr("err", msg=engine_text(str(exc))))
            return False
        set_rois(plot, [(st.rl, st.rh) for st in found])
        self._show_rois()
        self.status(atr("peak_done", n=len(found), e=f"{self.peak.max_error:g}"))
        return True

    # ---------------------------------------------------------------- M
    def fwhm_function(self, spec, rois):
        """(FWHM in channels as a function of the index, auto) from the resolution calibration
        (keV) or, without one, Aptec's auto resolution calibration from the ROI widths."""
        import numpy as np
        first = spec.first_channel
        if spec.fwhm_coeffs and spec.energy_coeffs:
            fc = list(spec.fwhm_coeffs)
            ec = np.polynomial.polynomial.polyder(np.asarray(spec.energy_coeffs, dtype=float))

            def f(i):
                ch = first + float(i)
                kev = float(np.polynomial.polynomial.polyval(ch, fc))
                slope = float(np.polynomial.polynomial.polyval(ch, ec)) if len(ec) else 0.0
                return kev / slope if slope > 0 else kev
            return f, False
        use = [r for r in rois if r.stats.centroid is not None]
        coeffs = amf.auto_resolution([r.stats.centroid - first for r in use], [r.stats.fwhm for r in use])
        if not coeffs:
            return None, True
        return (lambda i: max(float(np.polynomial.polynomial.polyval(float(i), coeffs)), 0.5)), True

    def run_multifit(self) -> bool:
        win = self.win
        spec = _displayed(win)
        if spec is None:
            self.status(atr("need_spectrum"))
            return False
        plot = win.plot
        plot.clear_fits()
        plot._recompute_rois()
        rois = [r for r in plot.rois if r.stats is not None]
        if not rois:
            self.status(atr("need_rois"))
            return False
        if self.multifit.detector == "nai" and spec.num_channels > 512:
            self.message(atr("mf_nai_big"))
            return False
        fwhm_of, auto = self.fwhm_function(spec, rois)
        if fwhm_of is None:
            self.message(atr("err", msg=atr("mf_no_res")))
            return False
        first = spec.first_channel
        energy_of = (lambda i: spec.energy_of(first + i)) if spec.energy_coeffs else None
        from .plot import Roi
        new, n_fit, n_peaks, n_mult = [], 0, 0, 0
        for r in plot.rois:
            st = r.stats
            if st is None:
                new.append(r)
                continue
            ep = list(range(st.bl, r.left)) + list(range(r.right + 1, st.bh + 1))
            res = amf.multifit_roi(spec.counts, r.left, r.right, list(st.coeffs), fwhm_of, self.multifit,
                                   st.fwhm, ep, energy_of)
            if not res.fitted or not res.components:
                new.append(r)
                continue
            n_fit += 1
            n_peaks += len(res.components)
            n_mult += bool(res.multiplet)
            for k in range(len(res.components)):
                q = r if k == 0 else Roi(r.left, r.right)
                q.fit = (res, k)
                for attr in ("aptec_id", "aptec_bkg", "aptec_q"):
                    setattr(q, attr, None)
                new.append(q)
        plot.rois[:] = new
        plot.indexed_roi = None
        plot._recompute_rois()
        plot.roisChanged.emit()
        plot.roiIndexChanged.emit(-1)
        plot.update()
        self._show_rois()
        self.status(atr("mf_done", n=n_fit, k=n_peaks, m=n_mult) + (atr("mf_auto") if auto else ""), 15000)
        return True

    # ---------------------------------------------------------------- I
    def run_identify(self) -> bool:
        win = self.win
        spec = _displayed(win)
        if spec is None:
            self.status(atr("need_spectrum"))
            return False
        plot = win.plot
        rois = [r for r in plot.rois if r.stats is not None]
        if not rois:
            self.status(atr("need_rois"))
            return False
        try:
            lines, lib_name = self.library_lines()
        except (OSError, ValueError) as exc:
            self.message(atr("err", msg=engine_text(str(exc))))
            return False
        e_range = None
        if spec.energy_coeffs:
            e_range = (spec.energy_of(spec.first_channel), spec.energy_of(spec.first_channel + spec.num_channels - 1))
        res = aa.identify([r.stats.centroid_energy for r in rois],
                          [r.stats.fwhm_kev if r.stats.fwhm else None for r in rois], lines, self.ident, e_range,
                          _elapsed(spec))
        for r, x in zip(rois, res):
            r.aptec_id = x
            r.aptec_bkg = None
            r.aptec_q = None
        n = sum(1 for x in res if x is not None)
        self._show_rois()
        self._refresh()
        self.status(atr("ident_done", n=n, m=len(rois), lib=lib_name))
        return True

    # ---------------------------------------------------------------- B
    def run_bkg(self, path: Optional[str] = None) -> bool:
        win = self.win
        spec = _displayed(win)
        if spec is None:
            self.status(atr("need_spectrum"))
            return False
        rois = [r for r in win.plot.rois if getattr(r, "aptec_id", None) is not None and r.stats is not None]
        if not rois:
            self.status(atr("need_ident"))
            return False
        path = path or self.bkg_file
        if not path:
            self.status(atr("need_bkg_file"))
            return False
        from ..convert import read_spectra
        try:
            spectra, _fmt = read_spectra(Path(path), win.settings.input_format() if hasattr(win, "settings") else None)
            bkg = spectra[0]
            lines, _name = self.library_lines()
            table = background_lines(bkg, win.plot.roi_props, self.peak, self.ident, lines)
        except Exception as exc:                # unreadable file, no calibration, ...
            self.message(atr("err", msg=engine_text(str(exc)) or type(exc).__name__))
            return False
        n = 0
        for r in rois:
            hit = table.get(_line_key(r.aptec_id.line))
            r.aptec_bkg = None
            if hit is not None and hit[0] > hit[2]:          # above the background MDA
                r.aptec_bkg = hit
                n += 1
            r.aptec_q = None
        self._refresh()
        self.status(atr("bkg_done", n=n, name=Path(path).name))
        return True

    # ---------------------------------------------------------------- Q
    def efficiency_at(self, spec):
        """Function energy -> (efficiency, relative error %) or None."""
        if self.eff_source:
            from ..analysis.efficiency import load_curve
            curve = load_curve(self.eff_source)
            return lambda e: (float(curve.efficiency(e)), 100.0 * float(curve.rel_uncertainty(e)))
        p = Path(spec.source_path) if spec.source_path else None
        if p is None or p.suffix.lower() != ".s0" or not p.is_file():
            p = getattr(self.win, "_path", None)
        if p is not None and Path(p).suffix.lower() == ".s0" and Path(p).is_file():
            from ..analysis import aptec_calibration as ac
            cal = ac.read_aptec_calibrations(p).get("efficiency")
            if cal is not None:
                return lambda e: ac.calculate_efficiency(cal, e)[:2]
        return None

    def run_quant(self) -> bool:
        win = self.win
        spec = _displayed(win)
        if spec is None:
            self.status(atr("need_spectrum"))
            return False
        rois = [r for r in win.plot.rois if getattr(r, "aptec_id", None) is not None and r.stats is not None]
        if not rois:
            self.status(atr("need_ident"))
            return False
        try:
            eff = self.efficiency_at(spec)
        except Exception as exc:
            self.message(atr("err", msg=engine_text(str(exc)) or type(exc).__name__))
            return False
        if eff is None:
            self.message(atr("err", msg=atr("q_eff_none")))
            return False
        x = spec.extra
        lt = spec.live_time
        n_ok, why = 0, set()
        for r in rois:
            st = r.stats
            cps = st.count_rate if st.count_rate is not None else (st.net / lt if lt else None)
            err = getattr(st, "err_pct", None)
            if cps is None:
                r.aptec_q = aa.QuantResult(None, None, None, None, note="no live time")
                why.add("no live time")
                continue
            bkg = getattr(r, "aptec_bkg", None)
            flags = ""
            if bkg is not None:
                cps_s = cps
                cps = cps_s - bkg[0]
                s_abs = abs(cps_s) * (err or 0.0) / 100.0
                err = 100.0 * (s_abs ** 2 + bkg[1] ** 2) ** 0.5 / abs(cps) if cps else None
                flags += "b"
            e_val, e_err = eff(st.centroid_energy)
            q = aa.quantify(cps, err, getattr(st, "mda_cps", None), r.aptec_id.line, e_val, self.quant,
                            live_time=lt, true_time=spec.real_time, start_time=spec.start_time,
                            activity_time=_parse_dt(x.get("activity_ref_date")),
                            quantity=_float(x.get("quantity")), total_quantity=_float(x.get("total_quantity")),
                            w=_float(x.get("w_const")), x=_float(x.get("x_const")), y=_float(x.get("y_const")),
                            efficiency_err_pct=e_err or 0.0)
            q.flags = flags + q.flags
            r.aptec_q = q
            if q.activity is not None:
                n_ok += 1
            else:
                why.add(q.note)
        self._refresh()
        text = atr("quant_done", n=n_ok, units=self.units_label(spec))
        if n_ok < len(rois):
            text += "  " + atr("quant_note", n=len(rois) - n_ok, why="; ".join(sorted(engine_text(w) for w in why if w)))
        self.status(text, 15000)
        return True

    def units_label(self, spec=None) -> str:
        u = self.quant.activity_units or "Bq"
        spec = spec or _displayed(self.win)
        if self.quant.use_quantity and not self.quant.use_total_quantity and spec is not None:
            qu = str(spec.extra.get("quantity_units", "") or "").strip()
            if qu:
                u += "/" + qu
        return u


# ===================================================================== helpers (no Qt state)
def _float(v) -> Optional[float]:
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    return None if math.isnan(f) else f


def _parse_dt(v):
    from datetime import datetime
    if isinstance(v, datetime):
        return v
    if not v:
        return None
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%d"):
        try:
            return datetime.strptime(str(v)[:19], fmt)
        except ValueError:
            continue
    return None


def _elapsed(spec) -> Optional[float]:
    t0 = _parse_dt(spec.extra.get("activity_ref_date")) if spec is not None else None
    if t0 is None or spec.start_time is None:
        return None
    return abs((spec.start_time - t0).total_seconds())


def _line_key(line) -> tuple:
    return (line.isotope.lower(), round(float(line.energy), 2))


def set_rois(plot, bounds) -> None:
    """Replace the plot's ROIs (Peak Search result)."""
    from .plot import Roi
    plot.rois.clear()
    plot.indexed_roi = None
    for lo, hi in bounds:
        plot.rois.append(Roi(int(lo), int(hi)))
    plot.rois.sort(key=lambda r: r.left)
    plot._recompute_rois()
    plot.roisChanged.emit()
    plot.roiIndexChanged.emit(-1)
    plot.update()


def background_lines(bkg, props, peak_setup, ident_setup, lines) -> dict:
    """Identified lines of a background spectrum: {(isotope, energy): (net cps, 1-sigma cps, MDA cps)}."""
    if not bkg.live_time:
        raise ValueError("the background spectrum has no live time")
    found = aa.peak_search(bkg.counts, peak_setup, props, bkg.live_time)
    if not found:
        return {}
    first = bkg.first_channel

    def en(ch):
        return bkg.energy_of(first + ch) if bkg.energy_coeffs else None
    energies = [en(st.centroid) if st.centroid is not None else None for st in found]
    fwhm = []
    for st in found:
        if st.fwhm and bkg.energy_coeffs and st.centroid is not None:
            fwhm.append(abs(en(st.centroid + st.fwhm / 2) - en(st.centroid - st.fwhm / 2)))
        else:
            fwhm.append(None)
    e_range = (en(0), en(bkg.num_channels - 1)) if bkg.energy_coeffs else None
    res = aa.identify(energies, fwhm, lines, ident_setup, e_range)
    out = {}
    for st, x in zip(found, res):
        if x is None or st.net_cps is None:
            continue
        out[_line_key(x.line)] = (st.net_cps, st.net_unc / bkg.live_time, st.mda_cps or 0.0)
    return out


# ===================================================================== menu
def install_analyze_menu(win) -> None:
    """Aptec's upper Analyze menu: Setup >, Peak Search (P), Identify Peaks (I), Background
    Subtract (B), Quantify (Q), inserted at the top of the Analyze menu."""
    win.aptec_analysis = ctl = AptecAnalysis(win)
    win._aana_actions = []

    def act(attr, key, fn, shortcut=None, tip=None):
        a = QAction(win)
        a.setObjectName(attr)
        a._aana_key = key
        a._aana_tip = tip or ("tip_" + key[4:] if key.startswith("act_") else "tip_" + key)
        if shortcut:
            a.setShortcut(QKeySequence(shortcut))
        a.triggered.connect(lambda _=False, f=fn: f())
        win.addAction(a)
        setattr(win, attr, a)
        win._aana_actions.append(a)
        return a

    act("act_a_setup_peak", "act_setup_peak", ctl.setup_peak, "Shift+P")
    act("act_a_setup_ident", "act_setup_ident", ctl.setup_ident, "Shift+I")
    act("act_a_setup_bkg", "act_setup_bkg", ctl.setup_bkg, "Shift+B")
    act("act_a_setup_quant", "act_setup_quant", ctl.setup_quant, "Shift+Q")
    act("act_a_setup_mf", "act_setup_mf", ctl.setup_multifit, "Shift+M")
    act("act_a_mf", "act_mf", ctl.run_multifit, "M")
    act("act_a_defaults", "act_defaults", ctl.defaults)
    act("act_a_ident", "act_ident", ctl.run_identify, "I")
    act("act_a_bkg", "act_bkg", ctl.run_bkg, "B")
    act("act_a_quant", "act_quant", ctl.run_quant, "Q")
    grp = QActionGroup(win)
    win._aana_engine = {}
    for eng, key in ((ENGINE_APTEC, "engine_aptec"), (ENGINE_SM, "engine_sm")):
        a = act("act_a_engine_" + eng, key, lambda e=eng: ctl.set_engine(e), tip="tip_engine")
        a.setCheckable(True)
        grp.addAction(a)
        win._aana_engine[eng] = a
    win._aana_engine[ctl.engine].setChecked(True)

    # P: Aptec Peak Search or SpectraMaster's analysis, by the chosen method
    a = win.act_analyze
    try:
        a.triggered.disconnect()
    except (RuntimeError, TypeError):
        pass
    a.triggered.connect(lambda _=False: ctl.run_peak())

    menu = win.menu_analyze
    menu.removeAction(win.act_analyze)
    first = menu.actions()[0] if menu.actions() else None
    win.menu_a_setup = QMenu(win)
    sm = win.menu_a_setup
    if hasattr(win, "act_roi_props"):
        sm.addAction(win.act_roi_props)
    for a in (win.act_a_setup_peak, win.act_a_setup_mf, win.act_a_setup_ident, win.act_a_setup_bkg,
              win.act_a_setup_quant):
        sm.addAction(a)
    sm.addSeparator()
    sm.addAction(win.act_a_defaults)
    win.menu_a_engine = sm.addMenu("")
    for a in win._aana_engine.values():
        win.menu_a_engine.addAction(a)
    menu.insertMenu(first, sm)
    menu.insertAction(first, win.act_analyze)
    for a in (win.act_a_mf, win.act_a_ident, win.act_a_bkg, win.act_a_quant):
        menu.insertAction(first, a)
    menu.insertSeparator(first)
    retranslate_analyze_menu(win)


def sync_enabled(win) -> None:
    """With the Aptec method P needs only a spectrum (SpectraMaster's engine may be missing)."""
    if not hasattr(win, "aptec_analysis"):
        return
    has = _displayed(win) is not None
    if win.aptec_analysis.engine == ENGINE_APTEC:
        win.act_analyze.setEnabled(has)
        win.act_analyze.setToolTip(atr("tip_peak"))
        win.act_analyze.setStatusTip(atr("tip_peak"))
    for a in (win.act_a_mf, win.act_a_ident, win.act_a_bkg, win.act_a_quant):
        a.setEnabled(has)


def sync_actions(win) -> None:
    if not hasattr(win, "aptec_analysis"):
        return
    ctl = win.aptec_analysis
    win._aana_engine[ctl.engine].setChecked(True)
    aptec = ctl.engine == ENGINE_APTEC
    for a in (win.act_a_mf, win.act_a_ident, win.act_a_bkg, win.act_a_quant):
        a.setVisible(aptec)
    retranslate_analyze_menu(win)
    if hasattr(win, "_update_actions"):
        win._update_actions()


def retranslate_analyze_menu(win) -> None:
    if not hasattr(win, "_aana_actions"):
        return
    from .i18n import tr
    for a in win._aana_actions:
        a.setText(atr(a._aana_key))
        a.setToolTip(atr(a._aana_tip))
        a.setStatusTip(atr(a._aana_tip))
    win.menu_a_setup.setTitle(atr("menu_setup"))
    win.menu_a_engine.setTitle(atr("menu_engine"))
    aptec = win.aptec_analysis.engine == ENGINE_APTEC
    if aptec:
        win.act_analyze.setText(atr("act_peak"))
        win.act_analyze.setToolTip(atr("tip_peak"))
        win.act_analyze.setStatusTip(atr("tip_peak"))
    else:
        win.act_analyze.setText(tr("act_analyze"))
        if hasattr(win, "refresh_analysis_available"):
            win.refresh_analysis_available()
    sync_enabled(win)


__all__ = ["install_analyze_menu", "retranslate_analyze_menu", "sync_actions", "sync_enabled", "AptecAnalysis", "PeakSearchDialog",
           "IdentifyDialog", "BackgroundDialog", "QuantifyDialog", "MultifitDialog", "DefaultsDialog", "set_rois", "background_lines",
           "ENGINE_APTEC", "ENGINE_SM"]
