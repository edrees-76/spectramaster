"""Arabic texts for Qt's own widgets (standard buttons, file dialog, context menus).

PySide6 ships only a stub ``qt_ar.qm`` (it refers to ``qtbase_ar.qm``, which is
not included), so Qt's built-in strings -- "OK", "Cancel", "Look in:",
"Copy" ... -- would stay English in the Arabic UI.  :class:`QtArabicTranslator`
is a small in-memory translator for the strings users actually meet.
"""
from __future__ import annotations

from PySide6.QtCore import QCoreApplication, QLibraryInfo, QTranslator

_BUTTONS = {
    "OK": "موافق", "Save": "حفظ", "Save All": "حفظ الكل", "Open": "فتح", "&Yes": "&نعم",
    "Yes to &All": "نعم &للكل", "&No": "&لا", "N&o to All": "لا لل&كل", "Abort": "إجهاض",
    "Retry": "إعادة المحاولة", "Ignore": "تجاهل", "Close": "إغلاق", "Cancel": "إلغاء",
    "Discard": "تجاهل التغييرات", "Help": "مساعدة", "Apply": "تطبيق", "Reset": "إعادة تعيين",
    "Restore Defaults": "استعادة الافتراضيات", "Yes": "نعم", "No": "لا",
}
_EDIT = {
    "&Undo": "ترا&جع", "&Redo": "إ&عادة", "Cu&t": "&قص", "&Copy": "&نسخ", "&Paste": "ل&صق",
    "Delete": "حذف", "Select All": "تحديد الكل", "Copy &Link Location": "نسخ &موقع الرابط",
}
_FILE_DIALOG = {
    "Look in:": "البحث في:", "File &name:": "&اسم الملف:", "Files of type:": "نوع الملفات:",
    "Look &in:": "ال&بحث في:", "&Look in:": "ال&بحث في:", "Files of &type:": "&نوع الملفات:",
    "&Open": "&فتح", "&Save": "&حفظ", "&Choose": "ا&ختيار", "Open": "فتح", "Save As": "حفظ باسم",
    "Back": "رجوع", "Forward": "تقدم", "Parent Directory": "المجلد الأعلى",
    "Create New Folder": "إنشاء مجلد جديد", "New Folder": "مجلد جديد", "List View": "عرض القائمة",
    "Detail View": "عرض التفاصيل", "My Computer": "جهاز الكمبيوتر", "Computer": "الكمبيوتر",
    "Recent Places": "الأماكن الأخيرة", "Directory:": "المجلد:", "File Folder": "مجلد ملفات",
    "Folder": "مجلد", "Find Directory": "البحث عن مجلد", "Directories": "المجلدات",
    "All Files (*)": "كل الملفات (*)", "&Rename": "إعادة ت&سمية", "&Delete": "&حذف",
    "Show &hidden files": "إظهار الملفات الم&خفية", "&New Folder": "مجلد &جديد",
    "Go back": "رجوع", "Go forward": "تقدم", "Go to the parent directory": "الانتقال إلى المجلد الأعلى",
    "Create a New Folder": "إنشاء مجلد جديد", "Change to list view mode": "التبديل إلى عرض القائمة",
    "Change to detail view mode": "التبديل إلى عرض التفاصيل", "Sidebar": "الشريط الجانبي",
    "Are you sure you want to delete '%1'?": "هل تريد بالتأكيد حذف '%1'؟",
}
_FS_MODEL = {"Name": "الاسم", "Size": "الحجم", "Type": "النوع", "Date Modified": "تاريخ التعديل",
             "Kind": "النوع", "My Computer": "جهاز الكمبيوتر", "Computer": "الكمبيوتر"}

TABLE: dict[str, dict[str, str]] = {
    "QPlatformTheme": _BUTTONS,
    "QDialogButtonBox": _BUTTONS,
    "QMessageBox": {**_BUTTONS, "Show Details...": "إظهار التفاصيل...", "Hide Details...": "إخفاء التفاصيل..."},
    "QLineEdit": _EDIT,
    "QWidgetTextControl": _EDIT,
    "QTextControl": _EDIT,
    "QFileDialog": _FILE_DIALOG,
    "QFileSystemModel": _FS_MODEL,
    "QFileInfoGatherer": _FS_MODEL,
    "QAbstractSpinBox": {"&Select All": "&تحديد الكل", "&Step up": "&زيادة", "Step &down": "إ&نقاص"},
    "QWizard": {"< &Back": "< ال&سابق", "&Next >": "ال&تالي >", "&Finish": "إ&نهاء", "Cancel": "إلغاء"},
    "QColorDialog": {"Select Color": "اختيار اللون"},
    "QPrintDialog": {"Print": "طباعة"},
    "QPrintPreviewDialog": {"Print Preview": "معاينة الطباعة", "Print": "طباعة", "Close": "إغلاق"},
}


class QtArabicTranslator(QTranslator):
    """In-memory Arabic catalogue for Qt's own strings (None = untranslated)."""

    def translate(self, context, source_text, disambiguation=None, n=-1):  # noqa: D401 (Qt override)
        ctx = context.decode() if isinstance(context, (bytes, bytearray)) else (context or "")
        src = source_text.decode() if isinstance(source_text, (bytes, bytearray)) else (source_text or "")
        # None -> null QString = "not translated"; an empty (non-null) string would *replace* every
        # unknown Qt string with nothing
        return TABLE.get(ctx, {}).get(src)

    def isEmpty(self) -> bool:  # noqa: N802 (Qt API)
        return False


_installed: list[QTranslator] = []


def install(lang: str) -> bool:
    """Install the Qt-strings translator for ``lang`` (removes a previous one). True if active."""
    app = QCoreApplication.instance()
    if app is None:
        return False
    for t in _installed:
        app.removeTranslator(t)
    _installed.clear()
    if lang != "ar":
        return False
    # a real catalogue first, should a later PySide6 ship qtbase_ar.qm
    real = QTranslator(app)
    if real.load("qtbase_ar", QLibraryInfo.path(QLibraryInfo.TranslationsPath)):
        app.installTranslator(real)
        _installed.append(real)
    t = QtArabicTranslator(app)
    app.installTranslator(t)
    _installed.append(t)
    return True
