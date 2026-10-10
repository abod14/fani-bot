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
import countries
import db
import i18n
import professions_repo as professions

(
    CHANNEL_GATE,
    NAME,
    COUNTRY,
    REGION,
    CITY,
    NEIGHBORHOOD,
    WHATSAPP,
    WHATSAPP_CONFIRM,
    TELEGRAM_CONTACT,
    DOMAIN,
    PROFESSION,
    CITY_SCOPE,  # لم تعد مستخدمة (صار خيار «المدينة كاملة» داخل شاشة الأحياء) — باقية للتوافق
    SERVICES,
    CONFIRM,
    SECOND_PROF,
) = range(15)
PROF_MISSING = 15   # «مهنتي غير موجودة»: ينتظر اسم المهنة نصًا
PROF_MISSING_CB = "reg_prof_missing"

ADD_SECOND_CB = "reg_add_second"
NO_SECOND_CB = "reg_no_second"
WHOLE_CITY_CB = "reg_whole_city"

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
COUNTRY_CB_PREFIX = "reg_country:"
CHANGE_COUNTRY_CB = "reg_change_country"
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


def _normalize_sa_whatsapp(number: str) -> str | None:  # للتوافق — الاستخدام الفعلي الآن countries.normalize_phone
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

def _country_keyboard(codes: list[str], lang: str) -> InlineKeyboardMarkup:
    buttons, row = [], []
    for code in codes:
        row.append(InlineKeyboardButton(countries.label(code, lang), callback_data=f"{COUNTRY_CB_PREFIX}{code}"))
        if len(row) == 2:
            buttons.append(row)
            row = []
    if row:
        buttons.append(row)
    return InlineKeyboardMarkup(buttons)


def _region_keyboard(country: str = countries.DEFAULT_COUNTRY, lang: str = "ar") -> InlineKeyboardMarkup:
    buttons, row = [], []
    for r in db.list_sa_regions(country):
        row.append(InlineKeyboardButton(r["name"], callback_data=f"reg_region:{r['id']}"))
        if len(row) == 2:
            buttons.append(row)
            row = []
    if row:
        buttons.append(row)
    if len(countries.enabled_codes("tg")) > 1:
        buttons.append([InlineKeyboardButton(i18n.t("change_country_btn", lang), callback_data=CHANGE_COUNTRY_CB)])
    return InlineKeyboardMarkup(buttons)


def _city_back_cb(ud: dict) -> str | None:
    """زر الرجوع تحت قائمة المدن: للمناطق عادةً — لكن لو الدولة فيها منطقة وحدة بس
    (الكويت/البحرين/قطر) ما فيه قائمة مناطق نرجع لها، فنرجع لاختيار الدولة."""
    if ud.get("region_count", 2) > 1:
        return BACK_TO_REGIONS_CB
    return CHANGE_COUNTRY_CB if len(countries.enabled_codes("tg")) > 1 else None


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


def _back_row(back_cb: str | None, lang: str) -> list:
    if back_cb == BACK_TO_REGIONS_CB:
        return [[InlineKeyboardButton(i18n.t("back_to_regions_btn", lang), callback_data=BACK_TO_REGIONS_CB)]]
    if back_cb == CHANGE_COUNTRY_CB:
        return [[InlineKeyboardButton(i18n.t("change_country_btn", lang), callback_data=CHANGE_COUNTRY_CB)]]
    return []


def _city_keyboard(region_id: int, page: int, lang: str, back_cb: str | None = BACK_TO_REGIONS_CB) -> InlineKeyboardMarkup:
    cities = db.list_sa_major_cities_by_region(region_id)
    return _paginated_keyboard(
        cities, page, "reg_city:", "reg_city_page:", extra_rows=_back_row(back_cb, lang),
    )


def _district_keyboard(city_id: int, page: int, selected_ids: set[int], lang: str,
                      allow_whole: bool = False) -> InlineKeyboardMarkup:
    """لوحة اختيار متعدد للأحياء (من 1 إلى 5 كحد أقصى)، مع صفحات وعلامة ✅ للمختار.
    allow_whole: مهنة نادرة — زر «أغطي المدينة كاملة» أول القائمة بدل اختيار أحياء."""
    districts = db.list_sa_districts_by_city(city_id)
    total = len(districts)
    start = page * GEO_PAGE_SIZE
    page_items = districts[start:start + GEO_PAGE_SIZE]

    buttons, row = [], []
    if allow_whole:
        buttons.append([InlineKeyboardButton(i18n.t("reg_whole_city_btn", lang), callback_data=WHOLE_CITY_CB)])
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
    # الكويت/البحرين: البوت يتخطى المنطقة والمدينة ويوصل هنا مباشرة — بدون هالزر الفني
    # ما يقدر يرجع يغيّر دولته لو اختارها بالغلط
    if len(countries.enabled_codes("tg")) > 1:
        buttons.append([InlineKeyboardButton(i18n.t("change_country_btn", lang), callback_data=CHANGE_COUNTRY_CB)])

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


def _profession_list_grouped_keyboard(lang: str, exclude: str | None = None, skip_btn: bool = False) -> InlineKeyboardMarkup:
    """كل المهن (أيًا كان عددها الحالي) بلوحة واحدة مسطّحة مقسّمة تحت عناوين
    مجالاتها (أقسامها) — نفس فكرة القائمة المسطّحة اللي بنيناها لخطوة بحث
    العميل (_profession_list_keyboard بـ search.py)، مع فرق واحد: هنا نضيف قبل
    مهن كل مجال زر عنوان غير قابل للاستخدام (callback_data ثابت PROFESSION_NOOP_CB)
    يوضّح للفني القسم اللي تنتمي له المهن التالية، بدل ما يضطر يختار المجال أولاً
    بخطوة منفصلة كما كان سابقًا."""
    buttons = []
    if skip_btn:
        buttons.append([InlineKeyboardButton(i18n.t("reg_skip_second_btn", lang), callback_data=NO_SECOND_CB)])
    for d in professions.get_domains(lang):
        profs = [p for p in professions.get_professions_by_domain(d["id"], lang) if p["id"] != exclude]
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
    if not skip_btn:   # المهنة الأولى فقط: آخر خيار «مهنتي غير موجودة» (طلب المالك)
        buttons.append([InlineKeyboardButton(i18n.t("reg_missing_btn", lang), callback_data=PROF_MISSING_CB)])
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


def _professions_text(ud: dict) -> str:
    return f"{ud['profession_name']} • {ud['profession2_name']}" if ud.get("profession2_name") else ud["profession_name"]


def _all_services(ud: dict) -> list:
    out = []
    for s_ in (ud.get("services") or []) + (ud.get("services2") or []):
        if s_ not in out:
            out.append(s_)
    return out


def _summary_text(ud: dict, lang: str) -> str:
    services = _all_services(ud)
    services_text = "، ".join(services) if services else i18n.t("no_services", lang)
    if ud.get("covers_whole_city"):
        neighborhoods_text = i18n.t("reg_summary_whole_city", lang)
    else:
        neighborhoods_text = ud.get("neighborhood") or i18n.t("not_specified", lang)
    wa_label = i18n.t("wa_label_yes", lang) if ud.get("has_whatsapp", True) else i18n.t("wa_label_no", lang)
    city_text = f"{ud['city']}، {countries.name(ud.get('country'), lang)}"
    body = i18n.t(
        "reg_summary_body", lang,
        name=ud["full_name"], city=city_text, districts=neighborhoods_text,
        contact=ud["whatsapp_number"], wa_label=wa_label,
        telegram=ud.get("telegram_contact_number") or i18n.t("not_available", lang),
        profession=_professions_text(ud), services=services_text,
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
    # نحافظ على وسم المصدر (لو محفوظ من /start برابط فيه ?start=...) قبل ما نمسح
    # user_data بالكامل، حتى نقدر نربطه بالتسجيل لو أكمل الفني.
    kept = {k: context.user_data[k] for k in ("source", "referrer_id") if k in context.user_data}
    context.user_data.clear()
    context.user_data.update(kept)
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
            i18n.t("reg_already_registered", lang, profession=db.profession_display(existing))
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
    name = db.arabic_name(update.message.text, min_len=3)   # طلب المالك: عربي أو إنجليزي فقط (لا الأوردو)
    if not name:
        await update.message.reply_text(i18n.t("reg_name_arabic", lang))
        return NAME
    context.user_data["full_name"] = name
    # الترتيب الجديد: المهنة قبل الموقع — عشان لو مهنته نادرة نعرض له «المدينة كاملة»
    # مباشرة بشاشة الأحياء بدل ما يختار أحياء وبعدين ينسأل.
    context.user_data["picking"] = 1
    keyboard = await asyncio.to_thread(_profession_list_grouped_keyboard, lang)
    await update.message.reply_text(i18n.t("reg_profession_prompt", lang), reply_markup=keyboard)
    return PROFESSION


# ─────────────────────────── الخطوة 2: المنطقة → المدينة → الحي ───────────────────────────

async def _location_step(context: ContextTypes.DEFAULT_TYPE, lang: str, country: str | None = None,
                         region_id: int | None = None):
    """يرجّع (نص، أزرار، الحالة التالية) لخطوة الموقع التالية: الدولة ← المنطقة ←
    المدينة ← الأحياء — مع تخطي تلقائي لأي خطوة فيها خيار واحد بس (مثلًا الكويت:
    منطقة وحدة ومدينة وحدة، فيروح الفني مباشرة لاختيار مناطقه)."""
    ud = context.user_data
    if region_id is None:
        if country is None:
            enabled = await asyncio.to_thread(countries.enabled_codes, "tg")
            if len(enabled) != 1:
                return i18n.t("reg_ask_country_work", lang), _country_keyboard(enabled, lang), COUNTRY
            country = enabled[0]
        ud["country"] = country
        regions = await asyncio.to_thread(db.list_sa_regions, country)
        ud["region_count"] = len(regions)
        if len(regions) != 1:
            markup = await asyncio.to_thread(_region_keyboard, country, lang)
            return i18n.t("reg_ask_region", lang), markup, REGION
        region_id = regions[0]["id"]

    region = await asyncio.to_thread(db.get_sa_region_by_id, region_id)
    if not region:
        markup = await asyncio.to_thread(_region_keyboard, ud.get("country", countries.DEFAULT_COUNTRY), lang)
        return i18n.t("unknown_option", lang), markup, REGION
    ud["region_id"] = region_id
    ud["country"] = region.get("country") or ud.get("country") or countries.DEFAULT_COUNTRY

    cities = await asyncio.to_thread(db.list_sa_major_cities_by_region, region_id)
    if len(cities) == 1:
        return _city_step(context, lang, cities[0])
    markup = await asyncio.to_thread(_city_keyboard, region_id, 0, lang, _city_back_cb(ud))
    return i18n.t("reg_region_selected", lang, region=region["name"]), markup, CITY


def _any_rare(ud: dict) -> bool:
    """هل وحدة من مهن الفني (الأولى أو الثانية) مهنة نادرة يسمح لها الأدمن بتغطية المدينة كاملة."""
    return bool(ud.get("p1_rare") or ud.get("p2_rare"))


def _city_step(context: ContextTypes.DEFAULT_TYPE, lang: str, city: dict):
    """بعد تحديد المدينة: لو لها أحياء → اختيار الأحياء (1-5) زي السعودية؛ لو بدون
    أحياء (أغلب مدن مصر/الخليج الصغيرة) → الفني يغطي المدينة كاملة تلقائيًا ونروح
    مباشرة لرقم التواصل."""
    ud = context.user_data
    ud["city_id"] = city["id"]
    ud["city"] = city["name"]
    ud["city_has_districts"] = bool(city.get("has_districts"))
    if city.get("country"):
        ud["country"] = city["country"]
    ud["district_page"] = 0
    ud["selected_district_ids"] = []

    if ud["city_has_districts"]:
        ud["covers_whole_city"] = False
        text = i18n.t("reg_district_step", lang, city=city["name"], max=MAX_DISTRICTS)
        if _any_rare(ud):
            text += "\n\n" + i18n.t("reg_rare_whole_city_hint", lang)
        return (
            text,
            _district_keyboard(city["id"], page=0, selected_ids=set(), lang=lang, allow_whole=_any_rare(ud)),
            NEIGHBORHOOD,
        )

    ud["covers_whole_city"] = True
    ud["district_ids"] = []
    ud["neighborhood"] = None
    text = i18n.t("reg_city_whole_selected", lang, city=city["name"]) + "\n\n" + _contact_prompt(context)
    return text, None, WHATSAPP


async def choose_country(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lang = _lang(context)
    query = update.callback_query
    await query.answer()
    code = query.data.split(":", 1)[1]
    enabled = await asyncio.to_thread(countries.enabled_codes, "tg")
    if code not in enabled:
        await query.edit_message_text(i18n.t("reg_ask_country_work", lang), reply_markup=_country_keyboard(enabled, lang))
        return COUNTRY
    await asyncio.to_thread(db.set_user_country, update.effective_user.id, code)
    text, markup, state = await _location_step(context, lang, country=code)
    await query.edit_message_text(text, reply_markup=markup)
    return state


async def change_country(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lang = _lang(context)
    query = update.callback_query
    await query.answer()
    text, markup, state = await _location_step(context, lang)
    await query.edit_message_text(text, reply_markup=markup)
    return state


async def choose_region(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lang = _lang(context)
    query = update.callback_query
    await query.answer()
    region_id = int(query.data.split(":", 1)[1])
    text, markup, state = await _location_step(context, lang, region_id=region_id)
    await query.edit_message_text(text, reply_markup=markup)
    return state


async def back_to_regions(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lang = _lang(context)
    query = update.callback_query
    await query.answer()
    country = context.user_data.get("country")
    text, markup, state = await _location_step(context, lang, country=country)
    await query.edit_message_text(text, reply_markup=markup)
    return state


async def city_text_search(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """اكتمال تلقائي: يكتب الفني جزء من اسم مدينته بدل تصفح الصفحات."""
    lang = _lang(context)
    region_id = context.user_data.get("region_id")
    if not region_id:
        text, markup, state = await _location_step(context, lang, country=context.user_data.get("country"))
        await update.message.reply_text(text, reply_markup=markup)
        return state

    back_cb = _city_back_cb(context.user_data)
    query_text = update.message.text.strip()
    matches = await asyncio.to_thread(db.search_sa_major_cities, region_id, query_text)
    if not matches:
        await update.message.reply_text(
            i18n.t("reg_city_not_found", lang),
            reply_markup=_city_keyboard(region_id, page=0, lang=lang, back_cb=back_cb),
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
    buttons.extend(_back_row(back_cb, lang))

    await update.message.reply_text(i18n.t("matched_results", lang), reply_markup=InlineKeyboardMarkup(buttons))
    return CITY


async def city_page_nav(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lang = _lang(context)
    query = update.callback_query
    await query.answer()
    page = int(query.data.split(":", 1)[1])
    region_id = context.user_data["region_id"]
    await query.edit_message_reply_markup(
        reply_markup=_city_keyboard(region_id, page, lang, _city_back_cb(context.user_data))
    )
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

    text, markup, state = _city_step(context, lang, city)
    await query.edit_message_text(text, reply_markup=markup)
    return state


async def district_page_nav(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lang = _lang(context)
    query = update.callback_query
    await query.answer()
    page = int(query.data.split(":", 1)[1])
    city_id = context.user_data["city_id"]
    context.user_data["district_page"] = page
    selected = set(context.user_data.get("selected_district_ids", []))
    await query.edit_message_reply_markup(reply_markup=_district_keyboard(city_id, page, selected, lang, allow_whole=_any_rare(context.user_data)))
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
                city_id, page=context.user_data.get("district_page", 0), selected_ids=selected, lang=lang,
                allow_whole=_any_rare(context.user_data),
            ),
        )
        return NEIGHBORHOOD

    buttons, row = [], []
    if _any_rare(context.user_data):
        buttons.append([InlineKeyboardButton(i18n.t("reg_whole_city_btn", lang), callback_data=WHOLE_CITY_CB)])
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
    if len(countries.enabled_codes("tg")) > 1:
        buttons.append([InlineKeyboardButton(i18n.t("change_country_btn", lang), callback_data=CHANGE_COUNTRY_CB)])

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
        reply_markup=_district_keyboard(city_id, page, set(selected), lang, allow_whole=_any_rare(context.user_data))
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
    context.user_data["covers_whole_city"] = False
    return await _after_location(query, context)


async def choose_whole_city(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """مهنة نادرة: الفني يغطي المدينة كاملة بدل اختيار أحياء محددة."""
    query = update.callback_query
    if not _any_rare(context.user_data):
        await query.answer()
        return NEIGHBORHOOD
    await query.answer()
    ud = context.user_data
    ud["covers_whole_city"] = True
    ud["district_ids"] = []
    ud["neighborhood"] = None
    ud["selected_district_ids"] = []
    return await _after_location(query, context)


async def _after_location(query, context: ContextTypes.DEFAULT_TYPE):
    """بعد الأحياء: عادةً نكمل لرقم التواصل؛ لكن لو جاي من «تعديل المهنة» (البيانات
    كاملة أصلًا) نرجع مباشرة لشاشة المراجعة."""
    lang = _lang(context)
    if context.user_data.pop("return_to_summary", False):
        await query.edit_message_text(_summary_text(context.user_data, lang), reply_markup=_confirm_keyboard(lang))
        return CONFIRM
    return await _ask_whatsapp(query.message, context)


def _contact_prompt(context: ContextTypes.DEFAULT_TYPE, invalid: bool = False) -> str:
    lang = _lang(context)
    code = context.user_data.get("country") or countries.DEFAULT_COUNTRY
    c = countries.get(code)
    key = "reg_invalid_number_country" if invalid else "reg_ask_contact_number_country"
    return i18n.t(key, lang, country=countries.name(code, lang), example=c["example"])


async def _ask_whatsapp(message, context: ContextTypes.DEFAULT_TYPE):
    await message.reply_text(_contact_prompt(context))
    return WHATSAPP


# ─────────────────────────── الخطوة 3: أرقام التواصل ───────────────────────────

async def got_whatsapp(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lang = _lang(context)
    raw = update.message.text.strip().replace(" ", "").replace("-", "")
    normalized = None
    if WHATSAPP_RE.match(raw):
        normalized = countries.normalize_phone(
            raw, context.user_data.get("country") or countries.DEFAULT_COUNTRY
        )
    if not normalized:
        await update.message.reply_text(_contact_prompt(context, invalid=True))
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
    await update.message.reply_text(i18n.t("reg_contact_saved", lang), reply_markup=ReplyKeyboardRemove())
    await update.message.reply_text(_summary_text(context.user_data, lang), reply_markup=_confirm_keyboard(lang))
    return CONFIRM


# ─────────────────────────── الخطوة 3 (بديل): المهنة (كل المهن مع أقسامها) ───────────────────────────

async def profession_list_noop(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """زر عنوان القسم غير قابل للاستخدام — فقط يرد على الضغطة بصمت لو أحد
    ضغطه بالخطأ (تلغرام يظهر ساعة تحميل على الزر لو ما رددنا على الاستعلام)."""
    await update.callback_query.answer()
    return PROFESSION


async def missing_profession(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """زر «مهنتي غير موجودة»: نطلب اسم المهنة نصًا."""
    lang = _lang(context)
    query = update.callback_query
    await query.answer()
    await query.edit_message_text(i18n.t("reg_missing_ask", lang))
    return PROF_MISSING


async def got_missing_profession(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """كتب اسم مهنته: نحفظ الطلب (صفحة «مهن مقترحة») وننبّه المالك ونشكره — ونبلغه هنا عند إضافتها."""
    lang = _lang(context)
    q = " ".join((update.message.text or "").split())[:60]
    if len(q) < 2 or q.isdigit():
        await update.message.reply_text(i18n.t("reg_missing_ask", lang))
        return PROF_MISSING
    user = update.effective_user
    name = context.user_data.get("full_name") or ""
    await asyncio.to_thread(db.add_profession_request, "", name, q, lang, "tg", user.id)
    try:
        import ratings
        uname = f" @{user.username}" if user.username else ""
        ratings._send_admin(f"🙋 مهنة مقترحة من فني (تلغرام): «{q}»\n👤 {name or '—'}{uname}\n"
                            "راجعها من لوحة التحكم ← «مهن مقترحة».")
    except Exception:
        pass
    await update.message.reply_text(i18n.t("reg_missing_thanks", lang, q=q))
    for k in ("full_name", "picking"):
        context.user_data.pop(k, None)
    return ConversationHandler.END


async def choose_profession(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """اختيار المهنة الأولى أو الثانية (حسب ud["picking"])."""
    lang = _lang(context)
    query = update.callback_query
    await query.answer()
    ud = context.user_data
    picking = ud.get("picking", 1)
    profession_id = query.data.split(":", 1)[1]
    domain, profession = await asyncio.to_thread(professions.get_profession, profession_id, lang)
    if not profession or (picking == 2 and profession_id == ud.get("profession_id")):
        keyboard = await asyncio.to_thread(
            _profession_list_grouped_keyboard, lang,
            ud.get("profession_id") if picking == 2 else None, picking == 2,
        )
        await query.edit_message_text(i18n.t("unknown_option", lang), reply_markup=keyboard)
        return PROFESSION

    if picking == 1:
        ud["domain_id"] = domain["id"] if domain else None
        ud["domain_name"] = domain["name"] if domain else ""
        ud["profession_id"] = profession_id
        ud["profession_name"] = profession["name"]
        ud["services"] = []
        ud["p1_rare"] = bool(profession.get("allow_city_wide"))
    else:
        ud["profession2_id"] = profession_id
        ud["profession2_name"] = profession["name"]
        ud["services2"] = []
        ud["p2_rare"] = bool(profession.get("allow_city_wide"))
    ud["available_services"] = profession["services"]

    if profession["services"]:
        await query.edit_message_text(
            i18n.t("reg_services_prompt", lang, profession=profession["name"]),
            reply_markup=_services_keyboard(profession["services"], set(), lang),
        )
        return SERVICES
    return await _after_services(query, context)


async def _after_services(query, context: ContextTypes.DEFAULT_TYPE):
    """بعد المهنة الأولى: نسأل عن مهنة ثانية (اختياري). بعد الثانية: نكمل للموقع."""
    lang = _lang(context)
    if context.user_data.get("picking", 1) == 1:
        keyboard = InlineKeyboardMarkup(
            [
                [InlineKeyboardButton(i18n.t("reg_add_second_btn", lang), callback_data=ADD_SECOND_CB)],
                [InlineKeyboardButton(i18n.t("reg_no_second_btn", lang), callback_data=NO_SECOND_CB)],
            ]
        )
        await query.edit_message_text(
            i18n.t("reg_second_prof_prompt", lang, profession=context.user_data["profession_name"]),
            reply_markup=keyboard,
        )
        return SECOND_PROF
    return await _after_professions(query, context)


async def add_second_profession(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lang = _lang(context)
    query = update.callback_query
    await query.answer()
    context.user_data["picking"] = 2
    keyboard = await asyncio.to_thread(
        _profession_list_grouped_keyboard, lang, context.user_data.get("profession_id"), True
    )
    await query.edit_message_text(i18n.t("reg_pick_second_prof", lang), reply_markup=keyboard)
    return PROFESSION


async def no_second_profession(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    ud = context.user_data
    for k in ("profession2_id", "profession2_name", "services2", "p2_rare"):
        ud.pop(k, None)
    return await _after_professions(query, context)


async def _after_professions(query, context: ContextTypes.DEFAULT_TYPE):
    """خلصت المهن: تسجيل جديد → خطوة الموقع. تعديل المهنة من شاشة المراجعة → نرجع
    للمراجعة، إلا لو كان مختار «المدينة كاملة» ومهنه الجديدة مو نادرة (والمدينة لها
    أحياء) — وقتها لازم يختار أحياءه من جديد."""
    lang = _lang(context)
    ud = context.user_data
    if ud.pop("editing_profession", False) and ud.get("city_id"):
        if ud.get("covers_whole_city") and ud.get("city_has_districts") and not _any_rare(ud):
            ud["return_to_summary"] = True
            ud["selected_district_ids"] = []
            ud["district_page"] = 0
            await query.edit_message_text(
                i18n.t("reg_reselect_districts_note", lang) + "\n\n"
                + i18n.t("reg_district_step", lang, city=ud["city"], max=MAX_DISTRICTS),
                reply_markup=_district_keyboard(ud["city_id"], 0, set(), lang),
            )
            return NEIGHBORHOOD
        await query.edit_message_text(_summary_text(ud, lang), reply_markup=_confirm_keyboard(lang))
        return CONFIRM

    text, markup, state = await _location_step(context, lang)
    await query.edit_message_text(text, reply_markup=markup)
    return state


# ─────────────────────────── الخدمات الفرعية ───────────────────────────

def _services_key(context) -> str:
    return "services2" if context.user_data.get("picking", 1) == 2 else "services"


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
    key = _services_key(context)
    selected = set(context.user_data.get(key, []))
    if service in selected:
        selected.discard(service)
    else:
        selected.add(service)
    context.user_data[key] = list(selected)
    await query.answer()

    await query.edit_message_reply_markup(
        reply_markup=_services_keyboard(available, selected, lang)
    )
    return SERVICES


async def services_done(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    return await _after_services(query, context)


# ─────────────────────────── الخطوة 6-7: المراجعة والتأكيد ───────────────────────────

async def confirm_edit(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """تعديل المهنة فقط: يرجع لقائمة كل المهن (مع أقسامها)، محتفظًا بباقي البيانات
    (الاسم، الموقع، أرقام التواصل) — يسمح للفني يستكشف مهنة ثانية قبل ما يقرر،
    بدون ما يعيد كتابة كل بياناته من الصفر."""
    lang = _lang(context)
    query = update.callback_query
    await query.answer()
    ud = context.user_data
    ud["editing_profession"] = True
    ud["picking"] = 1
    for k in ("profession2_id", "profession2_name", "services2", "p2_rare"):
        ud.pop(k, None)
    keyboard = await asyncio.to_thread(_profession_list_grouped_keyboard, lang)
    await query.edit_message_text(i18n.t("reg_profession_prompt", lang), reply_markup=keyboard)
    return PROFESSION


async def confirm_edit_all(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # تعديل الكل: نعيد البدء من الخطوة 1 بالكامل
    lang = _lang(context)
    query = update.callback_query
    await query.answer()
    kept = {k: context.user_data[k] for k in ("source", "referrer_id") if k in context.user_data}
    context.user_data.clear()
    context.user_data["lang"] = lang
    context.user_data.update(kept)
    await query.edit_message_text(i18n.t("reg_restart", lang))
    return NAME


async def back_to_profession_from_services(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """زر رجوع من خطوة الخدمات لقائمة كل المهن (مع أقسامها) — يتيح استكشاف مهنة
    ثانية (بخدماتها) قبل الاستقرار على واحدة، بدل ما يضطر يلغي التسجيل بالكامل."""
    lang = _lang(context)
    query = update.callback_query
    await query.answer()
    ud = context.user_data
    picking2 = ud.get("picking", 1) == 2
    keyboard = await asyncio.to_thread(
        _profession_list_grouped_keyboard, lang, ud.get("profession_id") if picking2 else None, picking2
    )
    await query.edit_message_text(
        i18n.t("reg_pick_second_prof" if picking2 else "reg_profession_prompt", lang),
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
            "services": _all_services(ud),
            "profession2_id": ud.get("profession2_id"),
            "profession2_name": ud.get("profession2_name"),
            "covers_whole_city": ud.get("covers_whole_city", False),
            "source": ud.get("source", "unknown"),
            "country": ud.get("country") or countries.DEFAULT_COUNTRY,
            "city_id": ud.get("city_id"),
            "referred_by": ud.get("referrer_id"),
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
            COUNTRY: [CallbackQueryHandler(choose_country, pattern=f"^{COUNTRY_CB_PREFIX}")],
            REGION: [
                CallbackQueryHandler(choose_region, pattern="^reg_region:"),
                CallbackQueryHandler(change_country, pattern=f"^{CHANGE_COUNTRY_CB}$"),
            ],
            CITY: [
                CallbackQueryHandler(choose_city, pattern="^reg_city:"),
                CallbackQueryHandler(change_country, pattern=f"^{CHANGE_COUNTRY_CB}$"),
                CallbackQueryHandler(city_page_nav, pattern="^reg_city_page:"),
                CallbackQueryHandler(back_to_regions, pattern=f"^{BACK_TO_REGIONS_CB}$"),
                MessageHandler(filters.TEXT & ~filters.COMMAND, city_text_search),
            ],
            NEIGHBORHOOD: [
                CallbackQueryHandler(districts_done, pattern=f"^{DISTRICTS_DONE_CB}$"),
                CallbackQueryHandler(choose_whole_city, pattern=f"^{WHOLE_CITY_CB}$"),
                CallbackQueryHandler(change_country, pattern=f"^{CHANGE_COUNTRY_CB}$"),
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
                CallbackQueryHandler(missing_profession, pattern=f"^{PROF_MISSING_CB}$"),
                CallbackQueryHandler(choose_profession, pattern="^reg_prof:"),
                CallbackQueryHandler(profession_list_noop, pattern=f"^{PROFESSION_NOOP_CB}$"),
                CallbackQueryHandler(no_second_profession, pattern=f"^{NO_SECOND_CB}$"),
            ],
            PROF_MISSING: [MessageHandler(filters.TEXT & ~filters.COMMAND, got_missing_profession)],
            SECOND_PROF: [
                CallbackQueryHandler(add_second_profession, pattern=f"^{ADD_SECOND_CB}$"),
                CallbackQueryHandler(no_second_profession, pattern=f"^{NO_SECOND_CB}$"),
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
