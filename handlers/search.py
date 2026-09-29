# تدفق /search — الترتيب: المهنة (قائمة مسطّحة من كل المهن مباشرة، بدون خطوة
# "مجال" وسيطة) → التفريعات (خدمة فرعية اختيارية داخل المهنة) → المنطقة → المدينة
# (من قائمة رسمية بأزرار) → الحي (أزرار من أحياء حقيقية لنفس المدينة، مع تخطي
# اختياري)، ثم نتائج مُرتّبة بنظام تناوب عادل، صفحات من 5، وزر "تواصل عبر واتساب/
# تلغرام" يسجّل الضغطة ويستهلك من الفرص المجانية لكل فني قبل ما يحتاج اشتراك.
#
# خطوة "المجال" اتشالت من بحث العميل تحديدًا (تجربة أسرع: خطوتين بس — المهنة ثم
# التفريعات — بدل ثلاثة) بناءً على طلب صريح؛ خطوة المجال ما زالت موجودة بتسجيل
# الفني نفسه (register.py) لأنها ما تأثرت بهذا التعديل.
#
# دعم تعدد اللغات: نجيب لغة العميل المحفوظة مرة واحدة عند الدخول ونخزّنها بـ
# context.user_data["lang"]، وكل النصوص/الأزرار تُعرض بهذي اللغة عبر i18n.t(...).
# أسماء المدن/الأحياء تبقى عربية دائمًا (بيانات رسمية).

import asyncio

from telegram import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardMarkup,
    ReplyKeyboardRemove,
    Update,
)
from telegram.ext import (
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    filters,
)

import db
import i18n
import professions_repo as professions
from handlers import donation

(
    SEARCH_PROFESSION,
    SEARCH_SUBSERVICE,
    SEARCH_REGION,
    SEARCH_CITY,
    SEARCH_NEIGHBORHOOD,
    SEARCH_RESULTS,
) = range(200, 206)

SKIP_NEIGHBORHOOD_CB = "srch_skip_nb"
BACK_TO_REGIONS_CB = "srch_back_regions"
MORE_RESULTS_CB = "srch_more"
NEARBY_DISTRICT_CB_PREFIX = "srch_nearby:"
NEARBY_CITY_CB_PREFIX = "srch_nearby_city:"
END_SEARCH_CB = "srch_end_search"
MANUAL_DISTRICT_PICK_CB = "srch_manual_dist_pick"
MANUAL_REGION_PICK_CB = "srch_manual_region_pick"
ALL_CITY_DISTRICTS_CB = "srch_all_city_districts"
NEARBY_SUGGESTIONS_COUNT = 3

PROFESSION_BACK_CB = "srch_prof_back"
SERVICE_ALL_CB = "srch_svc_all"
SERVICES_DONE_CB = "srch_svc_done"
CONFIRM_LOCATION_CB = "srch_loc_confirm"
REJECT_LOCATION_CB = "srch_loc_reject"
LOCATION_ALL_CITY_CB = "srch_loc_all_city"
LOCATION_TOGGLE_PREFIX = "srch_loc_toggle:"
LOCATION_NEARBY_DONE_CB = "srch_loc_nearby_done"
LOCATION_NEARBY_COUNT = 3  # + الحي المكتشف نفسه = 4 خيارات تعليم بالمجموع

GEO_PAGE_SIZE = 8


def _lang(context: ContextTypes.DEFAULT_TYPE) -> str:
    return context.user_data.get("lang", "ar")


def _neighborhood_display(neighborhood) -> str:
    """ud["neighborhood"] ممكن تكون نص وحد أو قائمة (لما العميل يعلّم أكثر من حي
    بشاشة تأكيد الموقع) — هذي تحوّلها لنص واحد يُعرض بأي رسالة بشكل موحّد."""
    if not neighborhood:
        return ""
    if isinstance(neighborhood, str):
        return neighborhood
    return "، ".join(neighborhood)


def _region_keyboard() -> InlineKeyboardMarkup:
    buttons, row = [], []
    for r in db.list_sa_regions():
        row.append(InlineKeyboardButton(r["name"], callback_data=f"srch_region:{r['id']}"))
        if len(row) == 2:
            buttons.append(row)
            row = []
    if row:
        buttons.append(row)
    return InlineKeyboardMarkup(buttons)


def _paginated_keyboard(items: list[dict], page: int, item_cb_prefix: str, page_cb_prefix: str, extra_rows: list = None):
    total = len(items)
    start = page * GEO_PAGE_SIZE
    page_items = items[start:start + GEO_PAGE_SIZE]

    buttons, row = [], []
    for it in page_items:
        row.append(InlineKeyboardButton(it["name"], callback_data=f"{item_cb_prefix}{it['id']}"))
        if len(row) == 2:
            buttons.append(row)
            row = []
    if row:
        buttons.append(row)

    nav_row = []
    if page > 0:
        nav_row.append(InlineKeyboardButton("◀️", callback_data=f"{page_cb_prefix}{page - 1}"))
    if start + GEO_PAGE_SIZE < total:
        nav_row.append(InlineKeyboardButton("▶️", callback_data=f"{page_cb_prefix}{page + 1}"))
    if nav_row:
        buttons.append(nav_row)

    for extra in (extra_rows or []):
        buttons.append(extra)

    return InlineKeyboardMarkup(buttons)


def _city_keyboard(region_id: int, page: int, lang: str) -> InlineKeyboardMarkup:
    cities = db.list_sa_major_cities_by_region(region_id)
    return _paginated_keyboard(
        cities, page, "srch_city:", "srch_city_page:",
        extra_rows=[[InlineKeyboardButton(i18n.t("back_to_regions_btn", lang), callback_data=BACK_TO_REGIONS_CB)]],
    )


def _district_keyboard(city_id: int, page: int, lang: str) -> InlineKeyboardMarkup:
    districts = db.list_sa_districts_by_city(city_id)
    return _paginated_keyboard(
        districts, page, "srch_dist:", "srch_dist_page:",
        extra_rows=[[InlineKeyboardButton(i18n.t("srch_skip_district_btn", lang), callback_data=SKIP_NEIGHBORHOOD_CB)]],
    )


def _location_choice_reply_keyboard(lang: str) -> ReplyKeyboardMarkup:
    """لوحة مفاتيح حقيقية (Reply Keyboard) لا أزرار شفافة — هذا الشكل الوحيد
    بتلغرام اللي يقدر يطلب موقع العميل الفعلي (GPS) عبر request_location.
    مطروحة بأول خطوة الموقع (بدل المنطقة) عشان لو شارك موقعه نحدد له المدينة
    والحي معًا بضغطة وحدة، بدل تصفح منطقة ← مدينة ← حي كامل يدويًا. الخيار
    الثاني نص عادي يرجعه للمسار اليدوي المعتاد بالكامل."""
    return ReplyKeyboardMarkup(
        [
            [KeyboardButton(i18n.t("srch_share_location_btn", lang), request_location=True)],
            [KeyboardButton(i18n.t("srch_manual_location_btn", lang))],
        ],
        resize_keyboard=True,
        one_time_keyboard=True,
    )


def _location_confirm_keyboard(
    choices: dict, selected_ids: list[int], detected_id: int | None, lang: str
) -> InlineKeyboardMarkup:
    """قائمة تعليم (checkbox) لأحياء GPS المقترحة: الحي المكتشف نفسه ("نعم هو")
    + أقرب 3 أحياء له (٤ خيارات بالمجموع)، يعلّم منها العميل وحدة أو أكثر ثم
    يضغط "تم" — بدل الاختيار الفوري القديم اللي يقفل الخطوة بضغطة وحدة."""
    buttons = []
    for did_str, name in choices.items():
        did = int(did_str)
        mark = "✅ " if did in selected_ids else "▫️ "
        if did == detected_id:
            label = f"{i18n.t('srch_location_confirm_yes_btn', lang)} — {name}"
        else:
            label = f"📍 {name}"
        buttons.append([InlineKeyboardButton(mark + label, callback_data=f"{LOCATION_TOGGLE_PREFIX}{did}")])

    buttons.append([InlineKeyboardButton(i18n.t("srch_svc_done_btn", lang), callback_data=LOCATION_NEARBY_DONE_CB)])
    buttons.append([InlineKeyboardButton(i18n.t("srch_all_city_districts_btn", lang), callback_data=LOCATION_ALL_CITY_CB)])
    buttons.append([InlineKeyboardButton(i18n.t("srch_location_confirm_no_btn", lang), callback_data=REJECT_LOCATION_CB)])
    buttons.append([InlineKeyboardButton(i18n.t("srch_end_search_btn", lang), callback_data=END_SEARCH_CB)])
    return InlineKeyboardMarkup(buttons)


# ─────────────────────────── لوحات الأزرار ───────────────────────────

def _all_professions_flat(lang: str) -> list[dict]:
    """كل المهن (الـ65) بترتيب واحد مسطّح، مرتّبة تنازليًا حسب عدد مرات طلبها
    الفعلي بسجل البحث (الأكثر طلبًا يطلع فوق تلقائيًا — سباك/كهربائي/دهان...
    براحتها تتصدّر لما الناس فعليًا يبحثون عنها أكثر، بدون أي ترتيب يدوي ثابت).
    مهنة ما بحث عنها أحد بعد (عداد = صفر) تحافظ على ترتيبها الأصلي بالتصنيف.
    الاستعلام خفيف جدًا (COUNT/GROUP BY على جدول مفهرس) ويشتغل مرة وحدة فقط
    عند فتح /search، فلا يوجد أي عبء حقيقي على السيرفر."""
    result = []
    for d in professions.get_domains(lang):
        result.extend(professions.get_professions_by_domain(d["id"], lang))

    popularity = db.get_profession_popularity()
    # sorted() مستقرة (stable) — تحافظ على الترتيب الأصلي بين المهن المتساوية
    # بالشعبية (خصوصًا كل المهن اللي عدادها صفر بعد)، فقط الأكثر طلبًا يتقدّم.
    result.sort(key=lambda p: popularity.get(p["id"], 0), reverse=True)
    return result


def _profession_list_keyboard(lang: str) -> InlineKeyboardMarkup:
    """كل المهن (أيًا كان عددها الحالي بـ data/professions.json) بلوحة واحدة،
    بدون أزرار صفحات/استمرار — العميل يشوفها كاملة مرة وحدة ويختار مباشرة
    (تلغرام يسمح لغاية 100 زر بلوحة وحدة، فحتى لو زاد العدد لاحقًا نبقى ضمن
    الحد بأمان). أزرار الصفحات تبقى فقط بخطوات لاحقة (المدينة/الحي) اللي عندها
    بيانات أكبر بكثير (مئات المدن/الأحياء)."""
    items = _all_professions_flat(lang)
    buttons, row = [], []
    for it in items:
        row.append(InlineKeyboardButton(it["name"], callback_data=f"srch_prof:{it['id']}"))
        if len(row) == 2:
            buttons.append(row)
            row = []
    if row:
        buttons.append(row)
    return InlineKeyboardMarkup(buttons)


def _subservice_keyboard(services: list[str], selected: set[str], lang: str) -> InlineKeyboardMarkup:
    """اختيار متعدد (تعليم) بنفس أسلوب register.py: index بدل النص الكامل بـ
    callback_data (حد تلغرام 64 بايت)، وعلامة ✅/▫️ قبل كل خدمة تدل هل هي
    محددة حاليًا أو لا. العميل يقدر يعلّم أكثر من خدمة ثم يضغط "تم"، أو يضغط
    "كل الخدمات" مباشرة لو ما يبي يضيّق النتائج بخدمة معيّنة."""
    buttons = []
    for idx, s in enumerate(services):
        mark = "✅ " if s in selected else "▫️ "
        buttons.append([InlineKeyboardButton(mark + s, callback_data=f"srch_svc:{idx}")])
    buttons.append([InlineKeyboardButton(i18n.t("srch_svc_done_btn", lang), callback_data=SERVICES_DONE_CB)])
    buttons.append([InlineKeyboardButton(i18n.t("srch_svc_all_btn", lang), callback_data=SERVICE_ALL_CB)])
    buttons.append([InlineKeyboardButton(i18n.t("srch_back_to_professions_btn", lang), callback_data=PROFESSION_BACK_CB)])
    return InlineKeyboardMarkup(buttons)




def _contact_button(p: dict, lang: str) -> InlineKeyboardMarkup:
    """أزرار التواصل مع الفني — واتساب وتلغرام يظهران متقابلين بجانب بعض بصف واحد
    (كل زر بعلامة تطبيقه) لما يكون الرقمان متوفرين، حتى يختار العميل القناة
    التي تناسبه مباشرة من نتائج البحث."""
    row = []
    if p.get("has_whatsapp", 1):
        row.append(InlineKeyboardButton(i18n.t("srch_contact_wa_btn", lang), callback_data=f"srch_wa:{p['id']}"))
    if p.get("telegram_contact_number"):
        row.append(InlineKeyboardButton(i18n.t("srch_contact_tg_btn", lang), callback_data=f"srch_tg:{p['id']}"))
    if not row:
        # لا واتساب ولا رقم تلغرام مسجّل — نعرض الرقم للاتصال المباشر فقط
        row.append(InlineKeyboardButton(i18n.t("srch_contact_show_btn", lang), callback_data=f"srch_wa:{p['id']}"))
    return InlineKeyboardMarkup([row])


def _wa_link(number: str, text: str | None = None) -> str:
    """يبني رابط واتساب دائمًا برقم دولي كامل برمز الدولة. بعض التسجيلات القديمة
    (قبل إصلاح التطبيع بخطوة التسجيل) قد يكون رقمها محفوظًا بصيغة محلية بدون رمز
    الدولة (05xxxxxxxx) — لو تركناه كما هو، واتساب نفسه يفتح لكنه يقول للعميل إن
    الفني ليس عنده حساب (لأن الرقم دوليًا غير صحيح)، رغم إن الفني فعليًا عنده
    واتساب على نفس الرقم. لذا نطبّعه هنا أيضًا كطبقة حماية إضافية.

    text (اختياري): رسالة جاهزة تُدرج تلقائيًا بحقل الكتابة بواتساب (wa.me يدعم
    ?text=)، نستخدمها عشان الفني يعرف إن العميل جاله عبر بوت «فني» — يشجّعه على
    الاشتراك لما يشوف إن البوت يجيبه عملاء فعليين."""
    import re as _re
    from urllib.parse import quote as _quote

    digits = _re.sub(r"\D", "", number)
    if digits.startswith("00"):
        digits = digits[2:]
    if digits.startswith("0") and not digits.startswith("966"):
        digits = "966" + digits[1:]
    elif not digits.startswith("966") and len(digits) == 9 and digits.startswith("5"):
        digits = "966" + digits
    link = f"https://wa.me/{digits}"
    if text:
        link += f"?text={_quote(text)}"
    return link


def _tg_link(number: str) -> str:
    """نفس منطق تطبيع الرقم المستخدم بواتساب، لكن لبناء رابط تلغرام (t.me/+الرقم).
    يفتح هذا الرابط محادثة مباشرة لو كان الرقم مسجّلًا بتلغرام وخصوصية الفني
    تسمح بذلك (الإعداد الافتراضي "الجميع")؛ غير ذلك يفتح صفحة بحث عن الرقم."""
    import re as _re

    digits = _re.sub(r"\D", "", number)
    if digits.startswith("00"):
        digits = digits[2:]
    if digits.startswith("0") and not digits.startswith("966"):
        digits = "966" + digits[1:]
    elif not digits.startswith("966") and len(digits) == 9 and digits.startswith("5"):
        digits = "966" + digits
    return f"https://t.me/+{digits}"


def _professional_card_text(p: dict) -> str:
    """نص بطاقة الفني كما يشاهدها العميل عند البحث — يشمل مهنته وتخصصاته حتى يفهم
    العميل نطاق خدماته من أول نظرة. نفس هذي الدالة تُستخدم كمعاينة للفني نفسه فور
    التسجيل (register.py) عشان يشوف بطاقته بالضبط قبل ما يستقبل أي طلب."""
    location = p["city"] + (f" — {p['neighborhood']}" if p["neighborhood"] else "")
    lines = [
        f"👷 {p['full_name']}",
        f"🛠️ {p['profession_name']}",
    ]
    services = p.get("services")
    if services is None and p.get("services_json"):
        import json as _json
        services = _json.loads(p["services_json"])
    if services:
        lines.append("📋 " + "، ".join(services))
    lines.append(f"📍 {location}")
    return "\n".join(lines)


# ─────────────────────────── الخطوة 1: المهنة (قائمة مسطّحة كاملة، بدون مجال ولا اقتراح ذكي) ───────────────────────────

async def search_entry(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    lang = await asyncio.to_thread(db.get_user_language, update.effective_user.id)
    context.user_data["lang"] = lang
    target = update.message or update.callback_query.message
    if update.callback_query:
        await update.callback_query.answer()
    keyboard = await asyncio.to_thread(_profession_list_keyboard, lang)
    await target.reply_text(
        i18n.t("srch_entry", lang),
        reply_markup=keyboard,
    )
    return SEARCH_PROFESSION


def _profession_selected_state(context: ContextTypes.DEFAULT_TYPE, profession_id: str, lang: str):
    """يحضّر بيانات المهنة المختارة، ويرجّع (نص، لوحة أزرار، الحالة التالية):
    لو عندها خدمات فرعية → خطوة التفريعات، وإلا → مباشرة لخطوة المنطقة (الموقع
    مو جزء من وعد "خطوتين"، هو خطوة لاحقة منفصلة لازمة لتحديد الفنيين القريبين)."""
    _, profession = professions.get_profession(profession_id, lang)
    if not profession:
        return None, None, None

    context.user_data["profession_id"] = profession_id
    context.user_data["profession_name"] = profession["name"]
    context.user_data["available_services"] = profession["services"]
    context.user_data["service_filter"] = None
    context.user_data["selected_services"] = []

    if profession["services"]:
        text = i18n.t("srch_subservice_prompt", lang, profession=profession["name"])
        markup = _subservice_keyboard(profession["services"], set(), lang)
        return text, markup, SEARCH_SUBSERVICE

    # "location" سترينل مو رقم حالة حقيقي — لأن الخطوة التالية (اختيار الموقع)
    # تحتاج لوحة مفاتيح حقيقية (Reply Keyboard) ما تقدر تُرفق بتعديل رسالة قديمة
    # (edit_message_text)، فلازم رسالة جديدة؛ الاستدعاء يتعامل مع هذا السترينل
    # بمناداة _send_location_choice بدل التعديل المباشر.
    return None, None, "location"


async def _send_location_choice(query, lang: str):
    """يقفل رسالة المهنة/التفريعات الحالية (تعديل عادي، أزرار شفافة) ثم يرسل
    رسالة جديدة بلوحة مفاتيح حقيقية (Reply Keyboard) لخيار الموقع — رسالة
    جديدة لازمة لأن تلغرام ما يسمح بإرفاق Reply Keyboard على تعديل رسالة."""
    await query.edit_message_text(i18n.t("srch_location_choice_intro", lang))
    await query.message.reply_text(
        i18n.t("srch_location_choice_prompt", lang),
        reply_markup=_location_choice_reply_keyboard(lang),
    )


async def back_to_search_professions(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lang = _lang(context)
    query = update.callback_query
    await query.answer()
    keyboard = await asyncio.to_thread(_profession_list_keyboard, lang)
    await query.edit_message_text(i18n.t("srch_entry", lang), reply_markup=keyboard)
    return SEARCH_PROFESSION


async def profession_text_fallback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """هذي الخطوة صارت أزرار فقط (بدون اقتراح ذكي من نص حر) — لو العميل كتب
    بدل ما يضغط زر، نرسل له القائمة من جديد بدل ما نتجاهل رسالته بصمت (هذا
    بالضبط اللي كان يخلي البحث يبدو "معلّق" على العميل)."""
    lang = _lang(context)
    keyboard = await asyncio.to_thread(_profession_list_keyboard, lang)
    await update.message.reply_text(
        i18n.t("srch_entry", lang), reply_markup=keyboard
    )
    return SEARCH_PROFESSION


async def choose_search_profession(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lang = _lang(context)
    query = update.callback_query
    await query.answer()
    profession_id = query.data.split(":", 1)[1]

    text, markup, next_state = await asyncio.to_thread(_profession_selected_state, context, profession_id, lang)
    if not next_state:
        keyboard = await asyncio.to_thread(_profession_list_keyboard, lang)
        await query.edit_message_text(i18n.t("unknown_option", lang), reply_markup=keyboard)
        return SEARCH_PROFESSION

    if next_state == "location":
        await _send_location_choice(query, lang)
        return SEARCH_REGION

    await query.edit_message_text(text, reply_markup=markup)
    return next_state


# ─────────────────────────── الخطوة 2: التفريعات (اختيار متعدد/تعليم) ───────────────────────────

async def choose_search_subservice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """تعليم/إلغاء تعليم خدمة فرعية وحدة — اختيار متعدد (زي register.py)، مو
    اختيار وحيد يقفل الخطوة فورًا. العميل يقدر يعلّم أكثر من خدمة ثم يضغط "تم"."""
    lang = _lang(context)
    query = update.callback_query
    available = context.user_data.get("available_services", [])
    try:
        idx = int(query.data.split(":", 1)[1])
        service = available[idx]
    except (ValueError, IndexError):
        await query.answer()
        return SEARCH_SUBSERVICE

    selected = set(context.user_data.get("selected_services", []))
    if service in selected:
        selected.discard(service)
    else:
        selected.add(service)
    context.user_data["selected_services"] = list(selected)
    await query.answer()

    await query.edit_message_reply_markup(reply_markup=_subservice_keyboard(available, selected, lang))
    return SEARCH_SUBSERVICE


async def subservice_done(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """العميل خلّص تعليم الخدمات اللي يبيها (وحدة أو أكثر) وضغط "تم" — نستخدمها
    كلها معًا كتصفية (أي فني يقدّم أي واحدة منها يظهر بالنتائج). لو ما علّم
    شي، نعتبرها بدون تصفية (كل الخدمات)."""
    lang = _lang(context)
    query = update.callback_query
    await query.answer()
    selected = context.user_data.get("selected_services") or []
    context.user_data["service_filter"] = selected or None
    await _send_location_choice(query, lang)
    return SEARCH_REGION


async def skip_subservice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lang = _lang(context)
    query = update.callback_query
    context.user_data["service_filter"] = None
    await query.answer()
    await _send_location_choice(query, lang)
    return SEARCH_REGION


# ─────────────────────────── الخطوة 2: المنطقة → المدينة → الحي ───────────────────────────

async def choose_search_region(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lang = _lang(context)
    query = update.callback_query
    await query.answer()
    region_id = int(query.data.split(":", 1)[1])
    region = await asyncio.to_thread(db.get_sa_region_by_id, region_id)
    if not region:
        await query.edit_message_text(i18n.t("unknown_option", lang), reply_markup=_region_keyboard())
        return SEARCH_REGION

    context.user_data["region_id"] = region_id
    await query.edit_message_text(
        i18n.t("reg_region_selected", lang, region=region["name"]),
        reply_markup=_city_keyboard(region_id, page=0, lang=lang),
    )
    return SEARCH_CITY


async def back_to_search_regions(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lang = _lang(context)
    query = update.callback_query
    await query.answer()
    await query.edit_message_text(i18n.t("reg_ask_region", lang), reply_markup=_region_keyboard())
    return SEARCH_REGION


async def region_text_router(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """أي نص بخطوة SEARCH_REGION — سواء زر "اختيار يدوي" (Reply Keyboard) أو أي
    نص آخر كتبه العميل بالغلط — يوديه لنفس المسار اليدوي المعتاد (لوحة المناطق
    الشفافة). لوحة المفاتيح الحقيقية one_time_keyboard فتختفي تلقائيًا بمجرد
    إرسال أي رد."""
    lang = _lang(context)
    await update.message.reply_text(
        i18n.t("reg_ask_region", lang), reply_markup=_region_keyboard()
    )
    return SEARCH_REGION


async def receive_early_location(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """يستقبل موقع العميل (GPS) المُرسل بخطوة SEARCH_REGION (أول خطوة بعد
    المهنة/التفريعات) — يحدد أقرب مدينة رسمية وأقرب حي فيها معًا بضغطة وحدة،
    لكن لا يلتزم بها مباشرة: يعرض على العميل قائمة تعليم (الحي المكتشف + أقرب
    3 أحياء له = 4 خيارات) يعلّم منها ما يشاء (وحدة أو أكثر) ثم يضغط "تم"،
    قبل ما يبدأ البحث فعليًا."""
    lang = _lang(context)
    loc = update.message.location
    result = await asyncio.to_thread(
        db.find_nearest_sa_city_and_district_by_coords, loc.latitude, loc.longitude
    )
    await update.message.reply_text(
        i18n.t("srch_location_received", lang), reply_markup=ReplyKeyboardRemove()
    )

    if not result or not result[0]:
        await update.message.reply_text(
            i18n.t("srch_location_no_match", lang), reply_markup=_region_keyboard()
        )
        return SEARCH_REGION

    city, district = result
    ud = context.user_data
    ud["pending_city_id"] = city["id"]
    ud["pending_city_name"] = city["name"]

    if not district:
        # ما قدرنا نحدد حي داخل المدينة (بيانات ناقصة) — ما فيه أحياء نعرضها
        # أصلًا، فتأكيد بسيط على مستوى المدينة فقط (بدون قائمة تعليم).
        text = i18n.t("srch_location_confirm", lang, city=city["name"], district_line="")
        buttons = [
            [InlineKeyboardButton(i18n.t("srch_location_confirm_yes_btn", lang), callback_data=CONFIRM_LOCATION_CB)],
            [InlineKeyboardButton(i18n.t("srch_location_confirm_no_btn", lang), callback_data=REJECT_LOCATION_CB)],
            [InlineKeyboardButton(i18n.t("srch_end_search_btn", lang), callback_data=END_SEARCH_CB)],
        ]
        await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(buttons))
        return SEARCH_REGION

    choices = {str(district["id"]): district["name"]}
    nearby = await asyncio.to_thread(
        db.nearest_sa_districts, district["id"], [district["id"]], LOCATION_NEARBY_COUNT
    )
    for d in nearby:
        choices[str(d["id"])] = d["name"]

    ud["pending_detected_district_id"] = district["id"]
    ud["loc_choice_map"] = choices
    ud["loc_selected_ids"] = []  # ما فيه أي تحديد افتراضي — العميل يعلّم بنفسه

    district_line = i18n.t("srch_location_confirm_district_line", lang, district=district["name"])
    text = i18n.t("srch_location_confirm", lang, city=city["name"], district_line=district_line)

    await update.message.reply_text(
        text,
        reply_markup=_location_confirm_keyboard(choices, [district["id"]], district["id"], lang),
    )
    return SEARCH_REGION


async def confirm_early_location(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """مسار احتياطي: يُستخدم فقط لما ما قدرنا نحدد أي حي (بيانات ناقصة) —
    تأكيد مباشر على مستوى المدينة فقط، بدون قائمة تعليم أحياء."""
    lang = _lang(context)
    query = update.callback_query
    await query.answer()
    ud = context.user_data
    city_id = ud.pop("pending_city_id", None)
    city_name = ud.pop("pending_city_name", None)

    if not city_id:
        await query.edit_message_text(i18n.t("unknown_option", lang), reply_markup=_region_keyboard())
        return SEARCH_REGION

    ud["city_id"] = city_id
    ud["city"] = city_name
    ud["neighborhood"] = None
    ud["district_id"] = None
    ud.setdefault("tried_city_ids", []).append(city_id)

    await query.edit_message_text(i18n.t("srch_location_confirmed", lang, city=city_name))
    return await _run_search(query.message, context, is_edit=False, customer_telegram_id=update.effective_user.id)


async def toggle_location_choice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """تعليم/إلغاء تعليم حي وحد من قائمة الأحياء المقترحة (الحي المكتشف أو أحد
    الأقرب له) — اختيار متعدد، ما يقفل الخطوة، لين يضغط العميل "تم"."""
    lang = _lang(context)
    query = update.callback_query
    await query.answer()
    ud = context.user_data
    choices = ud.get("loc_choice_map", {})
    detected_id = ud.get("pending_detected_district_id")
    selected = set(ud.get("loc_selected_ids", []))

    did = int(query.data.split(":", 1)[1])
    if did in selected:
        selected.discard(did)
    else:
        selected.add(did)
    ud["loc_selected_ids"] = list(selected)

    await query.edit_message_reply_markup(
        reply_markup=_location_confirm_keyboard(choices, list(selected), detected_id, lang)
    )
    return SEARCH_REGION


async def confirm_location_selection(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """العميل خلّص تعليم الأحياء اللي يبيها من قائمة الاقتراحات وضغط "تم" —
    نبحث بكل الأحياء المُعلَّمة معًا (منطق "أو": أي فني بأي حي منها يظهر)."""
    lang = _lang(context)
    query = update.callback_query
    ud = context.user_data
    selected_ids = ud.get("loc_selected_ids", [])

    if not selected_ids:
        await query.answer(i18n.t("srch_location_select_at_least_one", lang), show_alert=True)
        return SEARCH_REGION

    await query.answer()
    city_id = ud.pop("pending_city_id", None)
    city_name = ud.pop("pending_city_name", None)
    choices = ud.pop("loc_choice_map", {})
    ud.pop("loc_selected_ids", None)
    ud.pop("pending_detected_district_id", None)

    if not city_id:
        await query.edit_message_text(i18n.t("unknown_option", lang), reply_markup=_region_keyboard())
        return SEARCH_REGION

    names = [choices[str(did)] for did in selected_ids if str(did) in choices]

    ud["city_id"] = city_id
    ud["city"] = city_name
    ud["district_id"] = selected_ids if len(selected_ids) > 1 else selected_ids[0]
    ud["neighborhood"] = names if len(names) > 1 else (names[0] if names else None)
    ud.setdefault("tried_city_ids", []).append(city_id)
    ud["tried_district_ids"] = list(selected_ids)

    await query.edit_message_text(i18n.t("srch_location_confirmed", lang, city=city_name))
    return await _run_search(query.message, context, is_edit=False, customer_telegram_id=update.effective_user.id)


async def confirm_location_all_city(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """العميل يبي يبحث بكل المدينة المكتشفة تلقائيًا مباشرة، بدون تقييد بحي معيّن."""
    lang = _lang(context)
    query = update.callback_query
    await query.answer()
    ud = context.user_data
    city_id = ud.pop("pending_city_id", None)
    city_name = ud.pop("pending_city_name", None)
    ud.pop("pending_detected_district_id", None)
    ud.pop("loc_choice_map", None)
    ud.pop("loc_selected_ids", None)

    if not city_id:
        await query.edit_message_text(i18n.t("unknown_option", lang), reply_markup=_region_keyboard())
        return SEARCH_REGION

    ud["city_id"] = city_id
    ud["city"] = city_name
    ud["neighborhood"] = None
    ud["district_id"] = None
    ud.setdefault("tried_city_ids", []).append(city_id)

    await query.edit_message_text(i18n.t("srch_location_confirmed", lang, city=city_name))
    return await _run_search(query.message, context, is_edit=False, customer_telegram_id=update.effective_user.id)


async def reject_early_location(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """العميل رفض الموقع المكتشف تلقائيًا (مو صحيح) — نتجاهل الاقتراح المعلّق
    بالكامل ونرجعه للمسار اليدوي المعتاد من أول خطوة (المنطقة)."""
    lang = _lang(context)
    query = update.callback_query
    await query.answer()
    for key in (
        "pending_city_id", "pending_city_name", "pending_detected_district_id",
        "loc_choice_map", "loc_selected_ids",
    ):
        context.user_data.pop(key, None)
    await query.edit_message_text(i18n.t("reg_ask_region", lang), reply_markup=_region_keyboard())
    return SEARCH_REGION


async def search_city_page_nav(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lang = _lang(context)
    query = update.callback_query
    await query.answer()
    page = int(query.data.split(":", 1)[1])
    region_id = context.user_data["region_id"]
    await query.edit_message_reply_markup(reply_markup=_city_keyboard(region_id, page, lang))
    return SEARCH_CITY


async def choose_search_city(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """اختيار الموقع (شارك موقعي / يدوي) صار خطوة واحدة مبكرة بعد المهنة مباشرة
    (راجع _send_location_choice) — فوصول العميل لهذي الخطوة يعني أصلًا اختار
    المسار اليدوي، فنكمله بالكامل يدويًا بدون مقاطعة ثانية بخطوة المدينة."""
    lang = _lang(context)
    query = update.callback_query
    await query.answer()
    city_id = int(query.data.split(":", 1)[1])
    city = await asyncio.to_thread(db.get_sa_city_by_id, city_id)
    if not city:
        await query.edit_message_text(i18n.t("unknown_option", lang))
        return SEARCH_CITY

    context.user_data["city_id"] = city_id
    context.user_data["city"] = city["name"]
    context.user_data.setdefault("tried_city_ids", []).append(city_id)
    await query.edit_message_text(
        i18n.t("srch_city_step", lang, city=city["name"]),
        reply_markup=_district_keyboard(city_id, page=0, lang=lang),
    )
    return SEARCH_NEIGHBORHOOD


async def city_text_search(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """اكتمال تلقائي: يكتب العميل جزء من اسم مدينته بدل تصفح الصفحات."""
    lang = _lang(context)
    region_id = context.user_data.get("region_id")
    if not region_id:
        await update.message.reply_text(i18n.t("reg_ask_region", lang), reply_markup=_region_keyboard())
        return SEARCH_REGION

    query_text = update.message.text.strip()
    matches = await asyncio.to_thread(db.search_sa_major_cities, region_id, query_text)
    if not matches:
        await update.message.reply_text(
            i18n.t("reg_city_not_found", lang),
            reply_markup=_city_keyboard(region_id, page=0, lang=lang),
        )
        return SEARCH_CITY

    buttons, row = [], []
    for c in matches:
        row.append(InlineKeyboardButton(c["name"], callback_data=f"srch_city:{c['id']}"))
        if len(row) == 2:
            buttons.append(row)
            row = []
    if row:
        buttons.append(row)
    buttons.append([InlineKeyboardButton(i18n.t("back_to_regions_btn", lang), callback_data=BACK_TO_REGIONS_CB)])

    await update.message.reply_text(i18n.t("matched_results", lang), reply_markup=InlineKeyboardMarkup(buttons))
    return SEARCH_CITY


async def district_text_search(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """اكتمال تلقائي: يكتب العميل جزء من اسم الحي بدل تصفح الصفحات."""
    lang = _lang(context)
    city_id = context.user_data.get("city_id")
    if not city_id:
        await update.message.reply_text(i18n.t("unknown_option", lang))
        return SEARCH_CITY

    query_text = update.message.text.strip()
    matches = await asyncio.to_thread(db.search_sa_districts, city_id, query_text)
    if not matches:
        await update.message.reply_text(
            i18n.t("reg_district_not_found", lang),
            reply_markup=_district_keyboard(city_id, page=0, lang=lang),
        )
        return SEARCH_NEIGHBORHOOD

    buttons, row = [], []
    for d in matches:
        row.append(InlineKeyboardButton(d["name"], callback_data=f"srch_dist:{d['id']}"))
        if len(row) == 2:
            buttons.append(row)
            row = []
    if row:
        buttons.append(row)
    buttons.append([InlineKeyboardButton(i18n.t("srch_skip_district_btn", lang), callback_data=SKIP_NEIGHBORHOOD_CB)])

    await update.message.reply_text(i18n.t("matched_results", lang), reply_markup=InlineKeyboardMarkup(buttons))
    return SEARCH_NEIGHBORHOOD


async def search_district_page_nav(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lang = _lang(context)
    query = update.callback_query
    await query.answer()
    page = int(query.data.split(":", 1)[1])
    city_id = context.user_data["city_id"]
    await query.edit_message_reply_markup(reply_markup=_district_keyboard(city_id, page, lang))
    return SEARCH_NEIGHBORHOOD


async def choose_search_district(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lang = _lang(context)
    query = update.callback_query
    await query.answer()
    district_id = int(query.data.split(":", 1)[1])
    districts = await asyncio.to_thread(db.list_sa_districts_by_city, context.user_data["city_id"])
    district = next((d for d in districts if d["id"] == district_id), None)
    if not district:
        await query.edit_message_text(i18n.t("unknown_option", lang))
        return SEARCH_NEIGHBORHOOD

    context.user_data["neighborhood"] = district["name"]
    context.user_data["district_id"] = district_id
    context.user_data["tried_district_ids"] = [district_id]
    return await _run_search(query.message, context, is_edit=True, customer_telegram_id=update.effective_user.id)


async def skip_neighborhood(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    context.user_data["neighborhood"] = None
    context.user_data["district_id"] = None  # بحث بكل المدينة أصلًا، فلا داعي لاقتراح أحياء مجاورة
    return await _run_search(query.message, context, is_edit=True, customer_telegram_id=update.effective_user.id)


# ─────────────────────────── الخطوة 4: النتائج (تناوب + صفحات) ───────────────────────────
#
# مهم: نجيب قائمة IDs الكاملة المرتّبة (تناوب عادل) مرة واحدة فقط في بداية جلسة البحث،
# ونخزّنها بذاكرة المحادثة (context.user_data["result_ids"])، ثم نقسّمها بالذاكرة على
# صفحات من 5. هذا يتفادى مشكلة: لو استعلمنا قاعدة البيانات من جديد لكل صفحة بـ OFFSET،
# فإن mark_shown بعد الصفحة الأولى يغيّر ترتيب last_shown_at، فتتكرر أو تُفقد نتائج
# بين الصفحة الأولى والثانية بنفس الجلسة (وهذا فعليًا صار واختبرناه وصلّحناه).

RESULTS_PAGE_SIZE = 5


async def _run_search(message, context: ContextTypes.DEFAULT_TYPE, is_edit: bool, customer_telegram_id: int):
    ud = context.user_data
    result_ids = await asyncio.to_thread(
        db.search_active_professional_ids, ud["profession_id"], ud["city"], ud.get("neighborhood"),
        ud.get("district_id"), ud.get("service_filter"),
    )
    ud["result_ids"] = result_ids
    ud["shown_count"] = 0

    await asyncio.to_thread(
        db.log_search, customer_telegram_id, ud["profession_id"], ud["profession_name"],
        ud["city"], ud.get("neighborhood"), len(result_ids),
    )

    # نبّه (عبر البوت بتلغرام) أي فني كان سيظهر بهذا البحث لولا إنه خلّص فرصه
    # المجانية وما اشترك — يشجّعه يشترك لما يشوف إنه فعليًا يفوّت طلبات حقيقية.
    await _notify_missed_professionals(context, ud)

    return await _show_results_page(message, context, is_edit=is_edit)


async def _notify_missed_professionals(context: ContextTypes.DEFAULT_TYPE, ud: dict):
    missed = await asyncio.to_thread(
        db.find_subscription_missed_professionals,
        ud["profession_id"], ud["city"], ud.get("neighborhood"), ud.get("district_id"),
    )
    if not missed:
        return

    from handlers.subscription import CB_SUBSCRIBE_MENU

    district_suffix = f" — {_neighborhood_display(ud.get('neighborhood'))}" if ud.get("neighborhood") else ""
    sent_ids = []
    for p in missed:
        p_lang = await asyncio.to_thread(db.get_user_language, p["telegram_user_id"])
        text = i18n.t(
            "srch_missed_nudge", p_lang,
            profession=ud["profession_name"], city=ud["city"], district_suffix=district_suffix,
        )
        keyboard = InlineKeyboardMarkup(
            [[InlineKeyboardButton(
                i18n.t("srch_missed_nudge_subscribe_btn", p_lang), callback_data=CB_SUBSCRIBE_MENU
            )]]
        )
        try:
            await context.bot.send_message(chat_id=p["telegram_user_id"], text=text, reply_markup=keyboard)
            sent_ids.append(p["id"])
        except Exception:
            # الفني ممكن يكون حظر البوت أو غيره — ما نوقف تنبيه بقية الفنيين بسببه
            pass

    if sent_ids:
        await asyncio.to_thread(db.mark_search_nudge_sent, sent_ids)


async def _show_results_page(message, context: ContextTypes.DEFAULT_TYPE, is_edit: bool):
    lang = _lang(context)
    ud = context.user_data
    result_ids = ud["result_ids"]
    total = len(result_ids)
    shown_count = ud.get("shown_count", 0)

    if shown_count == 0 and total == 0:
        district_suffix = f" — {_neighborhood_display(ud.get('neighborhood'))}" if ud.get("neighborhood") else ""
        text = i18n.t(
            "srch_no_results", lang,
            profession=ud["profession_name"], city=ud["city"], district_suffix=district_suffix,
        )
        if is_edit:
            await message.edit_text(text)
        else:
            await message.reply_text(text)
        return await _offer_nearby_or_end(message, context)

    if shown_count == 0:
        header = i18n.t("srch_results_header", lang, count=total, profession=ud["profession_name"], city=ud["city"])
        if is_edit:
            await message.edit_text(header)
        else:
            await message.reply_text(header)

    page_ids = result_ids[shown_count: shown_count + RESULTS_PAGE_SIZE]
    results = await asyncio.to_thread(db.get_professionals_by_ids, page_ids)

    for p in results:
        await message.reply_text(_professional_card_text(p), reply_markup=_contact_button(p, lang))

    # نحدّث "آخر ظهور" فقط لمن ظهرت بطاقته فعليًا — أساس عدالة التناوب.
    # نسويها هنا (بعد إرسال هذه الصفحة) لأن القائمة نفسها (result_ids) ثابتة بالذاكرة
    # لباقي الجلسة، فلا تأثير على صفحات لاحقة بنفس الجلسة.
    await asyncio.to_thread(db.mark_shown, page_ids)

    new_shown_count = shown_count + len(results)
    ud["shown_count"] = new_shown_count

    if new_shown_count < total:
        more_keyboard = InlineKeyboardMarkup(
            [[InlineKeyboardButton(
                i18n.t("srch_more_btn", lang, remaining=total - new_shown_count), callback_data=MORE_RESULTS_CB
            )]]
        )
        await message.reply_text(i18n.t("srch_more_prompt", lang), reply_markup=more_keyboard)
        return SEARCH_RESULTS

    # استوفينا كل الفنيين المسجّلين بنفس الحي (مهما كان عددهم) — الآن فقط نقترح حي مجاور،
    # ولا نعرضه أبدًا قبل هذي اللحظة (طلب صريح: العدد ما يهم، لازم يستوفي حيه أولًا).
    return await _offer_nearby_or_end(message, context)


async def _offer_nearby_or_end(message, context: ContextTypes.DEFAULT_TYPE):
    """سلسلة اقتراحات لما تنتهي نتائج البحث الحالي: أولًا أحياء مجاورة بنفس المدينة،
    ولو خلصت كل الأحياء المجاورة بلا فائدة، ننتقل لاقتراح أقرب مدينة/مركز ثاني."""
    lang = _lang(context)
    ud = context.user_data
    district_id = ud.get("district_id")

    if district_id:
        tried_districts = ud.get("tried_district_ids", [district_id])
        nearby_districts = await asyncio.to_thread(
            db.nearest_sa_districts, district_id, tried_districts, NEARBY_SUGGESTIONS_COUNT
        )
        if nearby_districts:
            buttons = [
                [InlineKeyboardButton(f"🏘️ {d['name']}", callback_data=f"{NEARBY_DISTRICT_CB_PREFIX}{d['id']}")]
                for d in nearby_districts
            ]
            buttons.append([InlineKeyboardButton(i18n.t("srch_all_city_districts_btn", lang), callback_data=ALL_CITY_DISTRICTS_CB)])
            buttons.append([InlineKeyboardButton(i18n.t("srch_manual_choice_btn", lang), callback_data=MANUAL_DISTRICT_PICK_CB)])
            buttons.append([InlineKeyboardButton(i18n.t("srch_end_search_btn", lang), callback_data=END_SEARCH_CB)])
            await message.reply_text(
                i18n.t("srch_offer_nearby_district", lang),
                reply_markup=InlineKeyboardMarkup(buttons),
            )
            return SEARCH_RESULTS

    # ما فيه أحياء مجاورة ثانية بنفس المدينة (أو أصلًا بحث بكل المدينة) — نجرّب أقرب مدينة/مركز
    city_id = ud.get("city_id")
    if city_id:
        tried_cities = ud.get("tried_city_ids", [city_id])
        nearby_cities = await asyncio.to_thread(
            db.nearest_sa_cities, city_id, tried_cities, NEARBY_SUGGESTIONS_COUNT
        )
        if nearby_cities:
            buttons = [
                [InlineKeyboardButton(f"🏙️ {c['name']}", callback_data=f"{NEARBY_CITY_CB_PREFIX}{c['id']}")]
                for c in nearby_cities
            ]
            buttons.append([InlineKeyboardButton(i18n.t("srch_manual_choice_btn", lang), callback_data=MANUAL_REGION_PICK_CB)])
            buttons.append([InlineKeyboardButton(i18n.t("srch_end_search_btn", lang), callback_data=END_SEARCH_CB)])
            await message.reply_text(
                i18n.t("srch_offer_nearby_city", lang),
                reply_markup=InlineKeyboardMarkup(buttons),
            )
            return SEARCH_RESULTS

    await message.reply_text(i18n.t("srch_no_more_suggestions", lang))
    context.user_data.clear()
    return ConversationHandler.END


async def choose_nearby_district(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lang = _lang(context)
    query = update.callback_query
    await query.answer()
    district_id = int(query.data.split(":", 1)[1])
    district = await asyncio.to_thread(db.get_sa_district_by_id, district_id)
    if not district:
        await query.edit_message_text(i18n.t("unknown_option", lang))
        return SEARCH_RESULTS

    ud = context.user_data
    ud["neighborhood"] = district["name"]
    ud["district_id"] = district_id
    ud.setdefault("tried_district_ids", []).append(district_id)
    return await _run_search(query.message, context, is_edit=True, customer_telegram_id=update.effective_user.id)


async def choose_nearby_city(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lang = _lang(context)
    query = update.callback_query
    await query.answer()
    city_id = int(query.data.split(":", 1)[1])
    city = await asyncio.to_thread(db.get_sa_city_by_id, city_id)
    if not city:
        await query.edit_message_text(i18n.t("unknown_option", lang))
        return SEARCH_RESULTS

    ud = context.user_data
    ud["city_id"] = city_id
    ud["city"] = city["name"]
    # مدينة/مركز جديد كليًا — نبحث بكل المدينة (بدون تقييد بحي معيّن) ونصفّر تتبّع الأحياء
    ud["neighborhood"] = None
    ud["district_id"] = None
    ud["tried_district_ids"] = []
    ud.setdefault("tried_city_ids", []).append(city_id)
    return await _run_search(query.message, context, is_edit=True, customer_telegram_id=update.effective_user.id)


async def search_all_city_districts(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """العميل يبي يشوف كل فنيي المدينة بهذي المهنة، بغض النظر عن الحي — يلغي أي
    تقييد بحي معيّن ويعيد البحث على مستوى المدينة كاملة (نفس فكرة "تخطي الحي")."""
    query = update.callback_query
    await query.answer()
    context.user_data["neighborhood"] = None
    context.user_data["district_id"] = None
    return await _run_search(query.message, context, is_edit=True, customer_telegram_id=update.effective_user.id)


async def manual_district_pick(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """العميل ما يبي أحد الأحياء المقترحة (المجاورة) ولا يبي ينهي البحث — يرجّعه
    لقائمة أحياء المدينة الحالية كاملة يختار منها يدويًا."""
    lang = _lang(context)
    query = update.callback_query
    await query.answer()
    city_id = context.user_data.get("city_id")
    if not city_id:
        await query.edit_message_text(i18n.t("reg_ask_region", lang), reply_markup=_region_keyboard())
        return SEARCH_REGION

    await query.edit_message_text(
        i18n.t("srch_city_step", lang, city=context.user_data.get("city", "")),
        reply_markup=_district_keyboard(city_id, page=0, lang=lang),
    )
    return SEARCH_NEIGHBORHOOD


async def manual_region_pick(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """العميل ما يبي أحد المدن المقترحة (المجاورة) ولا يبي ينهي البحث — يرجّعه
    لبداية الاختيار اليدوي الكامل (المنطقة) عشان يختار مدينة ثانية كليًا."""
    lang = _lang(context)
    query = update.callback_query
    await query.answer()
    await query.edit_message_text(i18n.t("reg_ask_region", lang), reply_markup=_region_keyboard())
    return SEARCH_REGION


async def end_search_results(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lang = _lang(context)
    query = update.callback_query
    await query.answer()
    await query.edit_message_text(i18n.t("srch_ended", lang))
    context.user_data.clear()
    return ConversationHandler.END


async def show_more_results(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    return await _show_results_page(query.message, context, is_edit=False)


async def whatsapp_click(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    professional_id = int(query.data.split(":", 1)[1])
    lang = await asyncio.to_thread(db.get_user_language, update.effective_user.id)

    p = await asyncio.to_thread(db.get_professional_by_id, professional_id)
    if not p:
        await query.answer(i18n.t("srch_professional_gone", lang), show_alert=True)
        return

    await asyncio.to_thread(db.log_contact_click, professional_id, update.effective_user.id)
    await query.answer()

    if p.get("has_whatsapp", 1):
        prefill = i18n.t("srch_wa_prefill_text", lang, profession=p["profession_name"])
        open_wa_keyboard = InlineKeyboardMarkup(
            [[InlineKeyboardButton(
                i18n.t("srch_open_wa_btn", lang), url=_wa_link(p["whatsapp_number"], prefill)
            )]]
        )
        await query.message.reply_text(
            i18n.t("srch_wa_number_text", lang, name=p["full_name"], number=p["whatsapp_number"]),
            reply_markup=open_wa_keyboard,
        )
    else:
        # هذا الرقم بدون واتساب — نعرض رقم الاتصال المباشر فقط. تلغرام له زر
        # مستقل بنفس البطاقة (srch_tg) لو الفني مسجّل رقمه في تلغرام.
        await query.message.reply_text(
            i18n.t("srch_no_wa_text", lang, name=p["full_name"], number=p["whatsapp_number"])
        )

    await donation.maybe_prompt_donation(context, update.effective_user.id, lang)


async def telegram_click(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    professional_id = int(query.data.split(":", 1)[1])
    lang = await asyncio.to_thread(db.get_user_language, update.effective_user.id)

    p = await asyncio.to_thread(db.get_professional_by_id, professional_id)
    if not p or not p.get("telegram_contact_number"):
        await query.answer(i18n.t("srch_professional_gone", lang), show_alert=True)
        return

    await asyncio.to_thread(db.log_contact_click, professional_id, update.effective_user.id)
    await query.answer()

    number = p["telegram_contact_number"]
    open_tg_keyboard = InlineKeyboardMarkup(
        [[InlineKeyboardButton(i18n.t("srch_open_tg_btn", lang), url=_tg_link(number))]]
    )
    await query.message.reply_text(
        i18n.t("srch_tg_number_text", lang, name=p["full_name"], number=number),
        reply_markup=open_tg_keyboard,
    )

    await donation.maybe_prompt_donation(context, update.effective_user.id, lang)


# ─────────────────────────── إلغاء ───────────────────────────

async def cancel_search(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lang = _lang(context)
    context.user_data.clear()
    await update.message.reply_text(i18n.t("srch_cancelled", lang))
    return ConversationHandler.END


async def restart_via_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """نفس فكرة register.py: لو العميل أرسل /start وهو عالق بمنتصف بحث قديم،
    نخرجه منه فورًا ونعرض له القائمة الرئيسية، بدل ما يبقى عالق لين تنتهي مهلة
    المحادثة (15 دقيقة). لازم main.py يسجّل هذي المحادثة *قبل* هاندلر /start
    العام حتى يوصلها /start أصلًا."""
    lang = _lang(context)
    context.user_data.clear()
    from handlers.start import start_command

    await update.message.reply_text(i18n.t("srch_cancelled", lang))
    await start_command(update, context)
    return ConversationHandler.END


async def search_timeout(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """لو العميل توقف بمنتصف البحث بدون إكمال، ننهي المحادثة تلقائيًا بعد فترة
    (بدل ما تبقى عالقة وتسبب ردود غريبة لاحقًا مثل لغة قديمة أو أزرار ما تشتغل)."""
    context.user_data.clear()
    return ConversationHandler.END


# ─────────────────────────── تجميع الـ ConversationHandler ───────────────────────────

def build_search_conversation() -> ConversationHandler:
    return ConversationHandler(
        entry_points=[
            CommandHandler("search", search_entry),
            CallbackQueryHandler(search_entry, pattern="^start_search$"),
        ],
        states={
            SEARCH_PROFESSION: [
                CallbackQueryHandler(choose_search_profession, pattern="^srch_prof:"),
                MessageHandler(filters.TEXT & ~filters.COMMAND, profession_text_fallback),
            ],
            SEARCH_SUBSERVICE: [
                CallbackQueryHandler(choose_search_subservice, pattern="^srch_svc:"),
                CallbackQueryHandler(subservice_done, pattern=f"^{SERVICES_DONE_CB}$"),
                CallbackQueryHandler(skip_subservice, pattern=f"^{SERVICE_ALL_CB}$"),
                CallbackQueryHandler(back_to_search_professions, pattern=f"^{PROFESSION_BACK_CB}$"),
            ],
            SEARCH_REGION: [
                MessageHandler(filters.LOCATION, receive_early_location),
                CallbackQueryHandler(confirm_early_location, pattern=f"^{CONFIRM_LOCATION_CB}$"),
                CallbackQueryHandler(toggle_location_choice, pattern=f"^{LOCATION_TOGGLE_PREFIX}"),
                CallbackQueryHandler(confirm_location_selection, pattern=f"^{LOCATION_NEARBY_DONE_CB}$"),
                CallbackQueryHandler(confirm_location_all_city, pattern=f"^{LOCATION_ALL_CITY_CB}$"),
                CallbackQueryHandler(reject_early_location, pattern=f"^{REJECT_LOCATION_CB}$"),
                CallbackQueryHandler(end_search_results, pattern=f"^{END_SEARCH_CB}$"),
                CallbackQueryHandler(choose_search_region, pattern="^srch_region:"),
                MessageHandler(filters.TEXT & ~filters.COMMAND, region_text_router),
            ],
            SEARCH_CITY: [
                CallbackQueryHandler(choose_search_city, pattern="^srch_city:"),
                CallbackQueryHandler(search_city_page_nav, pattern="^srch_city_page:"),
                CallbackQueryHandler(back_to_search_regions, pattern=f"^{BACK_TO_REGIONS_CB}$"),
                MessageHandler(filters.TEXT & ~filters.COMMAND, city_text_search),
            ],
            SEARCH_NEIGHBORHOOD: [
                CallbackQueryHandler(choose_search_district, pattern="^srch_dist:"),
                CallbackQueryHandler(search_district_page_nav, pattern="^srch_dist_page:"),
                CallbackQueryHandler(skip_neighborhood, pattern=f"^{SKIP_NEIGHBORHOOD_CB}$"),
                MessageHandler(filters.TEXT & ~filters.COMMAND, district_text_search),
            ],
            SEARCH_RESULTS: [
                CallbackQueryHandler(show_more_results, pattern=f"^{MORE_RESULTS_CB}$"),
                CallbackQueryHandler(choose_nearby_district, pattern=f"^{NEARBY_DISTRICT_CB_PREFIX}"),
                CallbackQueryHandler(choose_nearby_city, pattern=f"^{NEARBY_CITY_CB_PREFIX}"),
                CallbackQueryHandler(search_all_city_districts, pattern=f"^{ALL_CITY_DISTRICTS_CB}$"),
                CallbackQueryHandler(manual_district_pick, pattern=f"^{MANUAL_DISTRICT_PICK_CB}$"),
                CallbackQueryHandler(manual_region_pick, pattern=f"^{MANUAL_REGION_PICK_CB}$"),
                CallbackQueryHandler(end_search_results, pattern=f"^{END_SEARCH_CB}$"),
            ],
            ConversationHandler.TIMEOUT: [MessageHandler(filters.ALL, search_timeout)],
        },
        fallbacks=[
            CommandHandler("cancel", cancel_search),
            # نفس فكرة التسجيل: لو العميل عالق بمنتصف بحث قديم، نخليه يقدر يبدأ
            # بحث جديد فورًا بمجرد ما يضغط الزر أو يرسل الأمر من جديد.
            CommandHandler("search", search_entry),
            CallbackQueryHandler(search_entry, pattern="^start_search$"),
            # /start يخرجه من أي بحث عالق ويرجعه للقائمة الرئيسية.
            CommandHandler("start", restart_via_start),
        ],
        name="search_conversation",
        persistent=False,
        conversation_timeout=900,
    )


# هاندلر مستقل (خارج الـ ConversationHandler) لأن زر "تواصل واتساب" قد يُضغط
# حتى بعد ما تنتهي المحادثة (النتائج تبقى ظاهرة برسائل سابقة).
def build_whatsapp_click_handler() -> CallbackQueryHandler:
    return CallbackQueryHandler(whatsapp_click, pattern="^srch_wa:[0-9]+$")


# نفس الفكرة لزر "تواصل تلغرام" المستقل بجانب زر واتساب.
def build_telegram_click_handler() -> CallbackQueryHandler:
    return CallbackQueryHandler(telegram_click, pattern="^srch_tg:[0-9]+$")
