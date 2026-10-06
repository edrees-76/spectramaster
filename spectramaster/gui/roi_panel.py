"""Dock widget listing the regions of interest drawn on the plot."""
from __future__ import annotations

import csv
from pathlib import Path
from typing import Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import (QAbstractItemView, QHBoxLayout, QHeaderView, QLabel, QPushButton,
                               QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget)

from .i18n import tr
from .plot import SpectrumPlot, format_count

COLS = ["roi_col_n", "roi_col_start", "roi_col_end", "roi_col_centroid", "roi_col_energy",
        "roi_col_fwhm", "roi_col_fwhm_kev", "roi_col_gross", "roi_col_net", "roi_col_unc",
        "roi_col_cps"]


def _f(v, fmt="{:.2f}") -> str:
    return "" if v is None else fmt.format(v)


def roi_rows(plot: SpectrumPlot) -> list[list[str]]:
    rows = []
    for i, roi in enumerate(plot.rois):
        st = roi.stats
        if st is None:
            continue
        cps = "" if st.count_rate is None else "\u2066" + f"{st.count_rate:.4g} ± {st.count_rate_unc:.2g}" + "\u2069"
        rows.append([str(i + 1), str(st.start_channel), str(st.end_channel), _f(st.centroid),
                     _f(st.centroid_energy), _f(st.fwhm), _f(st.fwhm_kev), f"{st.gross:.0f}",
                     f"{st.net:.1f}", f"{st.net_unc:.1f}", cps])
    return rows


def export_rois_csv(plot: SpectrumPlot, path) -> Path:
    path = Path(path)
    spec = plot.spectrum()
    with path.open("w", newline="", encoding="utf-8-sig") as fh:
        w = csv.writer(fh)
        if spec is not None:
            w.writerow(["# file", spec.source_path])
            w.writerow(["# sample_id", spec.sample_id])
            w.writerow(["# live_time_s", spec.live_time if spec.live_time is not None else ""])
            w.writerow(["# real_time_s", spec.real_time if spec.real_time is not None else ""])
        w.writerow(["roi", "start_ch", "end_ch", "centroid_ch", "centroid_keV", "fwhm_ch", "fwhm_keV",
                    "gross", "background", "net", "net_unc_1s", "net_cps", "net_cps_unc"])
        for i, roi in enumerate(plot.rois):
            st = roi.stats
            if st is None:
                continue
            w.writerow([i + 1, st.start_channel, st.end_channel, _f(st.centroid, "{:.4f}"),
                        _f(st.centroid_energy, "{:.4f}"), _f(st.fwhm, "{:.4f}"), _f(st.fwhm_kev, "{:.4f}"),
                        f"{st.gross:.0f}", f"{st.background:.3f}", f"{st.net:.3f}", f"{st.net_unc:.3f}",
                        _f(st.count_rate, "{:.6g}"), _f(st.count_rate_unc, "{:.6g}")])
    return path


class RoiPanel(QWidget):
    exportRequested = Signal()

    def __init__(self, plot: SpectrumPlot, parent=None):
        super().__init__(parent)
        self.plot = plot
        lay = QVBoxLayout(self)
        lay.setContentsMargins(6, 4, 6, 6)
        self.hint = QLabel()
        self.hint.setObjectName("infoLabel")
        self.hint.setWordWrap(True)
        lay.addWidget(self.hint)
        self.table = QTableWidget(0, len(COLS))
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.verticalHeader().setVisible(False)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setStretchLastSection(False)
        self.table.setAlternatingRowColors(True)
        self.table.doubleClicked.connect(self._zoom_row)
        lay.addWidget(self.table, 1)
        btns = QHBoxLayout()
        self.del_btn = QPushButton()
        self.del_btn.clicked.connect(self.delete_selected)
        self.clear_btn = QPushButton()
        self.clear_btn.clicked.connect(self.plot.clear_rois)
        self.export_btn = QPushButton()
        self.export_btn.clicked.connect(self.exportRequested.emit)
        btns.addWidget(self.del_btn)
        btns.addWidget(self.clear_btn)
        btns.addStretch(1)
        btns.addWidget(self.export_btn)
        lay.addLayout(btns)
        sc = QShortcut(QKeySequence.Delete, self.table)
        sc.setContext(Qt.WidgetShortcut)
        sc.activated.connect(self.delete_selected)
        plot.roisChanged.connect(self.refresh)
        self.retranslate()

    def retranslate(self) -> None:
        self.table.setHorizontalHeaderLabels([tr(k) for k in COLS])
        self.hint.setText(tr("roi_hint"))
        self.del_btn.setText(tr("roi_delete"))
        self.clear_btn.setText(tr("roi_clear"))
        self.export_btn.setText(tr("roi_export"))
        self.refresh()

    def refresh(self) -> None:
        rows = roi_rows(self.plot)
        self.table.setRowCount(len(rows))
        for r, row in enumerate(rows):
            for c, text in enumerate(row):
                it = QTableWidgetItem(text)
                it.setTextAlignment(Qt.AlignAbsolute | Qt.AlignRight | Qt.AlignVCenter)
                self.table.setItem(r, c, it)
        has = bool(rows)
        self.del_btn.setEnabled(has)
        self.clear_btn.setEnabled(has)
        self.export_btn.setEnabled(has)

    def select_row(self, r: int) -> None:
        from PySide6.QtCore import QItemSelectionModel
        idx = self.table.model().index(r, 0)
        self.table.selectionModel().select(idx, QItemSelectionModel.ClearAndSelect | QItemSelectionModel.Rows)

    def selected_rows(self) -> list[int]:
        return sorted({i.row() for i in self.table.selectedIndexes()}, reverse=True)

    def delete_selected(self) -> None:
        for r in self.selected_rows():
            self.plot.remove_roi(r)

    def _zoom_row(self, index) -> None:
        r = index.row()
        if 0 <= r < len(self.plot.rois):
            roi = self.plot.rois[r]
            w = roi.right - roi.left + 1
            self.plot.set_view(roi.left - w, roi.right + 1 + w, None)
