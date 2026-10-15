"""English/Arabic strings of the Aptec-style ROI menu (Properties, Paint, Edit, Delete Indexed,
Delete All, Sort, Flag Definitions) and the ROI Paint bar, merged into ``i18n.STRINGS`` on import
with the prefix ``aroi_``.  Names follow Aptec PCMCA/WIN."""
from __future__ import annotations

from . import i18n

EN = {
    "menu_roi": "&ROI",
    "act_props": "&Properties...",
    "act_paint": "P&aint",
    "act_edit": "&Edit",
    "act_del_indexed": "&Delete Indexed",
    "act_del_all": "Delete &All...",
    "act_sort": "&Sort",
    "act_flags": "&Flag Definitions",
    "act_next": "Next ROI",
    "act_prev": "Previous ROI",
    "tip_props": "How the ROI background, centroid, MDA and errors are calculated (Shift+R)",
    "tip_paint": "Paint a new ROI at the channel marker (F3); or Ctrl-click the left side, then "
                 "the right side of a peak",
    "tip_edit": "Edit the indexed ROI (F4)",
    "tip_del_indexed": "Delete the indexed ROI without asking (Del)",
    "tip_del_all": "Delete all ROIs after confirmation",
    "tip_sort": "Renumber the ROIs by increasing centroid energy",
    "tip_flags": "Meaning of the ROI flag letters",
    "tip_next": "Index the next ROI to the right (Space)",
    "tip_prev": "Index the next ROI to the left (Shift+Space)",
    # paint bar
    "paint_bar": "ROI Paint",
    "p_set": "Set",
    "p_delete": "Delete",
    "p_cancel": "Cancel",
    "tip_p_set": "Accept the painted ROI (Ctrl-click, Enter)",
    "tip_p_delete": "Delete the ROI being edited; cancels a new ROI",
    "tip_p_cancel": "Leave the ROI as it was (Esc)",
    "tip_p_expand": "Expand the ROI one channel left and right (F3)",
    "tip_p_shrink": "Shrink the ROI one channel left and right (F4)",
    "tip_p_left": "Shift the ROI one channel left (F5)",
    "tip_p_right": "Shift the ROI one channel right (F6)",
    "paint_status": "ROI Paint: channels {a} - {b}   Gross {g}   Net {net} ± {unc}   Centroid {cen}"
                    "   (drag with the mouse, F3-F6, then Set)",
    "edit_status": "ROI Edit {n}: channels {a} - {b}   Gross {g}   Net {net} ± {unc}   Centroid {cen}",
    "index_status": "ROI {n} of {total}: channels {a} - {b}   Centroid {cen}   Net {net} ± {unc}",
    "need_index": "Index an ROI first: Space / Shift+Space, or click it in the ROI list.",
    "need_spectrum": "Open a spectrum first.",
    "del_all_title": "Delete All ROIs",
    "del_all_q": "Delete all {n} ROIs of this spectrum?",
    # properties
    "props_title": "ROI Properties",
    "g_bkg": "ROI Bkgnd Line",
    "bkg_avg": "Straight line between end-point averages",
    "bkg_lsq": "Least squares fit, order {k}",
    "g_end": "ROI Bkgnd End Points",
    "end_fixed": "With X end channels",
    "end_var": "With X low end channels, Y high end channels",
    "end_x": "X:",
    "end_y": "Y:",
    "end_hint": "Channels outside each side of the ROI (0 - 32). Use 2nd order or higher only with "
                "at least 10 end points.",
    "g_cen": "Centroid Calculated",
    "cen_ghm": "Between Gross Half Max",
    "cen_fwhm": "Between Net Half Max",
    "cen_fwtm": "Between Net Tenth Max",
    "cen_all": "Over Whole ROI",
    "g_wgt": "Centroid Weighting",
    "wgt_net": "Net * Chan",
    "wgt_squared": "Net * abs(Net) * Chan",
    "g_conf": "Confidence",
    "mda_sigma": "MDA Sigma:",
    "err_sigma": "Error Sigma:",
    "defaults": "Defaults",
    # flags
    "flags_title": "Flag Definitions",
    "flags_intro": "Letters shown in the Flags column of the ROI list and in reports:",
    "flag_b": "Background subtracted",
    "flag_m": "Fitted peak (MultiFit)",
    "flag_s": "Fitted singlet",
    "flag_*": "MDA ROI assigned by peak identification",
    "flag_<": "MDA activity (listing only)",
    "flag_?": "Net count rate (activity) less than the MDA value",
    "flag_>": "Half life is too great: activity overflow when back decay corrected",
    "flags_note": "In this version the ? flag is set by the ROI calculation; the others come with "
                  "background subtraction, MultiFit and quantification.",
    # ROI list
    "col_bkg": "Background",
    "col_err": "% Err ({k}σ)",
    "col_flags": "Flags",
    "hint": "ROI > Paint (F3), Ctrl-click the left then the right side of a peak, or Ctrl + drag. "
            "Space / Shift+Space index the ROIs. Background: {bkg}, {x} end channels outside "
            "the ROI (ROI > Properties, Shift+R).",
    "hint_avg": "line between end-point averages",
    "hint_lsq": "least squares order {k}",
}

AR = {
    "menu_roi": "&مناطق ROI",
    "act_props": "&الخصائص...",
    "act_paint": "ر&سم منطقة",
    "act_edit": "&تعديل",
    "act_del_indexed": "&حذف المنطقة المؤشَّرة",
    "act_del_all": "حذف ال&كل...",
    "act_sort": "&ترتيب",
    "act_flags": "تعريف الأ&علام",
    "act_next": "المنطقة التالية",
    "act_prev": "المنطقة السابقة",
    "tip_props": "طريقة حساب خلفية المنطقة ومركزها و MDA والأخطاء (Shift+R)",
    "tip_paint": "رسم منطقة جديدة عند مؤشر القناة (F3)؛ أو Ctrl مع النقر على يسار القمة ثم يمينها",
    "tip_edit": "تعديل المنطقة المؤشَّرة (F4)",
    "tip_del_indexed": "حذف المنطقة المؤشَّرة دون سؤال (Del)",
    "tip_del_all": "حذف كل المناطق بعد التأكيد",
    "tip_sort": "إعادة ترقيم المناطق حسب طاقة المركز تصاعديًا",
    "tip_flags": "معنى حروف الأعلام في المناطق",
    "tip_next": "التأشير على المنطقة التالية إلى اليمين (Space)",
    "tip_prev": "التأشير على المنطقة التالية إلى اليسار (Shift+Space)",
    "paint_bar": "رسم منطقة",
    "p_set": "تثبيت",
    "p_delete": "حذف",
    "p_cancel": "إلغاء",
    "tip_p_set": "قبول المنطقة المرسومة (Ctrl مع النقر، Enter)",
    "tip_p_delete": "حذف المنطقة التي تُعدَّل؛ يلغي المنطقة الجديدة",
    "tip_p_cancel": "ترك المنطقة كما كانت (Esc)",
    "tip_p_expand": "توسيع المنطقة قناة من اليسار وقناة من اليمين (F3)",
    "tip_p_shrink": "تضييق المنطقة قناة من اليسار وقناة من اليمين (F4)",
    "tip_p_left": "إزاحة المنطقة قناة إلى اليسار (F5)",
    "tip_p_right": "إزاحة المنطقة قناة إلى اليمين (F6)",
    "paint_status": "رسم منطقة: القنوات {a} - {b}   الإجمالي {g}   الصافي {net} ± {unc}   المركز {cen}"
                    "   (اسحب بالفأرة أو F3-F6 ثم تثبيت)",
    "edit_status": "تعديل المنطقة {n}: القنوات {a} - {b}   الإجمالي {g}   الصافي {net} ± {unc}   المركز {cen}",
    "index_status": "المنطقة {n} من {total}: القنوات {a} - {b}   المركز {cen}   الصافي {net} ± {unc}",
    "need_index": "أشِّر على منطقة أولًا: Space / Shift+Space أو انقرها في قائمة المناطق.",
    "need_spectrum": "افتح طيفًا أولًا.",
    "del_all_title": "حذف كل المناطق",
    "del_all_q": "حذف كل المناطق ({n}) في هذا الطيف؟",
    "props_title": "خصائص المناطق",
    "g_bkg": "خط خلفية المنطقة",
    "bkg_avg": "خط مستقيم بين متوسطي نقاط الطرفين",
    "bkg_lsq": "ملاءمة بالمربعات الصغرى، الدرجة {k}",
    "g_end": "نقاط طرفي الخلفية",
    "end_fixed": "بعدد X من القنوات على كل طرف",
    "end_var": "بعدد X عند الطاقة المنخفضة و Y عند الطاقة العالية",
    "end_x": "X:",
    "end_y": "Y:",
    "end_hint": "قنوات خارج كل طرف من المنطقة (0 - 32). لا تستخدم الدرجة الثانية فأعلى إلا مع "
                "10 نقاط طرفية على الأقل.",
    "g_cen": "حساب المركز",
    "cen_ghm": "بين نصفي القيمة العظمى الإجمالية",
    "cen_fwhm": "بين نصفي القيمة العظمى الصافية",
    "cen_fwtm": "بين عُشري القيمة العظمى الصافية",
    "cen_all": "على كامل المنطقة",
    "g_wgt": "ترجيح المركز",
    "wgt_net": "Net * Chan",
    "wgt_squared": "Net * abs(Net) * Chan",
    "g_conf": "مستوى الثقة",
    "mda_sigma": "سيجما MDA:",
    "err_sigma": "سيجما الخطأ:",
    "defaults": "الافتراضي",
    "flags_title": "تعريف الأعلام",
    "flags_intro": "الحروف التي تظهر في عمود الأعلام في قائمة المناطق وفي التقارير:",
    "flag_b": "مطروح منه طيف الخلفية",
    "flag_m": "قمة مُلاءمة (MultiFit)",
    "flag_s": "قمة مفردة مُلاءمة",
    "flag_*": "منطقة MDA أنشأها تعريف النظائر",
    "flag_<": "نشاط MDA (في القوائم فقط)",
    "flag_?": "معدل العد الصافي (النشاط) أقل من قيمة MDA",
    "flag_>": "عمر النصف كبير جدًا: تجاوز في النشاط عند تصحيح الاضمحلال للخلف",
    "flags_note": "في هذا الإصدار يضع حساب المنطقة العلم ?؛ والبقية تأتي مع طرح الخلفية "
                  "و MultiFit والحساب الكمي.",
    "col_bkg": "الخلفية",
    "col_err": "% خطأ ({k}σ)",
    "col_flags": "أعلام",
    "hint": "مناطق ROI > رسم منطقة (F3)، أو Ctrl مع النقر على يسار القمة ثم يمينها، أو Ctrl مع السحب. "
            "Space / Shift+Space للتنقل بين المناطق. الخلفية: {bkg}، {x} قنوات خارج المنطقة "
            "(مناطق ROI > الخصائص، Shift+R).",
    "hint_avg": "خط بين متوسطي الطرفين",
    "hint_lsq": "مربعات صغرى درجة {k}",
}

PREFIX = "aroi_"
i18n.STRINGS.setdefault("en", {}).update({PREFIX + k: v for k, v in EN.items()})
i18n.STRINGS.setdefault("ar", {}).update({PREFIX + k: v for k, v in AR.items()})


# Help > Shortcuts: Aptec ROI keys (Del now deletes the indexed ROI, or the selected rows of
# the ROI list when it has the focus)
_SC = [
    ("Ctrl + Click", "Quick paint an ROI: left side, then right side (while painting: Set)",
     "رسم منطقة سريع: يسار القمة ثم يمينها (أثناء الرسم: تثبيت)"),
    ("F3  /  F4", "ROI Paint / Edit the indexed ROI (while painting: << >> / >> <<)",
     "رسم منطقة / تعديل المنطقة المؤشَّرة (أثناء الرسم: << >> / >> <<)"),
    ("F5  /  F6 (painting)", "Shift the painted ROI one channel left / right",
     "إزاحة المنطقة المرسومة قناة لليسار / لليمين"),
    ("Enter  /  Esc (painting)", "Set / Cancel the painted ROI", "تثبيت / إلغاء المنطقة المرسومة"),
    ("Space  /  Shift + Space", "Index the next / previous ROI", "التأشير على المنطقة التالية / السابقة"),
    ("Shift + R", "ROI Properties", "خصائص المناطق"),
    ("Del", "Delete the indexed ROI (the selected rows in the ROI list)",
     "حذف المنطقة المؤشَّرة (أو الصفوف المحددة في قائمة المناطق)"),
]
i18n.SHORTCUTS[:] = [row for row in i18n.SHORTCUTS if row[0] != "Delete (ROI table)"]
i18n.SHORTCUTS.extend(row for row in _SC if row not in i18n.SHORTCUTS)
i18n.SHORTCUT_KEYS_AR.update({"Ctrl + Click": "Ctrl + نقر",
                              "F5  /  F6 (painting)": "F5  /  F6 (أثناء الرسم)",
                              "Enter  /  Esc (painting)": "Enter  /  Esc (أثناء الرسم)"})


def rtr(key: str, **kwargs) -> str:
    """``tr`` for the keys above (namespaced with ``aroi_``)."""
    return i18n.tr(PREFIX + key, **kwargs)
