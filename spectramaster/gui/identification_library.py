"""Identification library choice (application libraries of ``analysis.library.APPLICATIONS``)
and the GUI texts of the identification results (calibration-drift note).

The engine default stays "all"; the GUI default is "environmental" (soil, water, food and air
laboratory) and is shown in the analysis results header.  The choice is persisted in the
settings under ``SETTINGS_KEY``.
"""
from __future__ import annotations

import re
from typing import Optional

from . import i18n

SETTINGS_KEY = "analysis/library"
GUI_DEFAULT = "environmental"
# display order (the recommended one first)
CHOICES = ("environmental", "all", "calibration", "safeguards", "medical")
DRIFT_PREFIX = "calibration drift detected"

EN = {
    "idl_label": "Identification library:",
    "idl_tip": "Nuclides searched during identification.  Restricting the candidates to the kind of "
               "work avoids coincidental matches (Environmental is recommended for soil, water, food "
               "and air samples).",
    "idl_environmental": "Environmental (soil, water, food, air) - recommended",
    "idl_all": "All nuclides (complete library)",
    "idl_calibration": "Calibration sources",
    "idl_safeguards": "Safeguards (uranium, plutonium)",
    "idl_medical": "Medical isotopes",
    "idl_short_environmental": "Environmental",
    "idl_short_all": "All nuclides",
    "idl_short_calibration": "Calibration sources",
    "idl_short_safeguards": "Safeguards",
    "idl_short_medical": "Medical",
    "idl_header": "Library: {name}",
    "idl_rerun": "(another library is selected now: run the analysis again)",
    "idl_drift": "Calibration drift detected ({detail}): peak energies were corrected for the "
                 "identification only; the stored energy calibration is unchanged.  Check the energy "
                 "calibration.",
}

AR = {
    "idl_label": "مكتبة التعرف:",
    "idl_tip": "النويدات التي يُبحث عنها أثناء التعرف.  حصر المرشحات في نوع العمل يتجنب التطابقات "
               "العَرَضية (يُوصى بالمكتبة البيئية لعينات التربة والمياه والغذاء والهواء).",
    "idl_environmental": "بيئية (تربة، مياه، غذاء، هواء) - موصى بها",
    "idl_all": "كل النويدات (المكتبة الكاملة)",
    "idl_calibration": "مصادر المعايرة",
    "idl_safeguards": "الضمانات (يورانيوم، بلوتونيوم)",
    "idl_medical": "النظائر الطبية",
    "idl_short_environmental": "بيئية",
    "idl_short_all": "كل النويدات",
    "idl_short_calibration": "مصادر المعايرة",
    "idl_short_safeguards": "الضمانات",
    "idl_short_medical": "طبية",
    "idl_header": "المكتبة: {name}",
    "idl_rerun": "(اختيرت مكتبة أخرى الآن: أعد التحليل)",
    "idl_drift": "اكتُشف انحراف في المعايرة ({detail}): صُحّحت طاقات القمم لأغراض التعرف فقط، "
                 "ولم تتغير معايرة الطاقة المخزنة.  تحقق من معايرة الطاقة.",
}

i18n.STRINGS.setdefault("en", {}).update(EN)
i18n.STRINGS.setdefault("ar", {}).update(AR)


def valid(application) -> bool:
    try:
        from ..analysis.library import APPLICATIONS
    except Exception:                       # engine missing: accept the known names
        return application in CHOICES
    return application in APPLICATIONS


def library_label(application: str, short: bool = False) -> str:
    key = ("idl_short_" if short else "idl_") + application
    return i18n.tr(key) if key in i18n.STRINGS.get("en", {}) else application


def stored_library(settings) -> str:
    """The persisted choice (GUI default "environmental" when nothing valid is stored)."""
    if settings is None:
        return GUI_DEFAULT
    v = str(settings.get(SETTINGS_KEY, GUI_DEFAULT) or GUI_DEFAULT)
    return v if valid(v) else GUI_DEFAULT


def store_library(settings, application: str) -> None:
    if settings is not None and valid(application):
        settings.set(SETTINGS_KEY, application)


def drift_detail(matches) -> Optional[str]:
    """The "(gain ..., offset ...)" part of the drift note of identify(), None without a drift."""
    for m in matches or []:
        note = getattr(m, "note", "") or ""
        i = note.find(DRIFT_PREFIX)
        if i >= 0:
            mo = re.match(r"calibration drift detected\s*\(([^)]*)\)", note[i:])
            return mo.group(1) if mo else ""
    return None


def strip_drift(note: str) -> str:
    """The note without the drift part (shown once above the table instead of on every row)."""
    if DRIFT_PREFIX not in (note or ""):
        return note
    return "; ".join(p for p in note.split("; ") if not p.startswith(DRIFT_PREFIX)
                     and not p.startswith("energies corrected"))


def drift_text(detail: str) -> str:
    return "⚠ " + i18n.tr("idl_drift", detail=i18n.ltr(detail))
