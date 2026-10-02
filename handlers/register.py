# تدفق /register الكامل — 7 خطوات، باستخدام ConversationHandler.
# نجمع البيانات بـ context.user_data خطوة بخطوة، ونحفظها بقاعدة البيانات فقط
# بعد تأكيد الفني النهائي (خطوة 6/7).
#
# دعم تعدد اللغات: نجيب لغة الفني المحفوظة (db.get_user_language) مرة واحدة عند
# الدخول ونخزّنها بـ context.user_data["lang"]، وكل النصوص/الأزرار تُعرض بهذي
# اللغة عبر i18n.t(...). أسماء المدن/الأحياء تبقى عربية دائمًا (بيانات رسمية).

import asyncio
import re

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

import config
import db
import i18n
import professions_repo as professions

(
    CHANNEL_GATE,
    NAME,
    REGION,
    CITY,
    NEIGHBORHOOD,
    WHATSAPP,
    WHATSAPP_CONFIRM,
    TELEGRAM_CONTACT,
    DOMAIN,
    PROFESSION,
    CITY_SCOPE,
    SERVICES,
    CONFIRM,
) = range(13)

CITY_WIDE_YES_CB = "reg_citywide_yes"
CITY_WIDE_NO_CB = "reg_citywide_no"


def _city_scope_keyboard(lang: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton(i18n.t("reg_city_wide_yes_btn", lang), callback_data=CITY_WIDE_YES_CB)],
            [InlineKeyboardButton(i18n.t("reg_city_wide_no_btn", lang), callback_data=CITY_WIDE_NO_CB)],
        ]
    )

CHANNEL_CHECK_CB = "reg_channel_check"


def _channel_gate_keyboard(lang: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton(i18n.t("reg_channel_join_btn", lang), url=config.CHANNEL_URL)],
            [InlineKeyboardButton(i18n.t("reg_channel_check_btn", lang), callback_data=CHANNEL_CHECK_CB)],
        ]
    )


async def _is_subscribed_to_channel(context: ContextTypes.DEFAULT_TYPE, user_id: int) -> bool:
    """يتحقق هل المستخدم مشترك بقناة البوت (config.CHANNEL_USERNAME) فعليًا.

    يحتاج البوت يكون "مشرف" (Admin) بالقناة حتى يقدر يستعلم — لو حصل أي خطأ
    (البوت لسا مو أدمن، القناة غير موجودة...) نسمح بإكمال التسجيل بدل ما نعلّق
    كل المسجّلين الجدد بسبب خطأ إعداد عندنا (fail-open، مع تسجيل تحذير بالسجلات)."""
    try:
        member = await context.bot.get_chat_member(f"@{config.CHANNEL_USERNAME}", user_id)
        is_sub = member.status in ("member", "administrator", "creator")
        print(f"[channel_check] user={user_id} status={member.status!r} subscribed={is_sub}", flush=True)
        return is_sub
    except Exception as e:  # noqa: BLE001 — أي خطأ هنا يعني مشكلة إعداد، مو مشكلة بالمستخدم
        print(f"[channel_check] تعذّر التحقق من اشتراك {user_id} بالقناة: {e}", flush=True)
        return True

BACK_TO_REGIONS_CB = "reg_back_regions"
DISTRICT_TOGGLE_CB_PREFIX = "reg_dist_toggle:"
DISTRICTS_DONE_CB = "reg_dist_done"
HAS_WHATSAPP_YES_CB = "reg_has_wa_yes"
HAS_WHATSAPP_NO_CB = "reg_has_wa_no"
SERVICES_DONE_CB = "reg_services_done"
SERVICES_BACK_CB = "reg_svc_back"
PROFESSION_NOOP_CB = "reg_prof_noop"
CONFIRM_YES_CB = "reg_confirm_yes"
CONFIRM_EDIT_CB = "reg_confirm_edit"  # تعديل المهنة فقط (يرجع لخطوة المجال/المهنة)
CONFIRM_EDIT_ALL_CB = "reg_confirm_edit_all"  # تعديل الكل (يعيد التسجيل من الاسم)

MIN_DISTRICTS = 1
MAX_DISTRICTS = 5  # قرار نهائي: الفني يختار حي واحد على الأقل وخمسة أحياء كحد أقصى

WHATSAPP_RE = re.compile(r"^\+?[0-9]{8,15}$")


def _normalize_sa_whatsapp(number: str) -> str | None:
    """يطبّع رقم الجوال لصيغة دولية موحّدة (+9665XXXXXXXX) مهما كانت الصيغة اللي
    كتبها الفني (0501234567 / 501234567 / 9665012345667 / +966501234567).

    هذا يصلّح مشكلة كانت تحصل فعليًا: الفني يكتب رقمه بصيغة محلية بدون رمز الدولة
    (05xxxxxxxx)، فيُحفظ كما هو ويُبنى منه رابط واتساب (wa.me/05xxxxxxxx) غير صحيح
    دوليًا — فيفتح واتساب فعلاً لكنه يقول للعميل إن الرقم ليس عليه حساب واتساب،
    رغم إن الفني عنده واتساب فعلاً على نفس الرقم بصيغته الصحيحة."""
    digits = re.sub(r"\D", "", number)
    if digits.startswith("00"):
        digits = digits[2:]
    if digits.startswith("966"):
        core = digits[3:]
    elif digits.startswith("0"):
        core = digits[1:]
    else:
        core = digits
    if len(core) != 9 or not core.startswith("5"):
        return None
    return f"+966{core}"

# عدد المدن/الأحياء بكل صفحة أزرار (4 صفوف × عمودين)
GEO_PAGE_SIZE = 8


def _lang(context: ContextTypes.DEFAULT_TYPE) -> str:
    return context.user_data.get("lang", "ar")


# ─────────────────────────── أزرار المنطقة/المدينة/الحي ───────────────────────────

def _region_keyboard() -> InlineKeyboardMarkup:
    buttons, row = [], []
    for r in db.list_sa_regions():
        row.append(InlineKeyboardButton(r["name"], callback_data=f"reg_region:{r['id']}"))
        if len(row) == 2:
            buttons.append(row)
            row = []
    if row:
        buttons.append(row)
    return InlineKeyboardMarkup(buttons)


def _paginated_keyboard(items: list[dict], page: int, item_cb_prefix: str, page_cb_prefix: str, extra_rows: list = None):
    """يبني لوحة أزرار مقسّمة صفحات (عمودين) من قائمة عناصر فيها id/name، مع أزرار تنقّل."""
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
        cities, page, "reg_city:", "reg_city_page:",
        extra_rows=[[InlineKeyboardButton(i18n.t("back_to_regions_btn", lang), callback_data=BACK_TO_REGIONS_CB)]],
    )


def _district_keyboard(city_id: int, page: int, selected_ids: set[int], lang: str) -> InlineKeyboardMarkup:
    """لوحة اختيار متعدد للأحياء (من 1 إلى 5 كحد أقصى)، مع صفحات وعلامة ✅ للمختار."""
    districts = db.list_sa_districts_by_city(city_id)
    total = len(districts)
    start = page * GEO_PAGE_SIZE
    page_items = districts[start:start + GEO_PAGE_SIZE]

    buttons, row = [], []
    for d in page_items:
        mark = "✅ " if d["id"] in selected_ids else "▫️ "
        row.append(InlineKeyboardButton(mark + d["name"], callback_data=f"{DISTRICT_TOGGLE_CB_PREFIX}{d['id']}"))
        if len(row) == 2:
            buttons.append(row)
            row = []
    if row:
        buttons.append(row)

    nav_row = []
    if page > 0:
        nav_row.append(InlineKeyboardButton("◀️", callback_data=f"reg_dist_page:{page - 1}"))
    if start + GEO_PAGE_SIZE < total:
        nav_row.append(InlineKeyboardButton("▶️", callback_data=f"reg_dist_page:{page + 1}"))
    if nav_row:
        buttons.append(nav_row)

    if selected_ids:
        buttons.append(
            [InlineKeyboardButton(
                i18n.t("reg_confirm_selection_btn", lang, count=len(selected_ids), max=MAX_DISTRICTS),
                callback_data=DISTRICTS_DONE_CB,
            )]
        )

    return InlineKeyboardMarkup(buttons)


# ─────────────────────────── أدوات مساعدة ───────────────────────────

def _domain_keyboard(lang: str) -> InlineKeyboardMarkup:
    buttons = []
    row = []
    for d in professions.get_domains(lang):
        row.append(InlineKeyboardButton(d["name"], callback_data=f"reg_dom:{d['id']}"))
        if len(row) == 2:
            buttons.append(row)
            row = []
    if row:
        buttons.append(row)
    return InlineKeyboardMarkup(buttons)


def _profession_keyboard(domain_id: str, lang: str) -> InlineKeyboardMarkup:
    buttons = []
    row = []
    for p in professions.get_professions_by_domain(domain_id, lang):
        row.append(InlineKeyboardButton(p["name"], callback_data=f"reg_prof:{p['id']}"))
        if len(row) == 2:
            buttons.append(row)
            row = []
    if row:
        buttons.append(row)
    buttons.append(
        [InlineKeyboardButton(i18n.t("back_to_domain_btn", lang), callback_data="reg_back_domain")]
    )
    return InlineKeyboardMarkup(buttons)


def _profession_list_grouped_keyboard(lang: str) -> InlineKeyboardMarkup:
    """كل المهن (أيًا كان عددها الحالي) بلوحة واحدة مسطّحة مقسّمة تحت عناوين
    مجالاتها (أقسامها) — نفس فكرة القائمة المسطّحة اللي بنيناها لخطوة بحث
    العميل (_profession_list_keyboard بـ search.py)، مع فرق واحد: هنا نضيف قبل
    مهن كل مجال زر عنوان غير قابل للاستخدام (callback_data ثابت PROFESSION_NOOP_CB)
    يوضّح للفني القسم اللي تنتمي له المهن التالية، بدل ما يضطر يختار المجال أولاً
    بخطوة منفصلة كما كان سابقًا."""
    buttons = []
    for d in professions.get_domains(lang):
        profs = professions.get_professions_by_domain(d["id"], lang)
        if not profs:
            continue
        buttons.append([InlineKeyboardButton(f"── {d['name']} ──", callback_data=PROFESSION_NOOP_CB)])
        row = []
        for p in profs:
            row.append(InlineKeyboardButton(p["name"], callback_data=f"reg_prof:{p['id']}"))
            if len(row) == 2:
                buttons.append(row)
                row = []
        if row:
            buttons.append(row)
    return InlineKeyboardMarkup(buttons)


def _services_keyboard(services: list[str], selected: set[str], lang: str) -> InlineKeyboardMarkup:
    """نستخدم رقم ترتيب الخدمة (index) بدل نصها الكامل داخل callback_data، لأن
    تلغرام يفرض حد أقصى 64 بايت على callback_data. بعض أسماء الخدمات العربية
    الطويلة (مثل خدمة تابعة لـ"كهربائي منازل") تتجاوز هذا الحد بمجرد إضافة
    البادئة "reg_svc:"، فيرفض تلغرام الزر بصمت وتفشل شاشة الخدمات بالكامل —
    وهذا كان السبب الحقيقي وراء "رفض" تسجيل هذه المهنة تحديدًا."""
    buttons = []
    for idx, s in enumerate(services):
        mark = "✅ " if s in selected else "▫️ "
        buttons.append([InlineKeyboardButton(mark + s, callback_data=f"reg_svc:{idx}")])
    buttons.append(
        [InlineKeyboardButton(i18n.t("reg_services_done_btn", lang), callback_data=SERVICES_DONE_CB)]
    )
    # زر رجوع لقائمة المهن — يتيح للفني يستكشف مهنة ثانية بنفس المجال قبل ما يقرر
    buttons.append(
        [InlineKeyboardButton(i18n.t("reg_back_to_profession_btn", lang), callback_data=SERVICES_BACK_CB)]
    )
    return InlineKeyboardMarkup(buttons)


def _summary_text(ud: dict, lang: str) -> str:
    services = ud.get("services") or []
    services_text = "، ".join(services) if services else i18n.t("no_services", lang)
    if ud.get("covers_whole_city"):
        neighborhoods_text = i18n.t("reg_summary_whole_city", lang)
    else:
        neighborhoods_text = ud.get("neighborhood") or i18n.t("not_specified", lang)
    wa_label = i18n.t("wa_label_yes", lang) if ud.get("has_whatsapp", True) else i18n.t("wa_label_no", lang)
    body = i18n.t(
        "reg_summary_body", lang,
        name=ud["full_name"], city=ud["city"], districts=neighborhoods_text,
        contact=ud["whatsapp_number"], wa_label=wa_label,
        telegram=ud.get("telegram_contact_number") or i18n.t("not_available", lang),
        profession=ud["profession_name"], services=services_text,
    )
    return i18n.t("reg_summary_title", lang) + "\n\n" + body


def _confirm_keyboard(lang: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton(i18n.t("reg_confirm_btn", lang), callback_data=CONFIRM_YES_CB)],
            [InlineKeyboardButton(i18n.t("reg_edit_btn", lang), callback_data=CONFIRM_EDIT_CB)],
            [InlineKeyboardButton(i18n.t("reg_edit_all_btn", lang), callback_data=CONFIRM_EDIT_ALL_CB)],
        ]
    )


# ─────────────────────────── الخطوة 1: الاسم ───────────────────────────

async def register_entry(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    lang = await asyncio.to_thread(db.get_user_language, update.effective_user.id)
    context.user_data["lang"] = lang
    target = update.message or update.callback_query.message
    if update.callback_query:
        await update.callback_query.answer()

    # يسمح بمهنة واحدة فقط لكل حساب/رقم — لو عنده تسجيل قائم (نشط أو مرفوض لا)
    # نمنع تسجيل مهنة ثانية بنفس الحساب ونوجّهه لاستخدام رقم مختلف.
    existing = await asyncio.to_thread(db.get_professional_by_telegram_id, update.effective_user.id)
    if existing and existing["status"] != db.STATUS_REJECTED:
        await target.reply_text(
            i18n.t("reg_already_registered", lang, profession=existing["profession_name"])
        )
        return ConversationHandler.END

    if not await _is_subscribed_to_channel(context, update.effective_user.id):
        await target.reply_text(
            i18n.t("reg_channel_gate", lang),
            reply_markup=_channel_gate_keyboard(lang),
        )
        return CHANNEL_GATE

    await target.reply_text(
        i18n.t("reg_start", lang),
        reply_markup=ReplyKeyboardRemove(),
    )
    return NAME


async def channel_check(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lang = _lang(context)
    query = update.callback_query

    if not await _is_subscribed_to_channel(context, update.effective_user.id):
        # answer() تُستدعى مرة وحدة فقط لكل ضغطة زر — هنا نستخدمها لعرض تنبيه منبثق
        # بدل رسالة عادية، لأنه الحالة الأكثر احتمالًا (نسي يشترك فعليًا).
        await query.answer(i18n.t("reg_channel_not_joined", lang), show_alert=True)
        return CHANNEL_GATE

    await query.answer()
    await query.edit_message_text(i18n.t("reg_start", lang))
    return NAME


async def got_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lang = _lang(context)
    name = update.message.text.strip()
    if len(name) < 3:
        await update.message.reply_text(i18n.t("reg_name_short", lang))
        return NAME
    context.user_data["full_name"] = name
    await update.message.reply_text(i18n.t("reg_ask_region", lang), reply_markup=_region_keyboard())
    return REGION


# ─────────────────────────── الخطوة 2: المنطقة → المدينة → الحي ───────────────────────────

async def choose_region(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lang = _lang(context)
    query = update.callback_query
    await query.answer()
    region_id = int(query.data.split(":", 1)[1])
    region = await asyncio.to_thread(db.get_sa_region_by_id, region_id)
    if not region:
        await query.edit_message_text(i18n.t("unknown_option", lang), reply_markup=_region_keyboard())
        return REGION

    context.user_data["region_id"] = region_id
    await query.edit_message_text(
        i18n.t("reg_region_selected", lang, region=region["name"]),
        reply_markup=_city_keyboard(region_id, page=0, lang=lang),
    )
    return CITY


async def back_to_regions(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lang = _lang(context)
    query = update.callback_query
    await query.answer()
    await query.edit_message_text(i18n.t("reg_ask_region", lang), reply_markup=_region_keyboard())
    return REGION


async def city_text_search(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """اكتمال تلقائي: يكتب الفني جزء من اسم مدينته بدل تصفح الصفحات."""
    lang = _lang(context)
    region_id = context.user_data.get("region_id")
    if not region_id:
        await update.message.reply_text(i18n.t("reg_ask_region", lang), reply_markup=_region_keyboard())
        return REGION

    query_text = update.message.text.strip()
    matches = await asyncio.to_thread(db.search_sa_major_cities, region_id, query_text)
    if not matches:
        await update.message.reply_text(
            i18n.t("reg_city_not_found", lang),
            reply_markup=_city_keyboard(region_id, page=0, lang=lang),
        )
        return CITY

    buttons, row = [], []
    for c in matches:
        row.append(InlineKeyboardButton(c["name"], callback_data=f"reg_city:{c['id']}"))
        if len(row) == 2:
            buttons.append(row)
            row = []
    if row:
        buttons.append(row)
    buttons.append([InlineKeyboardButton(i18n.t("back_to_regions_btn", lang), callback_data=BACK_TO_REGIONS_CB)])

    await update.message.reply_text(i18n.t("matched_results", lang), reply_markup=InlineKeyboardMarkup(buttons))
    return CITY


async def city_page_nav(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lang = _lang(context)
    query = update.callback_query
    await query.answer()
    page = int(query.data.split(":", 1)[1])
    region_id = context.user_data["region_id"]
    await query.edit_message_reply_markup(reply_markup=_city_keyboard(region_id, page, lang))
    return CITY


async def choose_city(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lang = _lang(context)
    query = update.callback_query
    await query.answer()
    city_id = int(query.data.split(":", 1)[1])
    city = await asyncio.to_thread(db.get_sa_city_by_id, city_id)
    if not city:
        await query.edit_message_text(i18n.t("unknown_option", lang))
        return CITY

    context.user_data["city_id"] = city_id
    context.user_data["city"] = city["name"]
    context.user_data["district_page"] = 0
    context.user_data["selected_district_ids"] = []
    await query.edit_message_text(
        i18n.t("reg_district_step", lang, city=city["name"], max=MAX_DISTRICTS),
        reply_markup=_district_keyboard(city_id, page=0, selected_ids=set(), lang=lang),
    )
    return NEIGHBORHOOD


async def district_page_nav(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lang = _lang(context)
    query = update.callback_query
    await query.answer()
    page = int(query.data.split(":", 1)[1])
    city_id = context.user_data["city_id"]
    context.user_data["district_page"] = page
    selected = set(context.user_data.get("selected_district_ids", []))
    await query.edit_message_reply_markup(reply_markup=_district_keyboard(city_id, page, selected, lang))
    return NEIGHBORHOOD


async def district_text_search(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """اكتمال تلقائي: يكتب الفني جزء من اسم الحي بدل تصفح الصفحات، مع المحافظة
    على أي أحياء اختارها سابقًا (اختيار متعدد)."""
    lang = _lang(context)
    city_id = context.user_data.get("city_id")
    if not city_id:
        await update.message.reply_text(i18n.t("unknown_option", lang))
        return CITY

    selected = set(context.user_data.get("selected_district_ids", []))
    query_text = update.message.text.strip()
    matches = await asyncio.to_thread(db.search_sa_districts, city_id, query_text)
    if not matches:
        await update.message.reply_text(
            i18n.t("reg_district_not_found", lang),
            reply_markup=_district_keyboard(
                city_id, page=context.user_data.get("district_page", 0), selected_ids=selected, lang=lang
            ),
        )
        return NEIGHBORHOOD

    buttons, row = [], []
    for d in matches:
        mark = "✅ " if d["id"] in selected else "▫️ "
        row.append(InlineKeyboardButton(mark + d["name"], callback_data=f"{DISTRICT_TOGGLE_CB_PREFIX}{d['id']}"))
        if len(row) == 2:
            buttons.append(row)
            row = []
    if row:
        buttons.append(row)
    if selected:
        buttons.append(
            [InlineKeyboardButton(
                i18n.t("reg_confirm_selection_btn", lang, count=len(selected), max=MAX_DISTRICTS),
                callback_data=DISTRICTS_DONE_CB,
            )]
        )

    await update.message.reply_text(i18n.t("matched_results", lang), reply_markup=InlineKeyboardMarkup(buttons))
    return NEIGHBORHOOD


async def toggle_district(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lang = _lang(context)
    query = update.callback_query
    district_id = int(query.data.split(":", 1)[1])
    selected = list(context.user_data.get("selected_district_ids", []))

    if district_id in selected:
        selected.remove(district_id)
    elif len(selected) >= MAX_DISTRICTS:
        await query.answer(i18n.t("reg_max_district_alert", lang, max=MAX_DISTRICTS), show_alert=True)
        return NEIGHBORHOOD
    else:
        selected.append(district_id)

    context.user_data["selected_district_ids"] = selected
    await query.answer()

    city_id = context.user_data["city_id"]
    page = context.user_data.get("district_page", 0)
    await query.edit_message_reply_markup(
        reply_markup=_district_keyboard(city_id, page, set(selected), lang)
    )
    return NEIGHBORHOOD


async def districts_done(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lang = _lang(context)
    query = update.callback_query
    selected_ids = context.user_data.get("selected_district_ids", [])
    if len(selected_ids) < MIN_DISTRICTS:
        await query.answer(i18n.t("reg_min_district_alert", lang), show_alert=True)
        return NEIGHBORHOOD
    await query.answer()

    districts = await asyncio.to_thread(db.list_sa_districts_by_city, context.user_data["city_id"])
    by_id = {d["id"]: d for d in districts}
    chosen = [by_id[did] for did in selected_ids if did in by_id]

    context.user_data["district_ids"] = [d["id"] for d in chosen]
    context.user_data["neighborhood"] = "، ".join(d["name"] for d in chosen)
    return await _ask_whatsapp(query.message, context)


async def _ask_whatsapp(message, context: ContextTypes.DEFAULT_TYPE):
    await message.reply_text(i18n.t("reg_ask_contact_number", _lang(context)))
    return WHATSAPP


# ─────────────────────────── الخطوة 3: أرقام التواصل ───────────────────────────

async def got_whatsapp(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lang = _lang(context)
    raw = update.message.text.strip().replace(" ", "")
    if not WHATSAPP_RE.match(raw):
        await update.message.reply_text(i18n.t("reg_invalid_number", lang))
        return WHATSAPP
    normalized = _normalize_sa_whatsapp(raw)
    if not normalized:
        await update.message.reply_text(i18n.t("reg_invalid_number", lang))
        return WHATSAPP
    context.user_data["whatsapp_number"] = normalized

    keyboard = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(i18n.t("has_whatsapp_yes_btn", lang), callback_data=HAS_WHATSAPP_YES_CB),
                InlineKeyboardButton(i18n.t("has_whatsapp_no_btn", lang), callback_data=HAS_WHATSAPP_NO_CB),
            ]
        ]
    )
    await update.message.reply_text(i18n.t("reg_ask_has_whatsapp", lang), reply_markup=keyboard)
    return WHATSAPP_CONFIRM


async def confirm_has_whatsapp(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lang = _lang(context)
    query = update.callback_query
    await query.answer()
    has_wa = query.data == HAS_WHATSAPP_YES_CB
    context.user_data["has_whatsapp"] = has_wa
    label = i18n.t("wa_label_yes", lang) if has_wa else i18n.t("wa_label_no", lang)
    await query.edit_message_text(i18n.t("reg_wa_saved", lang, label=label))
    return await _ask_telegram_contact(query.message, context)


async def _ask_telegram_contact(message, context: ContextTypes.DEFAULT_TYPE):
    lang = _lang(context)
    contact_button = KeyboardButton(i18n.t("reg_telegram_share_btn", lang), request_contact=True)
    keyboard = ReplyKeyboardMarkup(
        [[contact_button]], resize_keyboard=True, one_time_keyboard=True
    )
    await message.reply_text(i18n.t("reg_ask_telegram_contact", lang), reply_markup=keyboard)
    return TELEGRAM_CONTACT


async def got_telegram_contact(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lang = _lang(context)
    contact = update.message.contact
    if contact is None or contact.user_id != update.effective_user.id:
        await update.message.reply_text(i18n.t("reg_telegram_retry", lang))
        return TELEGRAM_CONTACT

    context.user_data["telegram_contact_number"] = contact.phone_number
    await update.message.reply_text(
        i18n.t("reg_profession_prompt", lang),
        reply_markup=ReplyKeyboardRemove(),
    )
    keyboard = await asyncio.to_thread(_profession_list_grouped_keyboard, lang)
    await update.message.reply_text(
        i18n.t("reg_all_professions_list", lang), reply_markup=keyboard
    )
    return PROFESSION


# ─────────────────────────── الخطوة 3 (بديل): المهنة (كل المهن مع أقسامها) ───────────────────────────

async def profession_list_noop(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """زر عنوان القسم غير قابل للاستخدام — فقط يرد على الضغطة بصمت لو أحد
    ضغطه بالخطأ (تلغرام يظهر ساعة تحميل على الزر لو ما رددنا على الاستعلام)."""
    await update.callback_query.answer()
    return PROFESSION


async def choose_profession(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lang = _lang(context)
    query = update.callback_query
    await query.answer()
    profession_id = query.data.split(":", 1)[1]
    domain, profession = await asyncio.to_thread(professions.get_profession, profession_id, lang)
    if not profession:
        keyboard = await asyncio.to_thread(_profession_list_grouped_keyboard, lang)
        await query.edit_message_text(
            i18n.t("unknown_option", lang), reply_markup=keyboard
        )
        return PROFESSION

    context.user_data["domain_id"] = domain["id"] if domain else None
    context.user_data["domain_name"] = domain["name"] if domain else ""
    context.user_data["profession_id"] = profession_id
    context.user_data["profession_name"] = profession["name"]
    context.user_data["available_services"] = profession["services"]
    context.user_data["services"] = []
    context.user_data["covers_whole_city"] = False

    # مهنة نادرة (علّمها الأدمن من لوحة التحكم) — نعرض خيار تغطية المدينة كاملة
    # بدل الاكتفاء بالأحياء اللي اختارها الفني قبل شوي (حد أقصى 5)، لأن قلة
    # عدد الفنيين بهذي المهنة تخليهم يختفون عن عملاء بأحياء ثانية بنفس المدينة.
    if profession.get("allow_city_wide"):
        await query.edit_message_text(
            i18n.t("reg_city_wide_prompt", lang, city=context.user_data.get("city", "")),
            reply_markup=_city_scope_keyboard(lang),
        )
        return CITY_SCOPE

    return await _proceed_after_profession(query, context, lang)


async def choose_city_scope(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lang = _lang(context)
    query = update.callback_query
    await query.answer()
    context.user_data["covers_whole_city"] = query.data == CITY_WIDE_YES_CB
    return await _proceed_after_profession(query, context, lang)


async def _proceed_after_profession(query, context: ContextTypes.DEFAULT_TYPE, lang: str):
    """بعد تحديد المهنة (ونطاق التغطية لو مهنة نادرة)، يكمل لخطوة الخدمات الفرعية
    لو موجودة، وإلا يروح مباشرة لشاشة المراجعة النهائية."""
    available_services = context.user_data.get("available_services", [])
    if available_services:
        await query.edit_message_text(
            i18n.t("reg_services_prompt", lang, profession=context.user_data["profession_name"]),
            reply_markup=_services_keyboard(available_services, set(), lang),
        )
        return SERVICES

    # لا توجد خدمات فرعية — نروح مباشرة لشاشة المراجعة
    await query.edit_message_text(_summary_text(context.user_data, lang), reply_markup=_confirm_keyboard(lang))
    return CONFIRM


# ─────────────────────────── الخطوة 5: الخدمات الفرعية ───────────────────────────

async def toggle_service(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lang = _lang(context)
    query = update.callback_query
    available = context.user_data.get("available_services", [])
    try:
        idx = int(query.data.split(":", 1)[1])
        service = available[idx]
    except (ValueError, IndexError):
        await query.answer()
        return SERVICES
    selected = set(context.user_data.get("services", []))
    if service in selected:
        selected.discard(service)
    else:
        selected.add(service)
    context.user_data["services"] = list(selected)
    await query.answer()

    await query.edit_message_reply_markup(
        reply_markup=_services_keyboard(available, selected, lang)
    )
    return SERVICES


async def services_done(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lang = _lang(context)
    query = update.callback_query
    await query.answer()
    await query.edit_message_text(_summary_text(context.user_data, lang), reply_markup=_confirm_keyboard(lang))
    return CONFIRM


# ─────────────────────────── الخطوة 6-7: المراجعة والتأكيد ───────────────────────────

async def confirm_edit(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """تعديل المهنة فقط: يرجع لقائمة كل المهن (مع أقسامها)، محتفظًا بباقي البيانات
    (الاسم، الموقع، أرقام التواصل) — يسمح للفني يستكشف مهنة ثانية قبل ما يقرر،
    بدون ما يعيد كتابة كل بياناته من الصفر."""
    lang = _lang(context)
    query = update.callback_query
    await query.answer()
    keyboard = await asyncio.to_thread(_profession_list_grouped_keyboard, lang)
    await query.edit_message_text(
        i18n.t("reg_edit_profession_note", lang),
        reply_markup=keyboard,
    )
    return PROFESSION


async def confirm_edit_all(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # تعديل الكل: نعيد البدء من الخطوة 1 بالكامل
    lang = _lang(context)
    query = update.callback_query
    await query.answer()
    context.user_data.clear()
    context.user_data["lang"] = lang
    await query.edit_message_text(i18n.t("reg_restart", lang))
    return NAME


async def back_to_profession_from_services(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """زر رجوع من خطوة الخدمات لقائمة كل المهن (مع أقسامها) — يتيح استكشاف مهنة
    ثانية (بخدماتها) قبل الاستقرار على واحدة، بدل ما يضطر يلغي التسجيل بالكامل."""
    lang = _lang(context)
    query = update.callback_query
    await query.answer()
    keyboard = await asyncio.to_thread(_profession_list_grouped_keyboard, lang)
    await query.edit_message_text(
        i18n.t("reg_all_professions_list", lang),
        reply_markup=keyboard,
    )
    return PROFESSION


async def confirm_yes(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lang = _lang(context)
    query = update.callback_query
    await query.answer()

    ud = context.user_data
    row_id = await asyncio.to_thread(
        db.create_registration,
        {
            "telegram_user_id": update.effective_user.id,
            "full_name": ud["full_name"],
            "city": ud["city"],
            "neighborhood": ud.get("neighborhood"),
            "district_ids": ud.get("district_ids", []),
            "whatsapp_number": ud["whatsapp_number"],
            "has_whatsapp": ud.get("has_whatsapp", True),
            "telegram_contact_number": ud.get("telegram_contact_number"),
            "domain_name": ud["domain_name"],
            "profession_id": ud["profession_id"],
            "profession_name": ud["profession_name"],
            "services": ud.get("services", []),
            "covers_whole_city": ud.get("covers_whole_city", False),
        },
    )

    await query.edit_message_text(
        i18n.t(
            "reg_success", lang,
            name=ud["full_name"], city=ud["city"], profession=ud["profession_name"],
        )
    )

    # معاينة بطاقته كما بيشوفها العميل بالضبط — حتى يرتاح ويفهم شكل ظهوره، ونفس
    # الدالة اللي تُستخدم فعليًا بنتائج البحث (handlers/search.py) عشان تكون مطابقة
    # 100% لما بيشوفه العميل الحقيقي، بدون أي تكرار للمنطق.
    from handlers.search import _professional_card_text

    saved = await asyncio.to_thread(db.get_professional_by_id, row_id)
    if saved:
        await query.message.reply_text(i18n.t("reg_card_preview_intro", lang))
        await query.message.reply_text(_professional_card_text(saved))

    # إشعار الأدمن — نستورد هنا لتفادي استيراد دائري بين register.py و admin.py
    from handlers.admin import notify_admin_new_registration

    await notify_admin_new_registration(context, row_id)

    context.user_data.clear()
    return ConversationHandler.END


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lang = _lang(context)
    context.user_data.clear()
    await update.message.reply_text(
        i18n.t("reg_cancelled", lang),
        reply_markup=ReplyKeyboardRemove(),
    )
    return ConversationHandler.END


async def restart_via_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """لو المستخدم أرسل /start وهو عالق بمنتصف محادثة تسجيل (بأي خطوة)، نخرجه
    منها فورًا ونعرض له القائمة الرئيسية من جديد — بدل ما يبقى "محشور" بمحادثة
    قديمة ما تستجيب صح لباقي أوامره لين تنتهي مهلتها (15 دقيقة). هذا الهاندلر
    مسجَّل كـ fallback هنا، ومهم إن هاندلرز /register و/search بـ main.py تُسجَّل
    *قبل* هاندلر /start العام، وإلا هذا الكود ما بيوصله /start أبدًا."""
    context.user_data.clear()
    from handlers.start import start_command

    await update.message.reply_text(i18n.t("reg_cancelled", lang=_lang(context)), reply_markup=ReplyKeyboardRemove())
    await start_command(update, context)
    return ConversationHandler.END


async def registration_timeout(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """لو المستخدم توقف بمنتصف التسجيل بدون إكمال أو إلغاء، ننهي المحادثة تلقائيًا
    بعد فترة (بدل ما تبقى عالقة للأبد وتسبب ردود غريبة لاحقًا مثل لغة قديمة)."""
    context.user_data.clear()
    return ConversationHandler.END




# ─────────────────────────── تجميع الـ ConversationHandler ───────────────────────────

def build_register_conversation() -> ConversationHandler:
    return ConversationHandler(
        entry_points=[
            CommandHandler("register", register_entry),
            CallbackQueryHandler(register_entry, pattern="^start_register$"),
        ],
        states={
            CHANNEL_GATE: [CallbackQueryHandler(channel_check, pattern=f"^{CHANNEL_CHECK_CB}$")],
            NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, got_name)],
            REGION: [CallbackQueryHandler(choose_region, pattern="^reg_region:")],
            CITY: [
                CallbackQueryHandler(choose_city, pattern="^reg_city:"),
                CallbackQueryHandler(city_page_nav, pattern="^reg_city_page:"),
                CallbackQueryHandler(back_to_regions, pattern=f"^{BACK_TO_REGIONS_CB}$"),
                MessageHandler(filters.TEXT & ~filters.COMMAND, city_text_search),
            ],
            NEIGHBORHOOD: [
                CallbackQueryHandler(districts_done, pattern=f"^{DISTRICTS_DONE_CB}$"),
                CallbackQueryHandler(toggle_district, pattern=f"^{DISTRICT_TOGGLE_CB_PREFIX}"),
                CallbackQueryHandler(district_page_nav, pattern="^reg_dist_page:"),
                MessageHandler(filters.TEXT & ~filters.COMMAND, district_text_search),
            ],
            WHATSAPP: [MessageHandler(filters.TEXT & ~filters.COMMAND, got_whatsapp)],
            WHATSAPP_CONFIRM: [
                CallbackQueryHandler(confirm_has_whatsapp, pattern=f"^{HAS_WHATSAPP_YES_CB}$|^{HAS_WHATSAPP_NO_CB}$"),
            ],
            TELEGRAM_CONTACT: [
                MessageHandler(filters.CONTACT | (filters.TEXT & ~filters.COMMAND), got_telegram_contact)
            ],
            PROFESSION: [
                CallbackQueryHandler(choose_profession, pattern="^reg_prof:"),
                CallbackQueryHandler(profession_list_noop, pattern=f"^{PROFESSION_NOOP_CB}$"),
            ],
            CITY_SCOPE: [
                CallbackQueryHandler(choose_city_scope, pattern=f"^{CITY_WIDE_YES_CB}$|^{CITY_WIDE_NO_CB}$"),
            ],
            SERVICES: [
                CallbackQueryHandler(services_done, pattern=f"^{SERVICES_DONE_CB}$"),
                CallbackQueryHandler(back_to_profession_from_services, pattern=f"^{SERVICES_BACK_CB}$"),
                CallbackQueryHandler(toggle_service, pattern="^reg_svc:"),
            ],
            CONFIRM: [
                CallbackQueryHandler(confirm_yes, pattern=f"^{CONFIRM_YES_CB}$"),
                CallbackQueryHandler(confirm_edit_all, pattern=f"^{CONFIRM_EDIT_ALL_CB}$"),
                CallbackQueryHandler(confirm_edit, pattern=f"^{CONFIRM_EDIT_CB}$"),
            ],
            ConversationHandler.TIMEOUT: [MessageHandler(filters.ALL, registration_timeout)],
        },
        fallbacks=[
            CommandHandler("cancel", cancel),
            # لو المستخدم عالق بمنتصف محاولة تسجيل قديمة (ما أكملها ولا ألغاها)،
            # نخليه يقدر يبدأ من جديد فورًا بمجرد ما يضغط زر التسجيل أو يرسل الأمر
            # من جديد، بدل ما ينتظر 15 دقيقة (conversation_timeout) بدون أي استجابة.
            CommandHandler("register", register_entry),
            CallbackQueryHandler(register_entry, pattern="^start_register$"),
            # /start يخرجه من أي محادثة تسجيل عالقة ويرجعه للقائمة الرئيسية —
            # لازم main.py يسجّل هذي المحادثة *قبل* هاندلر /start العام.
            CommandHandler("start", restart_via_start),
        ],
        name="register_conversation",
        persistent=False,
        conversation_timeout=900,
    )
