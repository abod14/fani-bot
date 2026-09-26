# تدفق /register الكامل — 7 خطوات، باستخدام ConversationHandler.
# نجمع البيانات بـ context.user_data خطوة بخطوة، ونحفظها بقاعدة البيانات فقط
# بعد تأكيد الفني النهائي (خطوة 6/7).

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
import professions_repo as professions

(
    NAME,
    REGION,
    CITY,
    NEIGHBORHOOD,
    WHATSAPP,
    TELEGRAM_CONTACT,
    DOMAIN,
    PROFESSION,
    SERVICES,
    CONFIRM,
) = range(10)

BACK_TO_REGIONS_CB = "reg_back_regions"
DISTRICT_TOGGLE_CB_PREFIX = "reg_dist_toggle:"
DISTRICTS_DONE_CB = "reg_dist_done"
SERVICES_DONE_CB = "reg_services_done"
CONFIRM_YES_CB = "reg_confirm_yes"
CONFIRM_EDIT_CB = "reg_confirm_edit"

MIN_DISTRICTS = 1
MAX_DISTRICTS = 5  # قرار نهائي: الفني يختار حي واحد على الأقل وخمسة أحياء كحد أقصى

WHATSAPP_RE = re.compile(r"^\+?[0-9]{8,15}$")

# عدد المدن/الأحياء بكل صفحة أزرار (4 صفوف × عمودين)
GEO_PAGE_SIZE = 8


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
        nav_row.append(InlineKeyboardButton("◀️ السابق", callback_data=f"{page_cb_prefix}{page - 1}"))
    if start + GEO_PAGE_SIZE < total:
        nav_row.append(InlineKeyboardButton("التالي ▶️", callback_data=f"{page_cb_prefix}{page + 1}"))
    if nav_row:
        buttons.append(nav_row)

    for extra in (extra_rows or []):
        buttons.append(extra)

    return InlineKeyboardMarkup(buttons)


def _city_keyboard(region_id: int, page: int) -> InlineKeyboardMarkup:
    cities = db.list_sa_major_cities_by_region(region_id)
    return _paginated_keyboard(
        cities, page, "reg_city:", "reg_city_page:",
        extra_rows=[[InlineKeyboardButton("⬅️ رجوع للمناطق", callback_data=BACK_TO_REGIONS_CB)]],
    )


def _district_keyboard(city_id: int, page: int, selected_ids: set[int]) -> InlineKeyboardMarkup:
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
        nav_row.append(InlineKeyboardButton("◀️ السابق", callback_data=f"reg_dist_page:{page - 1}"))
    if start + GEO_PAGE_SIZE < total:
        nav_row.append(InlineKeyboardButton("التالي ▶️", callback_data=f"reg_dist_page:{page + 1}"))
    if nav_row:
        buttons.append(nav_row)

    if selected_ids:
        buttons.append(
            [InlineKeyboardButton(
                f"تأكيد الاختيار ✅ ({len(selected_ids)}/{MAX_DISTRICTS})", callback_data=DISTRICTS_DONE_CB
            )]
        )

    return InlineKeyboardMarkup(buttons)


# ─────────────────────────── أدوات مساعدة ───────────────────────────

def _domain_keyboard() -> InlineKeyboardMarkup:
    buttons = []
    row = []
    for d in professions.get_domains():
        row.append(InlineKeyboardButton(d["name"], callback_data=f"reg_dom:{d['id']}"))
        if len(row) == 2:
            buttons.append(row)
            row = []
    if row:
        buttons.append(row)
    return InlineKeyboardMarkup(buttons)


def _profession_keyboard(domain_id: str) -> InlineKeyboardMarkup:
    buttons = []
    row = []
    for p in professions.get_professions_by_domain(domain_id):
        row.append(InlineKeyboardButton(p["name"], callback_data=f"reg_prof:{p['id']}"))
        if len(row) == 2:
            buttons.append(row)
            row = []
    if row:
        buttons.append(row)
    buttons.append(
        [InlineKeyboardButton("⬅️ رجوع لاختيار المجال", callback_data="reg_back_domain")]
    )
    return InlineKeyboardMarkup(buttons)


def _services_keyboard(services: list[str], selected: set[str]) -> InlineKeyboardMarkup:
    buttons = []
    for s in services:
        mark = "✅ " if s in selected else "▫️ "
        buttons.append([InlineKeyboardButton(mark + s, callback_data=f"reg_svc:{s}")])
    buttons.append(
        [InlineKeyboardButton("تأكيد الاختيار ✅", callback_data=SERVICES_DONE_CB)]
    )
    return InlineKeyboardMarkup(buttons)


def _summary_text(ud: dict) -> str:
    services = ud.get("services") or []
    services_text = "، ".join(services) if services else "لا يوجد"
    neighborhoods_text = ud.get("neighborhood") or "لم يُحدد"
    return (
        "مراجعة بيانات التسجيل:\n\n"
        f"الاسم: {ud['full_name']}\n"
        f"المدينة: {ud['city']}\n"
        f"الأحياء: {neighborhoods_text}\n"
        f"رقم الواتساب: {ud['whatsapp_number']}\n"
        f"حساب التلغرام: {ud.get('telegram_contact_number') or 'غير متاح'}\n"
        f"المهنة: {ud['profession_name']}\n"
        f"الخدمات: {services_text}"
    )


def _confirm_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("✅ تأكيد التسجيل", callback_data=CONFIRM_YES_CB),
                InlineKeyboardButton("✏️ تعديل البيانات", callback_data=CONFIRM_EDIT_CB),
            ]
        ]
    )


# ─────────────────────────── الخطوة 1: الاسم ───────────────────────────

async def register_entry(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    target = update.message or update.callback_query.message
    if update.callback_query:
        await update.callback_query.answer()
    await target.reply_text(
        "لنبدأ تسجيلك كفني 📝\n\nأرسل اسمك الكامل:",
        reply_markup=ReplyKeyboardRemove(),
    )
    return NAME


async def got_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    name = update.message.text.strip()
    if len(name) < 3:
        await update.message.reply_text("الاسم قصير جدًا، أرسل اسمك الكامل من فضلك:")
        return NAME
    context.user_data["full_name"] = name
    await update.message.reply_text("اختر منطقتك:", reply_markup=_region_keyboard())
    return REGION


# ─────────────────────────── الخطوة 2: المنطقة → المدينة → الحي ───────────────────────────

async def choose_region(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    region_id = int(query.data.split(":", 1)[1])
    region = db.get_sa_region_by_id(region_id)
    if not region:
        await query.edit_message_text("خيار غير معروف، اختر من القائمة:", reply_markup=_region_keyboard())
        return REGION

    context.user_data["region_id"] = region_id
    await query.edit_message_text(
        f"المنطقة: {region['name']}\n\nاختر مدينتك:",
        reply_markup=_city_keyboard(region_id, page=0),
    )
    return CITY


async def back_to_regions(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text("اختر منطقتك:", reply_markup=_region_keyboard())
    return REGION


async def city_page_nav(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    page = int(query.data.split(":", 1)[1])
    region_id = context.user_data["region_id"]
    await query.edit_message_reply_markup(reply_markup=_city_keyboard(region_id, page))
    return CITY


async def choose_city(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    city_id = int(query.data.split(":", 1)[1])
    city = db.get_sa_city_by_id(city_id)
    if not city:
        await query.edit_message_text("خيار غير معروف، حاول مرة أخرى.")
        return CITY

    context.user_data["city_id"] = city_id
    context.user_data["city"] = city["name"]
    context.user_data["district_page"] = 0
    context.user_data["selected_district_ids"] = []
    await query.edit_message_text(
        f"المدينة: {city['name']}\n\n"
        f"اختر أحياءك (حي واحد على الأقل، وحتى {MAX_DISTRICTS} أحياء كحد أقصى)، "
        "ثم اضغط «تأكيد الاختيار»:",
        reply_markup=_district_keyboard(city_id, page=0, selected_ids=set()),
    )
    return NEIGHBORHOOD


async def district_page_nav(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    page = int(query.data.split(":", 1)[1])
    city_id = context.user_data["city_id"]
    context.user_data["district_page"] = page
    selected = set(context.user_data.get("selected_district_ids", []))
    await query.edit_message_reply_markup(reply_markup=_district_keyboard(city_id, page, selected))
    return NEIGHBORHOOD


async def toggle_district(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    district_id = int(query.data.split(":", 1)[1])
    selected = list(context.user_data.get("selected_district_ids", []))

    if district_id in selected:
        selected.remove(district_id)
    elif len(selected) >= MAX_DISTRICTS:
        await query.answer(f"لا يمكن اختيار أكثر من {MAX_DISTRICTS} أحياء.", show_alert=True)
        return NEIGHBORHOOD
    else:
        selected.append(district_id)

    context.user_data["selected_district_ids"] = selected
    await query.answer()

    city_id = context.user_data["city_id"]
    page = context.user_data.get("district_page", 0)
    await query.edit_message_reply_markup(
        reply_markup=_district_keyboard(city_id, page, set(selected))
    )
    return NEIGHBORHOOD


async def districts_done(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    selected_ids = context.user_data.get("selected_district_ids", [])
    if len(selected_ids) < MIN_DISTRICTS:
        await query.answer("اختر حيًا واحدًا على الأقل قبل المتابعة.", show_alert=True)
        return NEIGHBORHOOD
    await query.answer()

    districts = db.list_sa_districts_by_city(context.user_data["city_id"])
    by_id = {d["id"]: d for d in districts}
    chosen = [by_id[did] for did in selected_ids if did in by_id]

    context.user_data["district_ids"] = [d["id"] for d in chosen]
    context.user_data["neighborhood"] = "، ".join(d["name"] for d in chosen)
    return await _ask_whatsapp(query.message, context)


async def _ask_whatsapp(message, context: ContextTypes.DEFAULT_TYPE):
    await message.reply_text(
        "أرسل رقم الواتساب الخاص بك (مع رمز الدولة)، مثال:\n+966501234567"
    )
    return WHATSAPP


# ─────────────────────────── الخطوة 3: أرقام التواصل ───────────────────────────

async def got_whatsapp(update: Update, context: ContextTypes.DEFAULT_TYPE):
    number = update.message.text.strip().replace(" ", "")
    if not WHATSAPP_RE.match(number):
        await update.message.reply_text(
            "رقم غير صحيح. أرسل الرقم مع رمز الدولة، مثال:\n+966501234567"
        )
        return WHATSAPP
    context.user_data["whatsapp_number"] = number

    contact_button = KeyboardButton("📱 مشاركة رقم التلغرام", request_contact=True)
    keyboard = ReplyKeyboardMarkup(
        [[contact_button]], resize_keyboard=True, one_time_keyboard=True
    )
    await update.message.reply_text(
        "الآن شارك رقم حسابك بتلغرام بالضغط على الزر بالأسفل:",
        reply_markup=keyboard,
    )
    return TELEGRAM_CONTACT


async def got_telegram_contact(update: Update, context: ContextTypes.DEFAULT_TYPE):
    contact = update.message.contact
    if contact is None or contact.user_id != update.effective_user.id:
        await update.message.reply_text(
            "الرجاء الضغط على زر مشاركة رقم التلغرام بالأسفل (وليس كتابة الرقم يدويًا):"
        )
        return TELEGRAM_CONTACT

    context.user_data["telegram_contact_number"] = contact.phone_number
    await update.message.reply_text(
        "تمام ✅ اختر مجال عملك:",
        reply_markup=ReplyKeyboardRemove(),
    )
    await update.message.reply_text("المجالات المتاحة:", reply_markup=_domain_keyboard())
    return DOMAIN


# ─────────────────────────── الخطوة 3 (بديل): المجال والمهنة ───────────────────────────

async def choose_domain(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    domain_id = query.data.split(":", 1)[1]
    domain = professions.get_domain(domain_id)
    if not domain:
        await query.edit_message_text("خيار غير معروف، اختر من القائمة:", reply_markup=_domain_keyboard())
        return DOMAIN

    context.user_data["domain_id"] = domain_id
    context.user_data["domain_name"] = domain["name"]
    await query.edit_message_text(
        f"مجال: {domain['name']}\n\nاختر مهنتك:",
        reply_markup=_profession_keyboard(domain_id),
    )
    return PROFESSION


async def back_to_domain(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text("المجالات المتاحة:", reply_markup=_domain_keyboard())
    return DOMAIN


async def choose_profession(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    profession_id = query.data.split(":", 1)[1]
    domain, profession = professions.get_profession(profession_id)
    if not profession:
        await query.edit_message_text("خيار غير معروف، حاول مرة أخرى.")
        return PROFESSION

    context.user_data["profession_id"] = profession_id
    context.user_data["profession_name"] = profession["name"]
    context.user_data["available_services"] = profession["services"]
    context.user_data["services"] = []

    if profession["services"]:
        await query.edit_message_text(
            f"مهنة: {profession['name']}\n\nاختر الخدمات التي تقدّمها (يمكن اختيار أكثر من خدمة):",
            reply_markup=_services_keyboard(profession["services"], set()),
        )
        return SERVICES

    # لا توجد خدمات فرعية — نروح مباشرة لشاشة المراجعة
    await query.edit_message_text(_summary_text(context.user_data), reply_markup=_confirm_keyboard())
    return CONFIRM


# ─────────────────────────── الخطوة 5: الخدمات الفرعية ───────────────────────────

async def toggle_service(update: Update, context: ContextTypes.DEFAULT_TYPE):
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
        reply_markup=_services_keyboard(available, selected)
    )
    return SERVICES


async def services_done(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text(_summary_text(context.user_data), reply_markup=_confirm_keyboard())
    return CONFIRM


# ─────────────────────────── الخطوة 6-7: المراجعة والتأكيد ───────────────────────────

async def confirm_edit(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # أبسط تنفيذ (زي ما ورد بالتصميم الأصلي): نعيد البدء من الخطوة 1
    query = update.callback_query
    await query.answer()
    context.user_data.clear()
    await query.edit_message_text("تمام، نبدأ التسجيل من جديد.")
    await query.message.reply_text("أرسل اسمك الكامل:")
    return NAME


async def confirm_yes(update: Update, context: ContextTypes.DEFAULT_TYPE):
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
            "telegram_contact_number": ud.get("telegram_contact_number"),
            "domain_name": ud["domain_name"],
            "profession_id": ud["profession_id"],
            "profession_name": ud["profession_name"],
            "services": ud.get("services", []),
        },
    )

    await query.edit_message_text(
        "✅ تم استلام طلب تسجيلك بنجاح\n\n"
        f"الاسم: {ud['full_name']}\n"
        f"المدينة: {ud['city']}\n"
        f"المهنة: {ud['profession_name']}\n\n"
        "طلبك الآن قيد المراجعة، وسيتم إعلامك فور الموافقة عليه."
    )

    # إشعار الأدمن — نستورد هنا لتفادي استيراد دائري بين register.py و admin.py
    from handlers.admin import notify_admin_new_registration

    await notify_admin_new_registration(context, row_id)

    context.user_data.clear()
    return ConversationHandler.END


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    await update.message.reply_text(
        "تم إلغاء التسجيل. أرسل /register في أي وقت للبدء من جديد.",
        reply_markup=ReplyKeyboardRemove(),
    )
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
            ],
            NEIGHBORHOOD: [
                CallbackQueryHandler(districts_done, pattern=f"^{DISTRICTS_DONE_CB}$"),
                CallbackQueryHandler(toggle_district, pattern=f"^{DISTRICT_TOGGLE_CB_PREFIX}"),
                CallbackQueryHandler(district_page_nav, pattern="^reg_dist_page:"),
            ],
            WHATSAPP: [MessageHandler(filters.TEXT & ~filters.COMMAND, got_whatsapp)],
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
        },
        fallbacks=[CommandHandler("cancel", cancel)],
        name="register_conversation",
        persistent=False,
    )
