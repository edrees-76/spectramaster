"""English/Arabic strings of the energy-calibration review and drift-check dialogs, merged
into ``i18n.STRINGS`` on import (namespaced with ``calib_``; kept out of i18n.py so other
modules' edits never conflict).  Numbers, units and coefficients are wrapped by the dialogs in
LTR isolates (:func:`i18n.ltr`) so they stay readable inside Arabic text."""
from __future__ import annotations

from . import i18n

EN = {
    # menu actions
    "act_cal": "&Energy Calibration...",
    "act_drift": "Check Calibration &Drift...",
    "tip_cal": "Propose, review and accept an energy calibration from the peaks of a known source",
    "tip_drift": "Compare the stored energy calibration with known lines; a correction is only "
                 "proposed and is applied after your confirmation",
    "need_spectrum": "Open a spectrum first.",
    "need_calibration": "The displayed spectrum has no energy calibration, so drift cannot be checked. "
                        "Use Energy Calibration first.",
    # calibration dialog
    "cal_title": "Energy Calibration",
    "cal_spectrum": "Spectrum:",
    "cal_source": "Calibration source:",
    "tip_source": "Nuclides separated by commas (e.g. Co-60,Cs-137), or the aliases "
                  "'mixed' (mixed-nuclide standard) and 'background' (K-40, Ra-226, Th-232)",
    "cal_order": "Polynomial order:",
    "cal_order_auto": "Auto (F-test)",
    "cal_propose": "Propose",
    "cal_running": "Searching peaks and fitting...",
    "cal_hint": "Choose the source and press Propose. Review every line-to-peak assignment "
                "before accepting; nothing is applied to the spectrum until you press Accept.",
    "cal_points_group": "Line-to-peak assignments (review before accepting)",
    "col_used": "Use",
    "col_nuclide": "Nuclide",
    "col_energy": "Library keV",
    "col_channel": "Channel",
    "col_channel_unc": "± channel",
    "col_residual": "Residual keV",
    "col_loo": "Leave-one-out keV",
    "col_sig": "Significance",
    "col_reason": "Reason for exclusion",
    "tip_col_loo": "Library energy minus the energy predicted by a fit without this line "
                   "(independent check of the assignment)",
    "tip_col_used": "Untick to exclude a point (a reason is required)",
    "cal_validation_group": "Validation",
    "val_ok": "Validation passed",
    "val_not_ok": "Validation FAILED: check the source and the line assignments",
    "val_summary": "{n} points · order {order} · F-test p (next order) {p} · χ²/ν {chi2} · "
                   "calibrated range {lo} – {hi} keV · extrapolated {ext} % of the channels",
    "val_errors": "Errors ({n})",
    "val_warnings": "Warnings ({n})",
    "val_no_messages": "No errors or warnings.",
    "cal_coeffs_group": "Coefficients (channel → keV)",
    "cal_energy": "Energy:",
    "cal_fwhm": "FWHM:",
    "cal_apply_fwhm": "Also apply the FWHM calibration proposed with it",
    "tip_apply_fwhm": "FWHM(channel) in keV fitted to the widths of the proposed lines",
    "cal_accept": "Accept and Apply",
    "cal_cancel": "Cancel",
    "reason_title": "Exclude point",
    "reason_prompt": "Reason for excluding {label} (required):",
    "reason_required": "A reason is required to exclude a point; the point stays in the fit.",
    "auto_excluded_again": "{label} was excluded again by the outlier test: {reason}",
    "refit_failed": "Re-fit not possible: {msg}",
    "propose_failed": "Calibration proposal failed:\n{msg}",
    "no_source": "Enter a calibration source.",
    "bad_source": "Unknown source: {msg}",
    "source_changed": "The source was changed after the proposal: press Propose again before accepting.",
    "val_blocked": "Accept is disabled while the validation reports errors: exclude wrong assignments "
                   "(with a reason) or choose the correct source.",
    "excluded_by_user": "excluded by the user: {reason}",
    "cal_rms": "RMS residual {rms} keV · max |residual| {max} keV · {dof} degree(s) of freedom",
    "cal_engine_messages": "Validation messages (engine text):",
    "cal_no_proposal": "No proposal yet.",
    "cal_running_refit": "Re-fitting...",
    "status_cal_applied": "Energy calibration applied to the displayed spectrum ({n} points, order {order}, "
                          "{lo} – {hi} keV). The file on disk is unchanged.",
    # drift dialog
    "drift_title": "Calibration Drift Check",
    "drift_ref": "Reference lines:",
    "drift_ref_placeholder": "empty = natural background lines (K-40, U and Th series)",
    "tip_drift_ref": "Leave empty for natural-background lines, or give calibration-source nuclides "
                     "(e.g. Co-60,Cs-137)",
    "drift_check": "Check",
    "drift_running": "Checking the calibration...",
    "drift_detected": "DRIFT DETECTED",
    "drift_none": "No significant drift",
    "drift_summary": "{state}: {n} reference lines, gain {gain} %, offset {off} keV{fixed}; "
                     "largest shift {kev} keV = {fwhm} FWHM ({sig} σ)",
    "drift_offset_fixed": " (offset fixed: not justified by the lines)",
    "drift_engine": "Report:",
    "drift_lines_group": "Reference lines",
    "drift_col_name": "Line",
    "drift_col_ref": "Reference keV",
    "drift_col_meas": "Measured keV",
    "drift_col_shift": "Shift keV ± σ",
    "drift_excluded_group": "Excluded lines",
    "drift_no_excluded": "None.",
    "drift_coeffs_group": "Energy coefficients (channel → keV)",
    "drift_current": "Current:",
    "drift_proposed": "Proposed:",
    "drift_none_proposed": "no proposal",
    "drift_apply": "Apply Proposed Correction...",
    "drift_close": "Close",
    "drift_confirm_title": "Apply drift correction?",
    "drift_confirm": "Replace the energy calibration of the displayed spectrum by the proposed "
                     "coefficients?\n\nCurrent:  {old}\nProposed: {new}\n\nThe file on disk is not modified.",
    "drift_confirm_nodrift": "No significant drift was found.",
    "drift_failed": "Drift check failed:\n{msg}",
    "status_drift_applied": "Drift correction applied to the displayed spectrum. The file on disk is unchanged.",
}

AR = {
    "act_cal": "معايرة الطاقة...",
    "act_drift": "فحص انجراف المعايرة...",
    "tip_cal": "اقتراح معايرة للطاقة من قمم مصدر معروف ومراجعتها واعتمادها",
    "tip_drift": "مقارنة معايرة الطاقة المخزنة بخطوط معروفة؛ يُقترح التصحيح فقط ولا يُطبَّق إلا بعد تأكيدك",
    "need_spectrum": "افتح طيفًا أولًا.",
    "need_calibration": "لا يحتوي الطيف المعروض على معايرة للطاقة، فلا يمكن فحص الانجراف. "
                        "استخدم معايرة الطاقة أولًا.",
    "cal_title": "معايرة الطاقة",
    "cal_spectrum": "الطيف:",
    "cal_source": "مصدر المعايرة:",
    "tip_source": "نويدات مفصولة بفواصل (مثل ⁦Co-60,Cs-137⁩)، أو الاسمان المختصران "
                  "⁦mixed⁩ (مصدر معياري متعدد النويدات) و⁦background⁩ (⁦K-40, Ra-226, Th-232⁩)",
    "cal_order": "رتبة كثيرة الحدود:",
    "cal_order_auto": "تلقائي (اختبار F)",
    "cal_propose": "اقتراح",
    "cal_running": "جارٍ البحث عن القمم والمواءمة...",
    "cal_hint": "اختر المصدر ثم اضغط «اقتراح». راجع كل إسناد بين خط وقمة قبل الاعتماد؛ "
                "لا يُطبَّق شيء على الطيف حتى تضغط «اعتماد وتطبيق».",
    "cal_points_group": "إسناد الخطوط إلى القمم (راجعه قبل الاعتماد)",
    "col_used": "استخدام",
    "col_nuclide": "النويدة",
    "col_energy": "طاقة المكتبة keV",
    "col_channel": "القناة",
    "col_channel_unc": "± القناة",
    "col_residual": "المتبقي keV",
    "col_loo": "المتبقي باستبعاد النقطة keV",
    "col_sig": "الدلالة الإحصائية",
    "col_reason": "سبب الاستبعاد",
    "tip_col_loo": "طاقة المكتبة مطروحًا منها الطاقة المتنبأ بها من مواءمة لا تتضمن هذا الخط "
                   "(فحص مستقل للإسناد)",
    "tip_col_used": "أزل العلامة لاستبعاد النقطة (يلزم ذكر السبب)",
    "cal_validation_group": "التحقق",
    "val_ok": "اجتازت المعايرة التحقق",
    "val_not_ok": "فشل التحقق: راجع المصدر وإسناد الخطوط",
    "val_summary": "عدد النقاط {n} · الرتبة {order} · قيمة p لاختبار F (للرتبة التالية) {p} · "
                   "⁦χ²/ν⁩ {chi2} · المدى المعايَر {lo} – {hi} keV · المستقرأ {ext} % من القنوات",
    "val_errors": "الأخطاء ({n})",
    "val_warnings": "التحذيرات ({n})",
    "val_no_messages": "لا توجد أخطاء ولا تحذيرات.",
    "cal_coeffs_group": "المعاملات (القناة ← keV)",
    "cal_energy": "الطاقة:",
    "cal_fwhm": "العرض الكامل عند نصف الارتفاع:",
    "cal_apply_fwhm": "تطبيق معايرة العرض (FWHM) المقترحة معها أيضًا",
    "tip_apply_fwhm": "العرض الكامل عند نصف الارتفاع بدلالة القناة (keV) مواءمًا على عروض الخطوط المقترحة",
    "cal_accept": "اعتماد وتطبيق",
    "cal_cancel": "إلغاء",
    "reason_title": "استبعاد نقطة",
    "reason_prompt": "سبب استبعاد {label} (إلزامي):",
    "reason_required": "يلزم ذكر سبب لاستبعاد النقطة؛ ستبقى النقطة في المواءمة.",
    "auto_excluded_again": "استُبعدت {label} مجددًا باختبار القيم الشاذة: {reason}",
    "refit_failed": "تعذّرت إعادة المواءمة: {msg}",
    "propose_failed": "فشل اقتراح المعايرة:\n{msg}",
    "no_source": "أدخل مصدر المعايرة.",
    "bad_source": "مصدر غير معروف: {msg}",
    "source_changed": "تغيّر المصدر بعد الاقتراح: اضغط «اقتراح» مرة أخرى قبل الاعتماد.",
    "val_blocked": "زر الاعتماد معطَّل ما دام التحقق يُبلغ عن أخطاء: استبعد الإسنادات الخاطئة "
                   "(مع ذكر السبب) أو اختر المصدر الصحيح.",
    "excluded_by_user": "استبعده المستخدم: {reason}",
    "cal_rms": "جذر متوسط مربعات المتبقي {rms} keV · أكبر متبقٍ مطلق {max} keV · درجات الحرية {dof}",
    "cal_engine_messages": "رسائل التحقق (نص المحرك بالإنجليزية):",
    "cal_no_proposal": "لا يوجد اقتراح بعد.",
    "cal_running_refit": "جارٍ إعادة المواءمة...",
    "status_cal_applied": "طُبِّقت معايرة الطاقة على الطيف المعروض (عدد النقاط {n}، الرتبة {order}، "
                          "{lo} – {hi} keV). لم يُعدَّل الملف المحفوظ على القرص.",
    "drift_title": "فحص انجراف المعايرة",
    "drift_ref": "الخطوط المرجعية:",
    "drift_ref_placeholder": "فارغ = خطوط الخلفية الطبيعية (⁦K-40⁩ وسلسلتا اليورانيوم والثوريوم)",
    "tip_drift_ref": "اتركه فارغًا لاستخدام خطوط الخلفية الطبيعية، أو أدخل نويدات مصدر المعايرة "
                     "(مثل ⁦Co-60,Cs-137⁩)",
    "drift_check": "فحص",
    "drift_running": "جارٍ فحص المعايرة...",
    "drift_detected": "رُصد انجراف",
    "drift_none": "لا يوجد انجراف ذو دلالة",
    "drift_summary": "{state}: عدد الخطوط المرجعية {n}، الكسب {gain} %، الإزاحة {off} keV{fixed}؛ "
                     "أكبر انزياح {kev} keV = {fwhm} FWHM ‏({sig} σ)",
    "drift_offset_fixed": " (الإزاحة مثبّتة: لا تسوّغها الخطوط)",
    "drift_engine": "التقرير:",
    "drift_lines_group": "الخطوط المرجعية",
    "drift_col_name": "الخط",
    "drift_col_ref": "الطاقة المرجعية keV",
    "drift_col_meas": "الطاقة المقيسة keV",
    "drift_col_shift": "الانزياح keV ± σ",
    "drift_excluded_group": "الخطوط المستبعدة",
    "drift_no_excluded": "لا يوجد.",
    "drift_coeffs_group": "معاملات الطاقة (القناة ← keV)",
    "drift_current": "الحالية:",
    "drift_proposed": "المقترحة:",
    "drift_none_proposed": "لا يوجد اقتراح",
    "drift_apply": "تطبيق التصحيح المقترح...",
    "drift_close": "إغلاق",
    "drift_confirm_title": "تطبيق تصحيح الانجراف؟",
    "drift_confirm": "هل تريد استبدال معايرة الطاقة للطيف المعروض بالمعاملات المقترحة؟\n\n"
                     "الحالية:  {old}\nالمقترحة: {new}\n\nلن يُعدَّل الملف المحفوظ على القرص.",
    "drift_confirm_nodrift": "لم يُرصد انجراف ذو دلالة.",
    "drift_failed": "فشل فحص الانجراف:\n{msg}",
    "status_drift_applied": "طُبِّق تصحيح الانجراف على الطيف المعروض. لم يُعدَّل الملف المحفوظ على القرص.",
}

PREFIX = "calib_"
i18n.STRINGS.setdefault("en", {}).update({PREFIX + k: v for k, v in EN.items()})
i18n.STRINGS.setdefault("ar", {}).update({PREFIX + k: v for k, v in AR.items()})


def ctr(key: str, **kwargs) -> str:
    """``tr`` for the keys above (namespaced with ``calib_``)."""
    return i18n.tr(PREFIX + key, **kwargs)
