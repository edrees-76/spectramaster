"""English/Arabic strings of the detector registry and picker (D5), the measurement-context bar
of the workflow dock and the laboratory-context section of the printed report, merged into
``i18n.STRINGS`` on import (namespaced with ``ctx_``).  Names, numbers and engine texts are wrapped
by the callers in LTR isolates (:func:`i18n.ltr`)."""
from __future__ import annotations

from . import i18n

EN = {
    # ---- context bar (workflow dock)
    "detector": "Detector:",
    "detector_none": "(not recorded)",
    "detector_session_only": "{name} (session snapshot, not in the registry)",
    "detector_tip": "Detector of this measurement, recorded in the analysis session (an undoable edit; "
                    "existing results are marked as requiring an update).  Efficiency calibrations of "
                    "another detector are then reported as incompatible.",
    "file_label": "Label in the spectrum file: {label}",
    "file_label_none": "Label in the spectrum file: (none)",
    "manage": "Detectors...",
    "manage_tip": "Create, edit or delete detector profiles",
    "geometry": "Geometry:",
    "geometry_none": "(not recorded)",
    "geometry_edit": "Edit...",
    "geometry_tip": "Measurement geometry of the sample, recorded in the analysis session",
    "undo": "Undo",
    "undo_tip": "Undo: {what}",
    "no_session": "(no analysis session)",
    "detector_missing": "The detector profile {name} is no longer in the registry.",
    # ---- registry / manager / editor
    "mgr_title": "Detector Profiles",
    "mgr_intro": "Detector profiles are identified by a permanent id: renaming a detector keeps its "
                 "calibrations and sessions.  Folder: {folder}",
    "mgr_new": "New...",
    "mgr_edit": "Edit...",
    "mgr_delete": "Delete",
    "mgr_close": "Close",
    "mgr_delete_title": "Delete detector profile",
    "mgr_delete_text": "Delete the detector profile {name}?\n\nSessions and calibrations keep their own "
                       "copy of it; it will no longer be offered in the lists.",
    "mgr_problems": "Unreadable files in the folder (ignored): {files}",
    "mgr_err_save": "Cannot save the detector profile:\n{msg}",
    "mgr_shape": "Peak Shape...",
    "mgr_shape_tip": "Measure the low-energy tail of the selected detector's peaks on calibration spectra "
                     "(strong isolated peaks); the analysis of its samples then uses it",
    "shape_pick_title": "Calibration spectra of the detector (strong isolated peaks)",
    "shape_title": "Peak-shape calibration",
    "shape_confirm": "Peak shape measured for {name}:\n\n{result}\n\nRecord it in the detector profile? "
                     "Sessions that use this detector from now on fit its peaks with this shape.",
    "shape_none": "Peak shape: not measured (Gaussian peaks)",
    "shape_gaussian": "Peak shape: Gaussian (no significant tail on {n} peaks)",
    "shape_tail": "Peak shape: low-energy tail {eta}, slope {tau} sigma ({n} peaks)",
    "shape_err_read": "Cannot read the spectra:\n{msg}",
    "shape_err_peaks": "Only {n} strong isolated peak(s) were found; at least {need} are needed. "
                       "Use calibration spectra with strong, well separated peaks.",
    "ed_title": "Detector Profile",
    "ed_name": "Name:",
    "ed_type": "Type:",
    "ed_manufacturer": "Manufacturer:",
    "ed_model": "Model:",
    "ed_serial": "Serial number:",
    "ed_releff": "Relative efficiency (%):",
    "ed_diameter": "Crystal diameter (mm):",
    "ed_length": "Crystal length (mm):",
    "ed_note": "Note:",
    "ed_unknown": "unknown",
    "ed_err_name": "A name is required.",
    "ed_err_number": "Invalid number for {field}: {text}",
    "type_HPGe": "HPGe",
    "type_NaI": "NaI(Tl)",
    "type_LaBr3": "LaBr3(Ce)",
    "type_CZT": "CZT",
    "type_other": "Other",
    # ---- geometry dialog
    "geo_title": "Measurement Geometry of the Sample",
    # ---- efficiency wizard / activity dialog
    "eff_profile": "Detector profile:",
    "eff_profile_tip": "The detector profile the calibration belongs to: its id is stored in the "
                       "calibration record, so a calibration of another detector is recognised.",
    "act_detectors": "Detector: session {session} · calibration {calibration}",
    "act_det_not_chosen": "not chosen",
    "act_det_not_recorded": "not recorded",
    "act_det_unknown": "unknown profile",
    "act_det_mismatch": "The efficiency calibration belongs to another detector: the results will be "
                        "marked as not reportable.",
    # ---- report section
    "rep_title": "Laboratory Context and Workflow Status",
    "rep_library": "Identification library",
    "rep_library_none": "not recorded",
    "rep_detector": "Detector profile",
    "rep_geometry": "Measurement geometry",
    "rep_reportable": "Reportable",
    "rep_reportable_yes": "yes",
    "rep_reportable_no": "no - see the errors below",
    "rep_no_session": "No analysis session belongs to this spectrum: workflow status not available.",
    "rep_statuses": "Workflow status",
    "rep_col_level": "Level",
    "rep_col_status": "Status",
    "rep_col_message": "Details",
    "rep_conc": "Concentrations ({unit})",
    "rep_conc_none": "Concentrations: not computed for this spectrum.",
    "rep_conc_missing": "Missing inputs: {items}",
    "rep_conc_notes": "Notes: {notes}",
    "rep_col_nuclide": "Nuclide",
    "rep_col_result": "Result",
    "rep_col_decision": "Decision",
    "rep_col_factor": "Decay factor",
    "rep_not_recalculated": "Values as computed in the session; nothing is recalculated for the report.",
    "rep_inc": "Laboratory context: library, detector, concentrations, workflow status",
}

AR = {
    # ---- context bar (workflow dock)
    "detector": "الكاشف:",
    "detector_none": "(غير مسجل)",
    "detector_session_only": "{name} (نسخة الجلسة، ليس في السجل)",
    "detector_tip": "كاشف هذا القياس، يُسجَّل في جلسة التحليل (تعديل يمكن التراجع عنه؛ وتُعلَّم النتائج "
                    "الموجودة بأنها تحتاج إلى تحديث).  وعندها تُعدّ معايرات الكفاءة الخاصة بكاشف آخر غير متوافقة.",
    "file_label": "الاسم في ملف الطيف: {label}",
    "file_label_none": "الاسم في ملف الطيف: (لا يوجد)",
    "manage": "الكواشف...",
    "manage_tip": "إنشاء ملفات تعريف الكواشف أو تعديلها أو حذفها",
    "geometry": "الهندسة:",
    "geometry_none": "(غير مسجلة)",
    "geometry_edit": "تعديل...",
    "geometry_tip": "هندسة قياس العينة، تُسجَّل في جلسة التحليل",
    "undo": "تراجع",
    "undo_tip": "تراجع: {what}",
    "no_session": "(لا توجد جلسة تحليل)",
    "detector_missing": "ملف تعريف الكاشف {name} لم يعد موجودًا في السجل.",
    # ---- registry / manager / editor
    "mgr_title": "ملفات تعريف الكواشف",
    "mgr_intro": "يُعرَّف كل كاشف بمعرّف دائم: تغيير اسم الكاشف يحتفظ بمعايراته وجلساته.  المجلد: {folder}",
    "mgr_new": "جديد...",
    "mgr_edit": "تعديل...",
    "mgr_delete": "حذف",
    "mgr_close": "إغلاق",
    "mgr_delete_title": "حذف ملف تعريف الكاشف",
    "mgr_delete_text": "حذف ملف تعريف الكاشف {name}؟\n\nتحتفظ الجلسات والمعايرات بنسختها الخاصة منه؛ "
                       "ولن يُعرض بعد الآن في القوائم.",
    "mgr_problems": "ملفات غير مقروءة في المجلد (تم تجاهلها): {files}",
    "mgr_err_save": "تعذّر حفظ ملف تعريف الكاشف:\n{msg}",
    "mgr_shape": "شكل القمة...",
    "mgr_shape_tip": "قياس ذيل الطاقة المنخفضة لقمم الكاشف المحدد من أطياف معايرة (قمم قوية معزولة)؛ "
                     "يُستخدم بعدها في تحليل عيناته",
    "shape_pick_title": "أطياف معايرة الكاشف (قمم قوية معزولة)",
    "shape_title": "معايرة شكل القمة",
    "shape_confirm": "شكل القمة المقاس للكاشف {name}:\n\n{result}\n\nهل يُسجَّل في ملف الكاشف؟ "
                     "الجلسات التي تستخدم هذا الكاشف من الآن تلائم قممه بهذا الشكل.",
    "shape_none": "شكل القمة: غير مقاس (قمم غاوسية)",
    "shape_gaussian": "شكل القمة: غاوسي (لا ذيل معتبر في {n} قمة)",
    "shape_tail": "شكل القمة: ذيل طاقة منخفضة {eta}، ميل {tau} سيغما ({n} قمة)",
    "shape_err_read": "تعذّرت قراءة الأطياف:\n{msg}",
    "shape_err_peaks": "وُجدت {n} قمة قوية معزولة فقط، والمطلوب {need} على الأقل. "
                       "استخدم أطياف معايرة فيها قمم قوية ومتباعدة.",
    "ed_title": "ملف تعريف الكاشف",
    "ed_name": "الاسم:",
    "ed_type": "النوع:",
    "ed_manufacturer": "الشركة المصنعة:",
    "ed_model": "الطراز:",
    "ed_serial": "الرقم التسلسلي:",
    "ed_releff": "الكفاءة النسبية (%):",
    "ed_diameter": "قطر البلورة (مم):",
    "ed_length": "طول البلورة (مم):",
    "ed_note": "ملاحظة:",
    "ed_unknown": "غير معروف",
    "ed_err_name": "الاسم مطلوب.",
    "ed_err_number": "رقم غير صالح في {field}: {text}",
    "type_HPGe": "HPGe",
    "type_NaI": "NaI(Tl)",
    "type_LaBr3": "LaBr3(Ce)",
    "type_CZT": "CZT",
    "type_other": "آخر",
    # ---- geometry dialog
    "geo_title": "هندسة قياس العينة",
    # ---- efficiency wizard / activity dialog
    "eff_profile": "ملف تعريف الكاشف:",
    "eff_profile_tip": "ملف تعريف الكاشف الذي تخصه المعايرة: يُخزَّن معرّفه في سجل المعايرة، فتُكتشف "
                       "معايرة كاشف آخر.",
    "act_detectors": "الكاشف: الجلسة {session} · المعايرة {calibration}",
    "act_det_not_chosen": "غير مختار",
    "act_det_not_recorded": "غير مسجل",
    "act_det_unknown": "ملف تعريف غير معروف",
    "act_det_mismatch": "معايرة الكفاءة تخص كاشفًا آخر: ستُعلَّم النتائج بأنها غير قابلة للإبلاغ.",
    # ---- report section
    "rep_title": "السياق المخبري وحالة سير العمل",
    "rep_library": "مكتبة التعرف",
    "rep_library_none": "غير مسجلة",
    "rep_detector": "ملف تعريف الكاشف",
    "rep_geometry": "هندسة القياس",
    "rep_reportable": "قابل للإبلاغ",
    "rep_reportable_yes": "نعم",
    "rep_reportable_no": "لا - انظر الأخطاء أدناه",
    "rep_no_session": "لا توجد جلسة تحليل تخص هذا الطيف: حالة سير العمل غير متاحة.",
    "rep_statuses": "حالة سير العمل",
    "rep_col_level": "المستوى",
    "rep_col_status": "الحالة",
    "rep_col_message": "التفاصيل",
    "rep_conc": "التراكيز ({unit})",
    "rep_conc_none": "التراكيز: لم تُحسب لهذا الطيف.",
    "rep_conc_missing": "مدخلات ناقصة: {items}",
    "rep_conc_notes": "ملاحظات: {notes}",
    "rep_col_nuclide": "النويدة",
    "rep_col_result": "النتيجة",
    "rep_col_decision": "القرار",
    "rep_col_factor": "معامل الاضمحلال",
    "rep_not_recalculated": "القيم كما حُسبت في الجلسة؛ لا يُعاد حساب أي شيء للتقرير.",
    "rep_inc": "السياق المخبري: المكتبة، الكاشف، التراكيز، حالة سير العمل",
}

PREFIX = "ctx_"
i18n.STRINGS.setdefault("en", {}).update({PREFIX + k: v for k, v in EN.items()})
i18n.STRINGS.setdefault("ar", {}).update({PREFIX + k: v for k, v in AR.items()})


def ctr(key: str, **kwargs) -> str:
    """``tr`` for the keys above (namespaced with ``ctx_``)."""
    return i18n.tr(PREFIX + key, **kwargs)


def ctr_in(lang, key: str, **kwargs) -> str:
    """``tr_in`` (explicit language, e.g. the report language) for the keys above."""
    return i18n.tr_in(lang, PREFIX + key, **kwargs)


def detector_type_label(t: str) -> str:
    key = "type_" + t
    return ctr(key) if key in EN else t
