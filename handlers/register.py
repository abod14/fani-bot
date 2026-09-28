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

import db
import i18n
import professions_repo as professions

(
    NAME,
    REGION,
    CITY,
    NEIGHBORHOOD,
    WHATSAPP,
    WHATSAPP_CONFIRM,
    TELEGRAM_CONTACT,
    DOMAIN,
    PROFESSION,
    SERVICES,
    CONFIRM,
) = range(11)

BACK_TO_REGIONS_CB = "reg_back_regions"
DISTRICT_TOGGLE_CB_PREFIX = "reg_dist_toggle:"
DISTRICTS_DONE_CB = "reg_dist_done"
HAS_WHATSAPP_YES_CB = "reg_has_wa_yes"
HAS_WHATSAPP_NO_CB = "reg_has_wa_no"
SERVICES_DONE_CB = "reg_services_done"
CONFIRM_YES_CB = "reg_confirm_yes"
CONFIRM_EDIT_CB = "reg_confirm_edit"

MIN_DISTRICTS = 1
MAX_DISTRICTS = 5  # قرار نهائي: الفني يختار حي واحد على الأقل وخمسة أحياء كحد أقصى

WHATSAPP_RE = re.compile(r"^\+?[0-9]{8,15}$")

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


def _services_keyboard(services: list[str], selected: set[str], lang: str) -> InlineKeyboardMarkup:
    buttons = []
    for s in services:
        mark = "✅ " if s in selected else "▫️ "
        buttons.append([InlineKeyboardButton(mark + s, callback_data=f"reg_svc:{s}")])
    buttons.append(
        [InlineKeyboardButton(i18n.t("reg_services_done_btn", lang), callback_data=SERVICES_DONE_CB)]
    )
    return InlineKeyboardMarkup(buttons)


def _summary_text(ud: dict, lang: str) -> str:
    services = ud.get("services") or []
    services_text = "، ".join(services) if services else i18n.t("no_services", lang)
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
            [
                InlineKeyboardButton(i18n.t("reg_confirm_btn", lang), callback_data=CONFIRM_YES_CB),
                InlineKeyboardButton(i18n.t("reg_edit_btn", lang), callback_data=CONFIRM_EDIT_CB),
            ]
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
    await target.reply_text(
        i18n.t("reg_start", lang),
        reply_markup=ReplyKeyboardRemove(),
    )
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
    region = db.get_sa_region_by_id(region_id)
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
    matches = db.search_sa_major_cities(region_id, query_text)
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
    city = db.get_sa_city_by_id(city_id)
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
    matches = db.search_sa_districts(city_id, query_text)
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

    districts = db.list_sa_districts_by_city(context.user_data["city_id"])
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
    number = update.message.text.strip().replace(" ", "")
    if not WHATSAPP_RE.match(number):
        await update.message.reply_text(i18n.t("reg_invalid_number", lang))
        return WHATSAPP
    context.user_data["whatsapp_number"] = number

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
        i18n.t("reg_domain_prompt", lang),
        reply_markup=ReplyKeyboardRemove(),
    )
    await update.message.reply_text(i18n.t("domains_available", lang), reply_markup=_domain_keyboard(lang))
    return DOMAIN


# ─────────────────────────── الخطوة 3 (بديل): المجال والمهنة ───────────────────────────

async def choose_domain(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lang = _lang(context)
    query = update.callback_query
    await query.answer()
    domain_id = query.data.split(":", 1)[1]
    domain = professions.get_domain(domain_id, lang)
    if not domain:
        await query.edit_message_text(i18n.t("unknown_option", lang), reply_markup=_domain_keyboard(lang))
        return DOMAIN

    context.user_data["domain_id"] = domain_id
    context.user_data["domain_name"] = domain["name"]
    await query.edit_message_text(
        i18n.t("reg_domain_selected", lang, domain=domain["name"]),
        reply_markup=_profession_keyboard(domain_id, lang),
    )
    return PROFESSION


async def back_to_domain(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lang = _lang(context)
    query = update.callback_query
    await query.answer()
    await query.edit_message_text(i18n.t("domains_available", lang), reply_markup=_domain_keyboard(lang))
    return DOMAIN


async def choose_profession(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lang = _lang(context)
    query = update.callback_query
    await query.answer()
    profession_id = query.data.split(":", 1)[1]
    domain, profession = professions.get_profession(profession_id, lang)
    if not profession:
        await query.edit_message_text(i18n.t("unknown_option", lang))
        return PROFESSION

    context.user_data["profession_id"] = profession_id
    context.user_data["profession_name"] = profession["name"]
    context.user_data["available_services"] = profession["services"]
    context.user_data["services"] = []

    if profession["services"]:
        await query.edit_message_text(
            i18n.t("reg_services_prompt", lang, profession=profession["name"]),
            reply_markup=_services_keyboard(profession["services"], set(), lang),
        )
        return SERVICES

    # لا توجد خدمات فرعية — نروح مباشرة لشاشة المراجعة
    await query.edit_message_text(_summary_text(context.user_data, lang), reply_markup=_confirm_keyboard(lang))
    return CONFIRM


# ─────────────────────────── الخطوة 5: الخدمات الفرعية ───────────────────────────

async def toggle_service(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lang = _lang(context)
    query = update.callback_query
    service = query.data.split(":", 1)[1]
    selected = set(context.user_data.get("services", []))
    if service in selected:
        selected.discard(service)
    else:
        selected.add(service)
    context.user_data["services"] = list(selected)
    await query.answer()

    available = context.user_data.get("available_services", [])
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
    # أبسط تنفيذ (زي ما ورد بالتصميم الأصلي): نعيد البدء من الخطوة 1
    lang = _lang(context)
    query = update.callback_query
    await query.answer()
    context.user_data.clear()
    context.user_data["lang"] = lang
    await query.edit_message_text(i18n.t("reg_restart", lang))
    return NAME


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
        },
    )

    await query.edit_message_text(
        i18n.t(
            "reg_success", lang,
            name=ud["full_name"], city=ud["city"], profession=ud["profession_name"],
        )
    )

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
            DOMAIN: [CallbackQueryHandler(choose_domain, pattern="^reg_dom:")],
            PROFESSION: [
                CallbackQueryHandler(choose_profession, pattern="^reg_prof:"),
                CallbackQueryHandler(back_to_domain, pattern="^reg_back_domain$"),
            ],
            SERVICES: [
                CallbackQueryHandler(services_done, pattern=f"^{SERVICES_DONE_CB}$"),
                CallbackQueryHandler(toggle_service, pattern="^reg_svc:"),
            ],
            CONFIRM: [
                CallbackQueryHandler(confirm_yes, pattern=f"^{CONFIRM_YES_CB}$"),
                CallbackQueryHandler(confirm_edit, pattern=f"^{CONFIRM_EDIT_CB}$"),
            ],
            ConversationHandler.TIMEOUT: [MessageHandler(filters.ALL, registration_timeout)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
        name="register_conversation",
        persistent=False,
        conversation_timeout=900,
    )
