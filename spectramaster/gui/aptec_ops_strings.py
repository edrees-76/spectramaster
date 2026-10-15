"""English/Arabic strings of the Aptec *Analyze* spectrum operations (Add Constant, Normalize,
Shift, Smooth, Reduce Channels, Derivative, Compare, Exchange, Combine, Strip, Position), merged
into ``i18n.STRINGS`` on import with the prefix ``aops_``."""
from __future__ import annotations

from . import i18n

EN = {
    "act_add_constant": "Add &Constant...",
    "act_normalize": "&Normalize...",
    "act_shift": "S&hift...",
    "act_smooth": "S&mooth...",
    "act_reduce": "&Reduce Channels...",
    "act_derivative": "&Derivative...",
    "act_compare": "C&ompare...",
    "act_exchange": "&Exchange...",
    "act_combine": "Com&bine...",
    "act_strip": "S&trip...",
    "act_position": "&Position...",
    "act_undo": "&Undo Spectrum Operation",
    "act_original": "Re&load Original Spectrum",
    "tip_add_constant": "Add a positive or negative whole number to every channel",
    "tip_normalize": "Multiply the spectrum and its counting times by a factor",
    "tip_shift": "Move the spectrum left or right by a whole number of channels",
    "tip_smooth": "Weighted average of every channel with its neighbours (3, 5, 7 or 9 channels)",
    "tip_reduce": "Add adjacent channels together (like a lower ADC gain); calibrations and ROIs follow",
    "tip_derivative": "Show the 1st, 2nd or 3rd derivative of the spectrum (a visual aid for peaks)",
    "tip_compare": "Show another spectrum file over the displayed one; again to leave compare mode",
    "tip_exchange": "Swap the displayed spectrum and the compare spectrum",
    "tip_combine": "Add the compare spectrum channel by channel (normalize first)",
    "tip_strip": "Subtract the compare spectrum channel by channel (normalize first)",
    "tip_position": "Vertical offset of the compare spectrum in pixels (also Ctrl+Up / Ctrl+Down)",
    "tip_undo": "Undo the last spectrum operation (Ctrl+Z)",
    "tip_original": "Read the displayed spectrum again from its file (all operations are dropped)",
    "need_spectrum": "Open a spectrum first.",
    "need_compare": "Select Compare first: this needs a compare spectrum.",
    "nothing_undo": "No spectrum operation to undo.",
    "no_file": "The displayed spectrum has no file to reload.",
    "done": "{what}.  The spectrum on the screen was changed; the file is unchanged until you save it "
            "(File > Save As).",
    "not_poisson": "  Counts are no longer Poisson counts: uncertainties from sqrt(counts) are not valid.",
    "undone": "Undone: {what}.",
    "reloaded": "The original spectrum was read again from the file.",
    "compare_on": "Compare: {name}.  Ctrl+Up / Ctrl+Down move it; Compare again leaves compare mode.",
    "compare_off": "Compare mode ended.",
    "fd_compare": "Compare spectrum",
    "compare_label": "Compare: {name}",
    "err": "The operation was not done: {msg}",
    # dialogs
    "const_title": "Add Constant",
    "const_value": "Constant (counts per channel):",
    "const_hint": "This whole number is added to every channel (a negative number subtracts).",
    "norm_title": "Normalize Spectrum Counts",
    "norm_factor": "Factor:",
    "norm_hint": "Every channel and the live and true times are multiplied by the factor. "
                 "-1 inverts the spectrum about zero.",
    "norm_ratio": "Live Time Matching Multiplier (compare / displayed): {r}",
    "norm_no_ratio": "No compare spectrum (or no live time): no live time matching multiplier.",
    "norm_bad": "Type a non-zero number.",
    "shift_title": "Shift",
    "shift_channels": "Channels:",
    "shift_left": "Left (to lower channels)",
    "shift_right": "Right (to higher channels)",
    "shift_hint": "The calibrations stay as they are: the data move under the channel axis. Vacated "
                  "channels become zero.",
    "smooth_title": "Smooth",
    "smooth_points": "{n} point",
    "smooth_hint": "Binomial weights, e.g. 5 point = (1 4 6 4 1)/16.  Aptec does not document its "
                   "weights, so this smoothing is not verified against Aptec.  A smoothed spectrum "
                   "no longer has Poisson counts.",
    "reduce_title": "Reduce Channels",
    "reduce_by": "Reduce by:",
    "reduce_item": "{f} to 1   ({m} channels)",
    "reduce_hint": "Adjacent channels are added; gross counts are unchanged. Energy and resolution "
                   "calibrations and ROI end points are divided to stay valid.",
    "deriv_title": "Derivative",
    "deriv_original": "Original data",
    "deriv_1": "First derivative (peak centroid at the zero crossing)",
    "deriv_2": "Second derivative (peaks: negative lobe between positive lobes)",
    "deriv_3": "Third derivative (centroids of multiplets at negative-to-positive crossings)",
    "deriv_smooth": "Smooth before (points):",
    "deriv_none": "None",
    "deriv_hint": "Central differences; smoothing first reduces the noise.  A visual aid only: do not "
                  "analyze a derivative.",
    "pos_title": "Position",
    "pos_offset": "Vertical offset (pixels, + = up):",
    "pair_title": "{op}",
    "pair_text": "{op}: displayed spectrum {sign} compare spectrum, channel by channel.\n\n"
                 "Displayed: {a}\nLive time {la}  ·  {na} channels\n\n"
                 "Compare: {b}\nLive time {lb}  ·  {nb} channels\n\n"
                 "Make sure the result will make sense: normally normalize first (e.g. by the live "
                 "time ratio).",
    "pair_warn_lt": "\n\nThe live times are different: the spectra are not normalized.",
    "pair_warn_cal": "\n\nThe energy calibrations are different: channels are added as they are.",
    "op_combine": "Combine",
    "op_strip": "Strip",
    "unknown": "(unknown)",
}

AR = {
    "act_add_constant": "إضافة &ثابت...",
    "act_normalize": "&تطبيع...",
    "act_shift": "إ&زاحة...",
    "act_smooth": "ت&نعيم...",
    "act_reduce": "تقليل ال&قنوات...",
    "act_derivative": "الم&شتقة...",
    "act_compare": "م&قارنة...",
    "act_exchange": "ت&بديل...",
    "act_combine": "&جمع...",
    "act_strip": "&طرح...",
    "act_position": "&موضع...",
    "act_undo": "ترا&جع عن عملية الطيف",
    "act_original": "إعادة &قراءة الطيف الأصلي",
    "tip_add_constant": "إضافة عدد صحيح موجب أو سالب إلى كل قناة",
    "tip_normalize": "ضرب الطيف وأزمنة العدّ في معامل",
    "tip_shift": "إزاحة الطيف يمينًا أو يسارًا بعدد صحيح من القنوات",
    "tip_smooth": "متوسط مرجّح لكل قناة مع جاراتها (3 أو 5 أو 7 أو 9 قنوات)",
    "tip_reduce": "جمع القنوات المتجاورة (كتخفيض كسب ADC)؛ تتبعها المعايرات والمناطق",
    "tip_derivative": "عرض المشتقة الأولى أو الثانية أو الثالثة للطيف (مساعدة بصرية لرؤية القمم)",
    "tip_compare": "عرض طيف من ملف آخر فوق الطيف المعروض؛ اخترها مرة ثانية لإنهاء المقارنة",
    "tip_exchange": "تبديل الطيف المعروض مع طيف المقارنة",
    "tip_combine": "جمع طيف المقارنة قناة بقناة (طبّع أولًا)",
    "tip_strip": "طرح طيف المقارنة قناة بقناة (طبّع أولًا)",
    "tip_position": "الإزاحة الرأسية لطيف المقارنة بالبكسل (وكذلك Ctrl+↑ و Ctrl+↓)",
    "tip_undo": "التراجع عن آخر عملية على الطيف (Ctrl+Z)",
    "tip_original": "قراءة الطيف المعروض من ملفه من جديد (تُلغى كل العمليات)",
    "need_spectrum": "افتح طيفًا أولًا.",
    "need_compare": "اختر «مقارنة» أولًا: هذه العملية تحتاج طيف مقارنة.",
    "nothing_undo": "لا توجد عملية على الطيف للتراجع عنها.",
    "no_file": "الطيف المعروض ليس له ملف لإعادة قراءته.",
    "done": "{what}.  تغيّر الطيف على الشاشة فقط؛ الملف لم يتغير حتى تحفظه (ملف > حفظ باسم).",
    "not_poisson": "  العدّات لم تعد عدّات بواسون: الأخطاء المحسوبة من الجذر التربيعي للعدّات غير صحيحة.",
    "undone": "تم التراجع عن: {what}.",
    "reloaded": "أُعيدت قراءة الطيف الأصلي من الملف.",
    "compare_on": "مقارنة: {name}.  Ctrl+↑ و Ctrl+↓ لتحريكه؛ «مقارنة» مرة ثانية لإنهاء المقارنة.",
    "compare_off": "انتهى وضع المقارنة.",
    "fd_compare": "طيف المقارنة",
    "compare_label": "مقارنة: {name}",
    "err": "لم تُنفّذ العملية: {msg}",
    "const_title": "إضافة ثابت",
    "const_value": "الثابت (عدّات لكل قناة):",
    "const_hint": "يُضاف هذا العدد الصحيح إلى كل قناة (العدد السالب يطرح).",
    "norm_title": "تطبيع عدّات الطيف",
    "norm_factor": "المعامل:",
    "norm_hint": "تُضرب كل قناة والزمن الحي والزمن الحقيقي في المعامل. المعامل \u200e-1\u200e يعكس الطيف حول الصفر.",
    "norm_ratio": "معامل مطابقة الزمن الحي (المقارنة / المعروض): {r}",
    "norm_no_ratio": "لا يوجد طيف مقارنة (أو لا يوجد زمن حي): لا يوجد معامل لمطابقة الزمن الحي.",
    "norm_bad": "اكتب عددًا غير الصفر.",
    "shift_title": "إزاحة",
    "shift_channels": "عدد القنوات:",
    "shift_left": "يسارًا (نحو القنوات الأدنى)",
    "shift_right": "يمينًا (نحو القنوات الأعلى)",
    "shift_hint": "المعايرات تبقى كما هي: البيانات هي التي تتحرك تحت محور القنوات. القنوات التي "
                  "تفرغ تصبح صفرًا.",
    "smooth_title": "تنعيم",
    "smooth_points": "{n} نقاط",
    "smooth_hint": "أوزان ذات الحدين، مثلًا 5 نقاط = \u200e(1 4 6 4 1)/16\u200e.  دليل Aptec لا يذكر أوزانه، لذلك "
                   "هذا التنعيم غير متحقق منه مقابل Aptec.  الطيف المنعّم لم تعد عدّاته عدّات بواسون.",
    "reduce_title": "تقليل القنوات",
    "reduce_by": "التقليل بنسبة:",
    "reduce_item": "{f} إلى 1   ({m} قناة)",
    "reduce_hint": "تُجمع القنوات المتجاورة؛ مجموع العدّات لا يتغير. تُقسم معايرتا الطاقة والدقة وحدود "
                   "المناطق لتبقى صحيحة.",
    "deriv_title": "المشتقة",
    "deriv_original": "البيانات الأصلية",
    "deriv_1": "المشتقة الأولى (مركز القمة عند نقطة عبور الصفر)",
    "deriv_2": "المشتقة الثانية (القمة: فص سالب بين فصّين موجبين)",
    "deriv_3": "المشتقة الثالثة (مراكز القمم المتداخلة عند العبور من السالب إلى الموجب)",
    "deriv_smooth": "التنعيم قبلها (نقاط):",
    "deriv_none": "بدون",
    "deriv_hint": "فروق مركزية؛ التنعيم أولًا يقلل الضجيج.  للمساعدة البصرية فقط: لا تحلّل طيف مشتقة.",
    "pos_title": "الموضع",
    "pos_offset": "الإزاحة الرأسية (بكسل، الموجب = لأعلى):",
    "pair_title": "{op}",
    "pair_text": "{op}: الطيف المعروض {sign} طيف المقارنة، قناة بقناة.\n\n"
                 "المعروض: {a}\nالزمن الحي {la}  ·  {na} قناة\n\n"
                 "المقارنة: {b}\nالزمن الحي {lb}  ·  {nb} قناة\n\n"
                 "تأكد أن النتيجة ستكون منطقية: عادةً طبّع أولًا (مثلًا بنسبة الزمنين الحيين).",
    "pair_warn_lt": "\n\nالزمنان الحيان مختلفان: الطيفان غير مُطبَّعين.",
    "pair_warn_cal": "\n\nمعايرتا الطاقة مختلفتان: ستُجمع القنوات كما هي.",
    "op_combine": "جمع",
    "op_strip": "طرح",
    "unknown": "(غير معروف)",
}

PREFIX = "aops_"
i18n.STRINGS.setdefault("en", {}).update({PREFIX + k: v for k, v in EN.items()})
i18n.STRINGS.setdefault("ar", {}).update({PREFIX + k: v for k, v in AR.items()})

_SC = [
    ("Ctrl + Z", "Undo the last spectrum operation", "التراجع عن آخر عملية على الطيف"),
    ("Ctrl + ↑  /  Ctrl + ↓", "Raise / lower the compare spectrum", "رفع / خفض طيف المقارنة"),
]
i18n.SHORTCUTS.extend(row for row in _SC if row not in i18n.SHORTCUTS)


def otr(key: str, **kwargs) -> str:
    """``tr`` for the keys above (namespaced with ``aops_``)."""
    return i18n.tr(PREFIX + key, **kwargs)
