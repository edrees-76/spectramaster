"""Analysis session of the main window (A5) and the laboratory workflow (Release F, F3).

* :class:`SessionController` (``win.session_ctl``) keeps the
  :class:`~spectramaster.lab.session.AnalysisSession` of the displayed spectrum as
  ``win.session``.  The main window calls it when a spectrum is shown, when an analysis is done
  and before a spectrum, a session or the window is replaced/closed; the activity dialog when it
  has computed activities; the fit-inspection window shares the same session (``win.fit_session``)
  so its manual edits, undo and redo are part of the saved session.
* File > Open Session... / Save Session / Save Session As... (``.smsession`` JSON).  Opening
  verifies the spectrum file by its SHA-256 (a moved file is looked for next to the session, then
  the user is asked to locate it), restores the stored energy calibration, results and history and
  **never recalculates**: stored results that require recalculation (changed inputs, other engine
  version) are shown as stored and flagged stale.
* The workflow dock lists :func:`~spectramaster.lab.workflow.workflow_status` (translated for the
  known codes); Analyze > Mark as Reviewed... and File > Export Report Record (JSON)... call
  ``mark_reviewed`` / ``write_report_json``.  The science stays in ``spectramaster.lab``.
"""
from __future__ import annotations

import copy
import json
import math
import re
from pathlib import Path
from typing import Optional

from PySide6.QtCore import Qt
from PySide6.QtGui import QAction, QColor, QIcon, QPainter, QPixmap
from PySide6.QtWidgets import (QDialog, QDialogButtonBox, QDockWidget, QFileDialog, QFormLayout, QLabel,
                               QLineEdit, QListWidget, QListWidgetItem, QMessageBox, QPlainTextEdit,
                               QVBoxLayout, QWidget)

from . import i18n
from .workflow_strings import wtr

SESSION_EXT = ".smsession"
REVIEWER_KEY = "workflow/reviewer"
LEVEL_COLORS = {"error": "#c62828", "warning": "#e65100", "info": "#6b7280", "ok": "#2e7d32"}
KNOWN_CODES = ("calibration_required", "incompatible_calibration", "outside_validated_scope", "results_stale",
               "no_results", "not_reviewed", "reviewed")


# ===================================================================== status texts
_NAME = r"(['\"])(?P<name>.*?)\1"
# (engine message pattern, string key, named groups shown LTR)
_PATTERNS = [
    (r"the spectrum has no energy calibration", "msg_no_energy_cal"),
    (r"no efficiency calibration recorded: activities cannot be reported", "msg_no_eff_cal"),
    (rf"efficiency calibration {_NAME} belongs to another detector", "msg_other_detector"),
    (rf"efficiency calibration {_NAME} belongs to another geometry: (?P<reasons>.+)", "msg_other_geometry_why"),
    (rf"efficiency calibration {_NAME} belongs to another geometry", "msg_other_geometry"),
    (rf"efficiency calibration {_NAME} is (?P<status>\w+)", "msg_eff_status"),
    (r"measurement geometry not recorded: compatibility not checked", "msg_geo_unrecorded"),
    (r"sample information not recorded: no concentration", "msg_sample_unrecorded"),
    (r"efficiency extrapolated at (?P<energies>.+) keV", "msg_extrapolated"),
    (r"no results computed yet", "msg_no_results"),
    (r"results require recalculation: (?P<reasons>.*)", "msg_stale"),
    (r"reviewed by (?P<who>.+?) on (?P<time>\S+): (?P<note>.*)", "msg_reviewed_note"),
    (r"reviewed by (?P<who>.+?) on (?P<time>\S+)", "msg_reviewed"),
    (r"automatic analysis not yet reviewed", "msg_not_reviewed"),
]
_COMPILED = [(re.compile(p + r"\Z", re.S), k) for p, k in _PATTERNS]


def status_text(st) -> str:
    """Translated message of a WorkflowStatus; unknown messages are shown as they are."""
    msg = st.message
    for rx, key in _COMPILED:
        m = rx.match(msg)
        if m is None:
            continue
        kw = {k: v for k, v in m.groupdict().items() if v is not None}
        if "status" in kw:
            vk = "wf_val_" + kw["status"]
            kw["status"] = wtr("val_" + kw["status"]) if vk in i18n.STRINGS["en"] else kw["status"]
        for k in ("name", "reasons", "energies", "time", "note", "who"):
            if k in kw:
                kw[k] = i18n.ltr(kw[k]) if k in ("name", "energies", "time") else kw[k]
        return wtr(key, **kw)
    return msg


def code_title(code: str) -> str:
    return wtr("code_" + code) if code in KNOWN_CODES else code


def _dot(color: str) -> QIcon:
    pm = QPixmap(12, 12)
    pm.fill(Qt.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing)
    p.setPen(Qt.NoPen)
    p.setBrush(QColor(color))
    p.drawEllipse(1, 1, 10, 10)
    p.end()
    return QIcon(pm)


class WorkflowPanel(QWidget):
    """Compact list of the workflow statuses (level dot and colour, translated message; the code
    title and the engine's own text in the tool tip)."""

    def __init__(self, parent=None):
        super().__init__(parent)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(4, 4, 4, 4)
        self.session_label = QLabel()
        self.session_label.setWordWrap(True)
        lay.addWidget(self.session_label)
        self.list = QListWidget()
        self.list.setWordWrap(True)
        self.list.setSelectionMode(QListWidget.NoSelection)
        lay.addWidget(self.list, 1)
        self.statuses: list = []

    def show_statuses(self, statuses, header: str, empty_text: str = "") -> None:
        self.statuses = list(statuses)
        self.session_label.setText(header)
        self.list.clear()
        if not self.statuses and empty_text:
            it = QListWidgetItem(_dot(LEVEL_COLORS["info"]), empty_text)
            it.setForeground(QColor(LEVEL_COLORS["info"]))
            self.list.addItem(it)
        for st in self.statuses:
            color = LEVEL_COLORS.get(st.level, LEVEL_COLORS["info"])
            it = QListWidgetItem(_dot(color), status_text(st))
            it.setForeground(QColor(color))
            it.setData(Qt.UserRole, (st.code, st.level))
            it.setToolTip(f"{wtr('level_' + st.level) if st.level in LEVEL_COLORS else st.level} · "
                          f"{code_title(st.code)}\n{st.message}")
            self.list.addItem(it)

    def rows(self) -> list[tuple[str, str, str]]:
        """(level, code, displayed text) of the listed statuses (tests, reports)."""
        out = []
        for i in range(self.list.count()):
            it = self.list.item(i)
            code, level = it.data(Qt.UserRole) or ("", "info")
            out.append((level, code, it.text()))
        return out


# ===================================================================== review dialog
class ReviewDialog(QDialog):
    def __init__(self, parent=None, reviewer: str = ""):
        super().__init__(parent)
        self.setLayoutDirection(Qt.RightToLeft if i18n.is_rtl() else Qt.LeftToRight)
        self.setWindowTitle(wtr("review_title"))
        lay = QVBoxLayout(self)
        form = QFormLayout()
        self.name_edit = QLineEdit(reviewer)
        form.addRow(wtr("review_reviewer"), self.name_edit)
        self.note_edit = QPlainTextEdit()
        self.note_edit.setFixedHeight(80)
        form.addRow(wtr("review_note"), self.note_edit)
        lay.addLayout(form)
        bb = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        bb.button(QDialogButtonBox.Ok).setText(wtr("review_title"))
        bb.accepted.connect(self.accept)
        bb.rejected.connect(self.reject)
        lay.addWidget(bb)


# ===================================================================== helpers
def _state(session) -> str:
    """Comparable state of a session (everything saved except the modification time)."""
    d = session.to_dict()
    d.pop("modified", None)
    return json.dumps(d, sort_keys=True, ensure_ascii=False, default=str)


def _same_coeffs(a, b) -> bool:
    a, b = list(a or []), list(b or [])
    return len(a) == len(b) and all(math.isclose(float(x), float(y), rel_tol=1e-12, abs_tol=1e-15)
                                    for x, y in zip(a, b))


def _energy_record(spectrum, source: str):
    from ..lab.calibration import CalibrationRecord
    return CalibrationRecord.from_spectrum(spectrum, "energy", source=source,
                                           name=spectrum.sample_id or "energy calibration")


def results_to_objects(results: dict) -> tuple[list, list]:
    """Peak / NuclideMatch objects of stored results (``matched`` refers to peaks by index)."""
    from ..analysis import NuclideMatch, Peak
    pf, mf = Peak.__dataclass_fields__, NuclideMatch.__dataclass_fields__
    peaks = [Peak(**{k: v for k, v in d.items() if k in pf}) for d in results.get("peaks", []) or []]
    matches = []
    for d in results.get("nuclide_matches", []) or []:
        kw = {k: v for k, v in d.items() if k in mf and k != "matched"}
        kw["matched"] = [(float(e), peaks[int(i)]) for e, i in d.get("matched", []) if 0 <= int(i) < len(peaks)]
        matches.append(NuclideMatch(**kw))
    return peaks, matches


# ===================================================================== controller
class SessionController:
    """The analysis session of the main window `win` (see the module docstring).

    ``ask_save_changes``, ``ask_review``, ``ask_spectrum_file``, ``confirm`` and the file-name
    prompts are separate methods so tests can replace them (no modal box blocks)."""

    def __init__(self, win):
        self.win = win
        self.session = None
        self.path: Optional[Path] = None           # session file (None: never saved)
        self._saved: Optional[str] = None          # _state() when saved / opened / created
        self._incoming = None                      # (session, spectrum index) while opening one
        self.concentration_session = None          # session_id the activity dialog's concentrations belong to
        self.panel = WorkflowPanel()

    # ------------------------------------------------------------ state
    @property
    def restoring(self) -> bool:
        return self._incoming is not None

    def _set(self, session, path: Optional[Path] = None) -> None:
        self.session, self.path = session, (Path(path) if path else None)
        self.win.session = session
        self._saved = _state(session) if session is not None else None

    def is_dirty(self) -> bool:
        return self.session is not None and _state(self.session) != self._saved

    def needs_saving(self) -> bool:
        """Unsaved changes worth a prompt: of a session saved or opened as a file, or of a review."""
        s = self.session
        return self.is_dirty() and (self.path is not None or bool(s.status.get("reviewed")))

    def ask_save_changes(self) -> str:
        """'save', 'discard' or 'cancel'."""
        box = QMessageBox(QMessageBox.Warning, wtr("unsaved_title"), wtr("unsaved_text"),
                          QMessageBox.Save | QMessageBox.Discard | QMessageBox.Cancel, self.win)
        box.setDefaultButton(QMessageBox.Save)
        ans = box.exec()
        return {QMessageBox.Save: "save", QMessageBox.Discard: "discard"}.get(ans, "cancel")

    def confirm_discard(self) -> bool:
        """True when the current session may be replaced (saved first if the user wants)."""
        if self.restoring or not self.needs_saving():
            return True
        ans = self.ask_save_changes()
        if ans == "save":
            return self.save_session()
        return ans == "discard"

    def confirm(self, title: str, text: str) -> bool:
        box = QMessageBox(QMessageBox.Question, title, text, QMessageBox.Yes | QMessageBox.No, self.win)
        box.setDefaultButton(QMessageBox.No)
        return box.exec() == QMessageBox.Yes

    def _status(self, text: str, ms: int = 10000) -> None:
        self.win.statusBar().showMessage(text, ms)

    def _settings(self):
        return getattr(self.win, "settings", None)

    # ------------------------------------------------------------ the displayed spectrum
    def _belongs(self, session, spectrum, index: int) -> bool:
        """`session` refers to `spectrum` (same file, position and counts)."""
        from ..lab.common import counts_fingerprint
        ref = session.spectrum_ref or {}
        path = getattr(self.win, "_path", None)
        if not ref.get("path") or path is None or spectrum is None:
            return False
        try:
            same_file = Path(ref["path"]).resolve() == Path(path).resolve()
        except OSError:
            same_file = False
        want = ref.get("counts_sha256")
        return (same_file and int(ref.get("index") or 0) == index
                and (not want or want == counts_fingerprint(spectrum.counts)))

    def session_for(self, spectrum):
        """The main session when it belongs to `spectrum` (the displayed one), else None."""
        win = self.win
        if self.session is None or spectrum is None or spectrum is not win.current_spectrum():
            return None
        return self.session if self._belongs(self.session, spectrum, win._index) else None

    def kept_quant(self, session) -> Optional[dict]:
        """Stored activity results kept when the peaks are recomputed (not when they are stale)."""
        if session is not self.session or session.status.get("results_stale"):
            return None
        return (session.results or {}).get("quant")

    def can_switch(self) -> bool:
        """Called before another spectrum of the file is shown."""
        return self.confirm_discard()

    def spectrum_shown(self, spectrum) -> None:
        """The main window shows `spectrum` (end of ``show_index``)."""
        win = self.win
        if self._incoming is not None:
            session, index = self._incoming
            if win._index == index:
                self._adopt(session)
            self.refresh()
            return
        s = self.session
        if s is not None and self._belongs(s, spectrum, win._index):
            self._sync_energy_calibration(s, spectrum)    # e.g. after Analyze > Energy Calibration
        else:
            self._new_session(spectrum)
        self.refresh()

    def _new_session(self, spectrum) -> None:
        from ..lab.session import AnalysisSession
        win = self.win
        path = getattr(win, "_path", None)
        if spectrum is None or path is None or not Path(path).is_file():
            self._set(None)
            return
        fmt = getattr(win, "_fmt", None)
        try:
            s = AnalysisSession.for_spectrum(path, spectrum, index=win._index, fmt=fmt.key if fmt else "")
            if spectrum.energy_coeffs:
                s.set_calibration(_energy_record(spectrum, "imported"),
                                  reason="energy calibration of the spectrum file")
        except Exception as exc:                 # unreadable for hashing: no session, never a crash
            self._set(None)
            self._status(wtr("session_not_updated", msg=f"{type(exc).__name__}: {exc}"))
            return
        self._set(s)

    def _sync_energy_calibration(self, s, spectrum) -> None:
        """Record a changed energy calibration (marks stored results as requiring an update)."""
        energy = [c for c in s.calibrations if c.get("kind") == "energy"]
        old = energy[-1].get("params") if energy else []
        if _same_coeffs(old, spectrum.energy_coeffs):
            return
        cals = [c for c in s.calibrations if c.get("kind") != "energy"]
        if spectrum.energy_coeffs:
            cals.append(_energy_record(spectrum, "measured").to_dict())
        s.edit("set_context", ["calibrations"], cals, reason="energy calibration changed")

    # ------------------------------------------------------------ results
    def analysis_done(self, spectrum, peaks, matches, application: Optional[str]) -> None:
        """Peak search + identification of the displayed spectrum finished."""
        s = self.session_for(spectrum)
        if s is None:
            return
        quant = self.kept_quant(s)
        if application:
            s.processing_settings = {**(s.processing_settings or {}), "identification_library": application}
        try:
            try:
                s.set_results(peaks, matches, quant, spectrum=spectrum)
            except ValueError:                   # a match refers to a peak not in the list
                s.set_results(peaks, (), quant, spectrum=spectrum)
        except Exception as exc:
            self._status(wtr("session_not_updated", msg=f"{type(exc).__name__}: {exc}"))
            return
        self.win.fit_session = s
        self.refresh()

    def activity_calculated(self, dialog) -> None:
        """The activity dialog computed `dialog.results` for the displayed spectrum: record its
        efficiency calibration, sample geometry, sample information and background, then the
        activities.  Staleness of the peaks / identification is kept (only a new analysis clears it)."""
        s = self.session_for(dialog.spectrum)
        if s is None or dialog.results is None:
            return
        # reasons the peaks / identification already require an update (before the edits below)
        stale = list(s.status.get("stale_reasons", [])) if s.status.get("results_stale") else []
        try:
            from ..lab.calibration import CalibrationRecord
            from ..lab.session import quant_to_dict
            rec = getattr(dialog, "curve_record", None)
            curve = getattr(dialog, "curve", None)
            if rec is None and curve is not None:
                rec = CalibrationRecord.from_efficiency_curve(curve, source="imported")
            if rec is not None:
                cals = [c for c in s.calibrations if c.get("kind") != "efficiency"] + [rec.to_dict()]
                s.edit("set_context", ["calibrations"], cals, reason="efficiency calibration used for the activities")
            geo = dialog.sample_geometry()
            if geo is not None:
                s.set_geometry(geo, reason="sample geometry of the activity calculation")
            if dialog.sample_info is not None:
                s.set_sample(dialog.sample_info, reason="sample information of the activity calculation")
            bkg = dialog.background
            if bkg is not None and bkg.source_path and Path(bkg.source_path).is_file():
                s.set_background(bkg.source_path, live_time=bkg.live_time,
                                 reason=f"measured background ({dialog.bkg_mode.currentData()} mode)")
            res = s.results or {}
            s.set_results(res.get("peaks", []), res.get("nuclide_matches", []), quant_to_dict(dialog.results),
                          spectrum=dialog.spectrum)
            for r in stale:                      # identification still requires an update
                s.mark_stale(r)
        except Exception as exc:                 # the dialog's results are never blocked
            self._status(wtr("session_not_updated", msg=f"{type(exc).__name__}: {exc}"))
            return
        self.concentration_session = s.session_id
        self.refresh()

    def changed(self) -> None:
        """Something edited the session elsewhere (fit inspection, undo / redo)."""
        self.refresh()

    # ------------------------------------------------------------ open / save (A5)
    def open_session(self, path=None) -> bool:
        from ..lab.common import counts_fingerprint
        from ..lab.session import AnalysisSession, SessionSchemaError
        win = self.win
        if not self.confirm_discard():
            return False
        if path is None:
            path = self.ask_open_path()
            if not path:
                return False
        path = Path(path)
        try:
            s = AnalysisSession.load(path)
        except SessionSchemaError as exc:
            win.show_error(wtr("err_schema", path=i18n.bidi_path(path), msg=str(exc)))
            return False
        except Exception as exc:
            win.show_error(wtr("err_open", path=i18n.bidi_path(path), msg=f"{type(exc).__name__}: {exc}"))
            return False
        ref = s.spectrum_ref or {}
        if not ref.get("path"):
            win.show_error(wtr("err_no_spectrum_ref", path=i18n.bidi_path(path)))
            return False
        notes = []
        if not ref.get("sha256"):                # legacy session: nothing to verify against
            if not Path(ref["path"]).is_file() and not self._locate(s, "ask_missing"):
                return False
            notes.append(wtr("status_unverified", path=i18n.bidi_path(s.spectrum_ref["path"])))
        else:
            res = s.resolve_spectrum([path.parent])
            if res.status == "relocated":
                notes.append(wtr("status_relocated", path=i18n.bidi_path(res.path)))
            elif res.status in ("missing", "modified"):
                if not self._locate(s, "ask_" + res.status):
                    return False
                notes.append(wtr("status_relocated", path=i18n.bidi_path(s.spectrum_ref["path"])))
        spath = Path(s.spectrum_ref["path"])
        fmt = None
        try:
            from ..formats import get_format
            fmt = get_format(ref.get("format")) if ref.get("format") else None
        except Exception:
            fmt = None
        from ..convert import read_spectra
        try:
            spectra, used = read_spectra(spath, fmt if fmt is not None and fmt.can_read else None)
        except Exception as exc:
            win.show_error(wtr("err_read", path=i18n.bidi_path(spath), msg=f"{type(exc).__name__}: {exc}"))
            return False
        index = int(ref.get("index") or 0)
        if not 0 <= index < len(spectra):
            win.show_error(wtr("err_index", path=i18n.bidi_path(spath), n=i18n.ltr(index + 1)))
            return False
        spec = spectra[index]
        want = ref.get("counts_sha256")
        if want and counts_fingerprint(spec.counts) != want:
            win.show_error(wtr("err_counts", path=i18n.bidi_path(spath)))
            return False
        energy = [c for c in s.calibrations if c.get("kind") == "energy"]
        if energy and not _same_coeffs(energy[-1].get("params"), spec.energy_coeffs):
            spec = copy.deepcopy(spec)          # the session's energy calibration, counts untouched
            spec.energy_coeffs = [float(v) for v in energy[-1]["params"]]
            spec.source_path = spec.source_path or str(spath)
            spectra[index] = spec
        reasons = s.is_stale_against()          # stored results are displayed, never recalculated
        for r in reasons:
            if r not in s.status.get("stale_reasons", []):
                s.mark_stale(r)
        self._incoming = (s, index)
        try:
            self._set(None)
            win.display(spectra, used, spath)
            if win._index != index:
                win.show_index(index)
        finally:
            self._incoming = None
        self.path = path
        self._saved = _state(s)
        if getattr(win, "settings", None) is not None:
            win.settings.set_folder("session", path)
        self.refresh()
        self._status("  ".join([wtr("status_opened", path=i18n.bidi_path(path))] + notes), 15000)
        if s.status.get("results_stale"):
            win.show_info(wtr("opened_stale", reasons="\n".join("• " + r for r in s.status.get("stale_reasons", []))))
        return True

    def _locate(self, s, question: str) -> bool:
        """Ask for the spectrum file; accepted only when its SHA-256 is the recorded one."""
        from ..lab.common import file_sha256
        old = s.spectrum_ref["path"]
        if not self.confirm(wtr("locate_title"), wtr(question, path=i18n.bidi_path(old))):
            return False
        chosen = self.ask_spectrum_file(old)
        if not chosen:
            return False
        chosen = Path(chosen).resolve()
        want = s.spectrum_ref.get("sha256")
        if want and file_sha256(chosen) != want:
            self.win.show_error(wtr("err_fingerprint"))
            return False
        s.edit("relocate_spectrum", ["spectrum_ref", "path"], str(chosen),
               reason=f"located by the user at {chosen}" + (" (SHA-256 verified)" if want else " (not verifiable)"))
        return True

    def _adopt(self, s) -> None:
        """Show a session that is being opened: its stored results as they are."""
        win = self.win
        self._set(s)
        win.fit_session = s if s.has_results() else None
        win.quant_results = None                 # activity results of another spectrum
        win.quant_concentration = None
        if not s.has_results():
            return
        try:
            peaks, matches = results_to_objects(s.results)
        except Exception as exc:
            win.analysis_panel.show_message(wtr("results_unreadable", msg=f"{type(exc).__name__}: {exc}"))
            return
        spec = win.current_spectrum()
        win.analysis_panel.set_results(peaks, matches, bool(spec is not None and spec.energy_coeffs),
                                       (s.processing_settings or {}).get("identification_library"))
        win.analysis_panel.show_message(wtr("banner_stale" if s.status.get("results_stale") else "banner_stored"))
        win.plot.set_peaks(peaks)
        if win.analysis_dock.isHidden():
            win.analysis_dock.show()

    def ask_open_path(self) -> Optional[str]:
        st = self._settings()
        path, _ = QFileDialog.getOpenFileName(self.win, wtr("fd_open"), st.folder("session") if st else "",
                                              wtr("fd_filter"))
        return path or None

    def ask_save_path(self, default: Path) -> Optional[str]:
        path, _ = QFileDialog.getSaveFileName(self.win, wtr("fd_save"), str(default), wtr("fd_filter"))
        return path or None

    def ask_spectrum_file(self, old_path: str) -> Optional[str]:
        st = self._settings()
        path, _ = QFileDialog.getOpenFileName(self.win, wtr("fd_locate", name=Path(old_path).name),
                                              st.folder("open") if st else "")
        return path or None

    def save_session(self, save_as: bool = False) -> bool:
        s = self.session
        if s is None:
            self.win.show_info(wtr("no_session"))
            return False
        path = self.path
        if save_as or path is None:
            st = self._settings()
            folder = Path(st.folder("session")) if st else Path.cwd()
            default = folder / (Path(s.spectrum_ref.get("path") or "session").stem + SESSION_EXT)
            path = self.ask_save_path(self.path or default)
            if not path:
                return False
            path = Path(path)
            if not path.suffix:
                path = path.with_suffix(SESSION_EXT)
        return self.save_session_to(path)

    def save_session_to(self, path) -> bool:
        s = self.session
        if s is None:
            return False
        try:
            out = s.save(path)
        except Exception as exc:
            self.win.show_error(wtr("err_save", path=i18n.bidi_path(path), msg=f"{type(exc).__name__}: {exc}"))
            return False
        self.path, self._saved = out, _state(s)
        if self._settings() is not None:
            self.win.settings.set_folder("session", out)
        self.refresh()
        self._status(wtr("status_saved", path=i18n.bidi_path(out)))
        return True

    # ------------------------------------------------------------ review (F3b)
    def ask_review(self, reviewer: str) -> Optional[tuple[str, str]]:
        dlg = ReviewDialog(self.win, reviewer)
        if dlg.exec() != QDialog.Accepted:
            return None
        return dlg.name_edit.text(), dlg.note_edit.toPlainText().strip()

    @staticmethod
    def review_error_text(exc: Exception) -> str:
        msg = str(exc)
        for needle, key in (("reviewer's name is required", "review_err_name"),
                            ("no results to review", "review_err_no_results"),
                            ("require recalculation", "review_err_stale")):
            if needle in msg:
                return wtr(key)
        return wtr("review_err", msg=msg)

    def review(self) -> bool:
        from ..lab.workflow import mark_reviewed
        win, s = self.win, self.session
        if s is None:
            win.show_info(wtr("no_session"))
            return False
        if not s.has_results() or s.status.get("results_stale"):     # refused before asking
            win.show_error(wtr("review_err_no_results" if not s.has_results() else "review_err_stale"))
            return False
        st = self._settings()
        ans = self.ask_review(str(st.get(REVIEWER_KEY, "") or "") if st else "")
        if ans is None:
            return False
        name, note = ans
        try:
            mark_reviewed(s, name, note)
        except ValueError as exc:
            win.show_error(self.review_error_text(exc))
            return False
        if st is not None:
            st.set(REVIEWER_KEY, name.strip())
        self.refresh()
        self._status(wtr("review_done", who=name.strip()))
        return True

    # ------------------------------------------------------------ report record (F3c)
    def concentrations(self) -> Optional[dict]:
        """The activity dialog's concentrations when they belong to the current session."""
        s = self.session
        if s is None or self.concentration_session != s.session_id:
            return None
        return getattr(self.win, "quant_concentration", None)

    def spectrum(self):
        s, win = self.session, self.win
        spec = win.current_spectrum() if s is not None else None
        return spec if spec is not None and self._belongs(s, spec, win._index) else None

    def export_report(self, path=None) -> Optional[Path]:
        from ..lab.workflow import WorkflowStatus, report_record, write_report_json
        win, s = self.win, self.session
        if s is None:
            win.show_info(wtr("no_session"))
            return None
        conc, spec = self.concentrations(), self.spectrum()
        try:
            rec = report_record(s, conc, spec)
        except Exception as exc:
            win.show_error(wtr("report_err", path="", msg=f"{type(exc).__name__}: {exc}"))
            return None
        if not rec.get("reportable", False):
            errors = [status_text(WorkflowStatus(**x)) for x in rec.get("statuses", []) if x.get("level") == "error"]
            if not self.confirm(wtr("report_not_reportable_title"),
                                wtr("report_not_reportable", errors="\n".join("• " + e for e in errors))):
                return None
        if path is None:
            st = self._settings()
            folder = Path(st.folder("export")) if st else Path.cwd()
            stem = Path(s.spectrum_ref.get("path") or "session").stem
            path, _ = QFileDialog.getSaveFileName(win, wtr("fd_report"), str(folder / f"{stem}_report.json"),
                                                  wtr("fd_report_filter"))
            if not path:
                return None
        try:
            out = write_report_json(path, s, conc, spec)
        except Exception as exc:
            win.show_error(wtr("report_err", path=i18n.bidi_path(path), msg=f"{type(exc).__name__}: {exc}"))
            return None
        if self._settings() is not None:
            win.settings.set_folder("export", out)
        self._status(wtr("report_written", path=i18n.bidi_path(out)))
        return out

    # ------------------------------------------------------------ display
    def statuses(self) -> list:
        from ..lab.workflow import WorkflowStatus, workflow_status
        if self.session is None:
            return []
        try:
            # as in the report record: a missing efficiency calibration is an error only once
            # activities are part of the work; for identification alone it is information
            quant = bool((self.session.results or {}).get("quant"))
            out = workflow_status(self.session, self.spectrum(), needs_activity=quant)
            if not quant and not any(c.get("kind") == "efficiency" for c in self.session.calibrations or []):
                out.insert(0, WorkflowStatus("calibration_required", "info",
                                             "no efficiency calibration recorded: activities cannot be reported"))
            return out
        except Exception as exc:                 # engine error -> a visible status, never a crash
            return [WorkflowStatus("engine_error", "warning",
                                   wtr("panel_engine_error", msg=f"{type(exc).__name__}: {exc}"))]

    def header_text(self) -> str:
        if self.session is None:
            return wtr("panel_none")
        text = wtr("panel_file", name=i18n.bidi_path(self.path.name)) if self.path else wtr("panel_new")
        return wtr("panel_modified", text=text) if self.path is not None and self.is_dirty() else text

    def refresh(self) -> None:
        self.panel.show_statuses(self.statuses(), self.header_text(),
                                 wtr("panel_no_spectrum") if self.session is None else "")
        update_actions(self.win)


# ===================================================================== main-window hooks
def install_session_io(win) -> None:
    """File > Open / Save / Save As session and Export Report Record (JSON); Analyze > Mark as
    Reviewed... and Batch Analysis...; the workflow dock (View menu).  Sets ``win.session_ctl``
    and ``win.session``."""
    win.session = None
    ctl = SessionController(win)
    win.session_ctl = ctl
    win.act_open_session = QAction(win)
    win.act_open_session.triggered.connect(lambda _=False: ctl.open_session())
    win.act_save_session = QAction(win)
    win.act_save_session.triggered.connect(lambda _=False: ctl.save_session())
    win.act_save_session_as = QAction(win)
    win.act_save_session_as.triggered.connect(lambda _=False: ctl.save_session(save_as=True))
    win.act_report_json = QAction(win)
    win.act_report_json.triggered.connect(lambda _=False: ctl.export_report())
    win.act_review = QAction(win)
    win.act_review.triggered.connect(lambda _=False: ctl.review())
    win.act_batch_analysis = QAction(win)
    win.act_batch_analysis.triggered.connect(lambda _=False: open_batch_analysis(win))
    for name in ("act_open_session", "act_save_session", "act_save_session_as", "act_report_json", "act_review",
                 "act_batch_analysis"):
        getattr(win, name).setObjectName(name)

    menu = getattr(win, "menu_file", None)
    if menu is not None:
        before = getattr(win, "act_folder", None)
        for a in (win.act_open_session, win.act_save_session, win.act_save_session_as):
            menu.insertAction(before, a)
        menu.insertSeparator(before)
        exit_ = getattr(win, "act_exit", None)
        menu.insertAction(exit_, win.act_report_json)
        menu.insertSeparator(exit_)
    menu = getattr(win, "menu_analyze", None)
    if menu is not None:
        menu.addSeparator()
        menu.addAction(win.act_review)
        menu.addAction(win.act_batch_analysis)

    win.workflow_dock = QDockWidget()
    win.workflow_dock.setObjectName("workflowDock")
    win.workflow_dock.setWidget(ctl.panel)
    win.workflow_dock.setAllowedAreas(Qt.RightDockWidgetArea | Qt.LeftDockWidgetArea | Qt.BottomDockWidgetArea)
    win.addDockWidget(Qt.RightDockWidgetArea, win.workflow_dock)
    menu = getattr(win, "menu_view", None)
    if menu is not None:
        menu.insertAction(getattr(win, "act_clear_rois", None), win.workflow_dock.toggleViewAction())
    win._analysis_batch_dialogs = []
    retranslate_session_io(win)


def retranslate_session_io(win) -> None:
    for name, k in (("act_open_session", "open_session"), ("act_save_session", "save_session"),
                    ("act_save_session_as", "save_session_as"), ("act_report_json", "report_json"),
                    ("act_review", "review"), ("act_batch_analysis", "batch")):
        a = getattr(win, name, None)
        if a is not None:
            a.setText(wtr("act_" + k))
            a.setToolTip(wtr("tip_" + k))
            a.setStatusTip(wtr("tip_" + k))
    dock = getattr(win, "workflow_dock", None)
    if dock is not None:
        dock.setWindowTitle(wtr("dock"))
        dock.toggleViewAction().setText(wtr("act_dock"))
    ctl = getattr(win, "session_ctl", None)
    if ctl is not None:
        ctl.refresh()


def update_actions(win) -> None:
    ctl = getattr(win, "session_ctl", None)
    if ctl is None or not hasattr(win, "act_review"):
        return
    s = ctl.session
    has = s is not None
    win.act_save_session.setEnabled(has)
    win.act_save_session_as.setEnabled(has)
    win.act_report_json.setEnabled(has)
    stale = bool(has and s.status.get("results_stale"))
    win.act_review.setEnabled(bool(has and s.has_results() and not stale))
    tip = wtr("tip_review_stale") if stale else wtr("tip_review")
    win.act_review.setToolTip(tip)
    win.act_review.setStatusTip(tip)


def open_batch_analysis(win, show: bool = True):
    from .batch_analysis import BatchAnalysisDialog
    dlg = BatchAnalysisDialog(win, getattr(win, "settings", None))
    dlg.setAttribute(Qt.WA_DeleteOnClose)
    keep = win.__dict__.setdefault("_analysis_batch_dialogs", [])
    keep.append(dlg)
    dlg.destroyed.connect(lambda *_: keep.remove(dlg) if dlg in keep else None)
    if show:
        dlg.show()
    return dlg


__all__ = ["SessionController", "WorkflowPanel", "ReviewDialog", "status_text", "code_title",
           "results_to_objects", "install_session_io", "retranslate_session_io", "open_batch_analysis",
           "SESSION_EXT"]
