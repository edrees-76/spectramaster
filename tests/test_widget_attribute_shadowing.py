"""No GUI class assigns an instance attribute over a Qt method of its widget base class.

`SampleDescriptionDialog.geometry = QLineEdit(...)` hid `QWidget.geometry()`; since the dialogs are
fitted to the screen when first shown (window_buttons.fit_to_screen), that raised in the event
filter and the dialog was not fitted (F5 Sample Description, the calibration ID dialog and the
efficiency points dialog)."""
from __future__ import annotations

import ast
import os
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
pytest.importorskip("PySide6")

from PySide6 import QtWidgets  # noqa: E402

GUI = Path(__file__).resolve().parents[1] / "spectramaster" / "gui"


def _qt_base(bases, local):
    """The first Qt widget class among the (possibly local) base class names, or None."""
    for b in bases:
        name = b.id if isinstance(b, ast.Name) else b.attr if isinstance(b, ast.Attribute) else None
        if name in local:
            found = _qt_base(local[name], local)
            if found is not None:
                return found
        cls = getattr(QtWidgets, name or "", None)
        if isinstance(cls, type) and issubclass(cls, QtWidgets.QWidget):
            return cls
    return None


def _shadowing(path: Path) -> list[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    local = {n.name: n.bases for n in ast.walk(tree) if isinstance(n, ast.ClassDef)}
    found = []
    for cls in (n for n in ast.walk(tree) if isinstance(n, ast.ClassDef)):
        base = _qt_base(cls.bases, local)
        if base is None:
            continue
        for node in ast.walk(cls):
            targets = node.targets if isinstance(node, ast.Assign) else [node.target] \
                if isinstance(node, (ast.AnnAssign, ast.AugAssign)) else []
            for t in targets:
                for e in (t.elts if isinstance(t, ast.Tuple) else [t]):
                    if isinstance(e, ast.Attribute) and isinstance(e.value, ast.Name) and e.value.id == "self" \
                            and callable(getattr(base, e.attr, None)):
                        found.append(f"{path.name}:{node.lineno} {cls.name}.{e.attr} hides {base.__name__}.{e.attr}()")
    return found


def test_no_gui_class_hides_a_qt_method():
    found = [f for p in sorted(GUI.glob("*.py")) for f in _shadowing(p)]
    assert found == []


def test_the_fixed_dialogs_are_fitted_when_shown():
    from datetime import datetime

    from spectramaster.gui.aptec_calibration_ui import IdDialog
    from spectramaster.gui.aptec_edit_ui import SampleDescriptionDialog
    from spectramaster.gui.app import create_app
    from spectramaster.gui.window_buttons import _FITTED
    from spectramaster.model import Spectrum
    create_app(["test"])
    spec = Spectrum(counts=[1.0] * 64, live_time=10.0, real_time=10.0, start_time=datetime(2024, 1, 1),
                    extra={"geometry_id": "Marinelli-1L"})
    for dlg in (SampleDescriptionDialog(spec, None), IdDialog(None, "keV", "HPGe-1", "Marinelli-1L")):
        dlg.show()
        QtWidgets.QApplication.processEvents()
        assert dlg.property(_FITTED) and dlg.geometry().width() > 0
        dlg.close()
