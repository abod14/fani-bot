# تدفق /search — الترتيب: المهنة (مجال ثم مهنة) → المنطقة → المدينة (من قائمة رسمية
# بأزرار) → الحي (أزرار من أحياء حقيقية لنفس المدينة، مع تخطي اختياري)، ثم نتائج
# مُرتّبة بنظام تناوب عادل، صفحات من 5، وزر "تواصل عبر واتساب" يسجّل الضغطة ويستهلك
# من الفرص المجانية لكل فني قبل ما يحتاج اشتراك.

import asyncio

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    ConversationHandler,
)

import db
import professions_repo as professions

(
    SEARCH_DOMAIN,
    SEARCH_PROFESSION,
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
NEARBY_SUGGESTIONS_COUNT = 3

GEO_PAGE_SIZE = 8


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
        cities, page, "srch_city:", "srch_city_page:",
        extra_rows=[[InlineKeyboardButton("⬅️ رجوع للمناطق", callback_data=BACK_TO_REGIONS_CB)]],
    )


def _district_keyboard(city_id: int, page: int) -> InlineKeyboardMarkup:
    districts = db.list_sa_districts_by_city(city_id)
    return _paginated_keyboard(
        districts, page, "srch_dist:", "srch_dist_page:",
        extra_rows=[[InlineKeyboardButton("تخطي (كل أحياء المدينة)", callback_data=SKIP_NEIGHBORHOOD_CB)]],
    )


# ─────────────────────────── لوحات الأزرار ───────────────────────────

def _domain_keyboard() -> InlineKeyboardMarkup:
    buttons, row = [], []
    for d in professions.get_domains():
        row.append(InlineKeyboardButton(d["name"], callback_data=f"srch_dom:{d['id']}"))
        if len(row) == 2:
            buttons.append(row)
            row = []
    if row:
        buttons.append(row)
    return InlineKeyboardMarkup(buttons)


def _profession_keyboard(domain_id: str) -> InlineKeyboardMarkup:
    buttons, row = [], []
    for p in professions.get_professions_by_domain(domain_id):
        row.append(InlineKeyboardButton(p["name"], callback_data=f"srch_prof:{p['id']}"))
        if len(row) == 2:
            buttons.append(row)
            row = []
    if row:
        buttons.append(row)
    buttons.append([InlineKeyboardButton("⬅️ رجوع لاختيار المجال", callback_data="srch_back_domain")])
    return InlineKeyboardMarkup(buttons)


def _whatsapp_button(professional_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [[InlineKeyboardButton("📱 تواصل عبر واتساب", callback_data=f"srch_wa:{professional_id}")]]
    )


def _wa_link(number: str) -> str:
    digits = number.lstrip("+")
    return f"https://wa.me/{digits}"


def _professional_card_text(p: dict) -> str:
    location = p["city"] + (f" — {p['neighborhood']}" if p["neighborhood"] else "")
    lines = [
        f"👷 {p['full_name']}",
        f"📍 {location}",
    ]
    if p["telegram_contact_number"]:
        lines.append(f"✈️ تلغرام: {p['telegram_contact_number']}")
    return "\n".join(lines)


# ─────────────────────────── الخطوة 1: المهنة (مجال ثم مهنة) ───────────────────────────

async def search_entry(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    target = update.message or update.callback_query.message
    if update.callback_query:
        await update.callback_query.answer()
    await target.reply_text("اختر مجال الخدمة المطلوبة:", reply_markup=_domain_keyboard())
    return SEARCH_DOMAIN


async def choose_search_domain(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    domain_id = query.data.split(":", 1)[1]
    domain = professions.get_domain(domain_id)
    if not domain:
        await query.edit_message_text("خيار غير معروف، اختر من القائمة:", reply_markup=_domain_keyboard())
        return SEARCH_DOMAIN

    await query.edit_message_text(f"مجال: {domain['name']}\n\nاختر المهنة:", reply_markup=_profession_keyboard(domain_id))
    return SEARCH_PROFESSION


async def back_to_search_domain(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text("اختر مجال الخدمة المطلوبة:", reply_markup=_domain_keyboard())
    return SEARCH_DOMAIN


async def choose_search_profession(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    profession_id = query.data.split(":", 1)[1]
    domain, profession = professions.get_profession(profession_id)
    if not profession:
        await query.edit_message_text("خيار غير معروف، حاول مرة أخرى.")
        return SEARCH_PROFESSION

    context.user_data["profession_id"] = profession_id
    context.user_data["profession_name"] = profession["name"]

    await query.edit_message_text(f"مهنة: {profession['name']}\n\nاختر منطقتك:", reply_markup=_region_keyboard())
    return SEARCH_REGION


# ─────────────────────────── الخطوة 2: المنطقة → المدينة → الحي ───────────────────────────

async def choose_search_region(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    region_id = int(query.data.split(":", 1)[1])
    region = db.get_sa_region_by_id(region_id)
    if not region:
        await query.edit_message_text("خيار غير معروف، اختر من القائمة:", reply_markup=_region_keyboard())
        return SEARCH_REGION

    context.user_data["region_id"] = region_id
    await query.edit_message_text(
        f"المنطقة: {region['name']}\n\nاختر المدينة:",
        reply_markup=_city_keyboard(region_id, page=0),
    )
    return SEARCH_CITY


async def back_to_search_regions(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text("اختر منطقتك:", reply_markup=_region_keyboard())
    return SEARCH_REGION


async def search_city_page_nav(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    page = int(query.data.split(":", 1)[1])
    region_id = context.user_data["region_id"]
    await query.edit_message_reply_markup(reply_markup=_city_keyboard(region_id, page))
    return SEARCH_CITY


async def choose_search_city(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    city_id = int(query.data.split(":", 1)[1])
    city = db.get_sa_city_by_id(city_id)
    if not city:
        await query.edit_message_text("خيار غير معروف، حاول مرة أخرى.")
        return SEARCH_CITY

    context.user_data["city_id"] = city_id
    context.user_data["city"] = city["name"]
    context.user_data.setdefault("tried_city_ids", []).append(city_id)
    await query.edit_message_text(
        f"المدينة: {city['name']}\n\nاختر الحي (أو تخطى للبحث بكل المدينة):",
        reply_markup=_district_keyboard(city_id, page=0),
    )
    return SEARCH_NEIGHBORHOOD


async def search_district_page_nav(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    page = int(query.data.split(":", 1)[1])
    city_id = context.user_data["city_id"]
    await query.edit_message_reply_markup(reply_markup=_district_keyboard(city_id, page))
    return SEARCH_NEIGHBORHOOD


async def choose_search_district(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    district_id = int(query.data.split(":", 1)[1])
    districts = db.list_sa_districts_by_city(context.user_data["city_id"])
    district = next((d for d in districts if d["id"] == district_id), None)
    if not district:
        await query.edit_message_text("خيار غير معروف، حاول مرة أخرى.")
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
        ud.get("district_id"),
    )
    ud["result_ids"] = result_ids
    ud["shown_count"] = 0

    await asyncio.to_thread(
        db.log_search, customer_telegram_id, ud["profession_id"], ud["profession_name"],
        ud["city"], ud.get("neighborhood"), len(result_ids),
    )

    return await _show_results_page(message, context, is_edit=is_edit)


async def _show_results_page(message, context: ContextTypes.DEFAULT_TYPE, is_edit: bool):
    ud = context.user_data
    result_ids = ud["result_ids"]
    total = len(result_ids)
    shown_count = ud.get("shown_count", 0)

    if shown_count == 0 and total == 0:
        text = (
            f"لا يوجد حاليًا فنيين ({ud['profession_name']}) متاحين بمدينة «{ud['city']}»"
            + (f" — حي {ud['neighborhood']}" if ud.get("neighborhood") else "")
            + "."
        )
        if is_edit:
            await message.edit_text(text)
        else:
            await message.reply_text(text)
        return await _offer_nearby_or_end(message, context)

    if shown_count == 0:
        header = f"وجدنا {total} فني/فنيين ({ud['profession_name']}) بمدينة «{ud['city']}»:"
        if is_edit:
            await message.edit_text(header)
        else:
            await message.reply_text(header)

    page_ids = result_ids[shown_count: shown_count + RESULTS_PAGE_SIZE]
    results = await asyncio.to_thread(db.get_professionals_by_ids, page_ids)

    for p in results:
        await message.reply_text(_professional_card_text(p), reply_markup=_whatsapp_button(p["id"]))

    # نحدّث "آخر ظهور" فقط لمن ظهرت بطاقته فعليًا — أساس عدالة التناوب.
    # نسويها هنا (بعد إرسال هذه الصفحة) لأن القائمة نفسها (result_ids) ثابتة بالذاكرة
    # لباقي الجلسة، فلا تأثير على صفحات لاحقة بنفس الجلسة.
    await asyncio.to_thread(db.mark_shown, page_ids)

    new_shown_count = shown_count + len(results)
    ud["shown_count"] = new_shown_count

    if new_shown_count < total:
        more_keyboard = InlineKeyboardMarkup(
            [[InlineKeyboardButton(f"عرض المزيد ⬇️ ({total - new_shown_count} متبقي)", callback_data=MORE_RESULTS_CB)]]
        )
        await message.reply_text("للمزيد من الفنيين:", reply_markup=more_keyboard)
        return SEARCH_RESULTS

    # استوفينا كل الفنيين المسجّلين بنفس الحي (مهما كان عددهم) — الآن فقط نقترح حي مجاور،
    # ولا نعرضه أبدًا قبل هذي اللحظة (طلب صريح: العدد ما يهم، لازم يستوفي حيه أولًا).
    return await _offer_nearby_or_end(message, context)


async def _offer_nearby_or_end(message, context: ContextTypes.DEFAULT_TYPE):
    """سلسلة اقتراحات لما تنتهي نتائج البحث الحالي: أولًا أحياء مجاورة بنفس المدينة،
    ولو خلصت كل الأحياء المجاورة بلا فائدة، ننتقل لاقتراح أقرب مدينة/مركز ثاني."""
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
            buttons.append([InlineKeyboardButton("❌ إنهاء البحث", callback_data=END_SEARCH_CB)])
            await message.reply_text(
                "استوفينا كل الفنيين بحيك. تحب نبحث لك بحي مجاور؟",
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
            buttons.append([InlineKeyboardButton("❌ إنهاء البحث", callback_data=END_SEARCH_CB)])
            await message.reply_text(
                "ما فيه فنيين أكثر قريبين منك. تحب نبحث لك بأقرب مدينة أو مركز؟",
                reply_markup=InlineKeyboardMarkup(buttons),
            )
            return SEARCH_RESULTS

    await message.reply_text("ما فيه مدن أو مراكز أقرب ثانية نقترحها — جرّب /search من جديد بمنطقة مختلفة.")
    context.user_data.clear()
    return ConversationHandler.END


async def choose_nearby_district(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    district_id = int(query.data.split(":", 1)[1])
    district = await asyncio.to_thread(db.get_sa_district_by_id, district_id)
    if not district:
        await query.edit_message_text("خيار غير معروف، حاول مرة أخرى.")
        return SEARCH_RESULTS

    ud = context.user_data
    ud["neighborhood"] = district["name"]
    ud["district_id"] = district_id
    ud.setdefault("tried_district_ids", []).append(district_id)
    return await _run_search(query.message, context, is_edit=True, customer_telegram_id=update.effective_user.id)


async def choose_nearby_city(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    city_id = int(query.data.split(":", 1)[1])
    city = await asyncio.to_thread(db.get_sa_city_by_id, city_id)
    if not city:
        await query.edit_message_text("خيار غير معروف، حاول مرة أخرى.")
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


async def end_search_results(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text("تمام، تم إنهاء البحث. أرسل /search في أي وقت للبحث من جديد.")
    context.user_data.clear()
    return ConversationHandler.END


async def show_more_results(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    return await _show_results_page(query.message, context, is_edit=False)


async def whatsapp_click(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    professional_id = int(query.data.split(":", 1)[1])

    p = await asyncio.to_thread(db.get_professional_by_id, professional_id)
    if not p:
        await query.answer("عذرًا، هذا الفني لم يعد متاحًا.", show_alert=True)
        return

    await asyncio.to_thread(db.log_contact_click, professional_id, update.effective_user.id)
    await query.answer()

    open_wa_keyboard = InlineKeyboardMarkup(
        [[InlineKeyboardButton("💬 فتح واتساب الآن", url=_wa_link(p["whatsapp_number"]))]]
    )
    await query.message.reply_text(
        f"رقم واتساب {p['full_name']}: {p['whatsapp_number']}",
        reply_markup=open_wa_keyboard,
    )


# ─────────────────────────── إلغاء ───────────────────────────

async def cancel_search(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    await update.message.reply_text("تم إلغاء البحث. أرسل /search في أي وقت للبدء من جديد.")
    return ConversationHandler.END


# ─────────────────────────── تجميع الـ ConversationHandler ───────────────────────────

def build_search_conversation() -> ConversationHandler:
    return ConversationHandler(
        entry_points=[
            CommandHandler("search", search_entry),
            CallbackQueryHandler(search_entry, pattern="^start_search$"),
        ],
        states={
            SEARCH_DOMAIN: [CallbackQueryHandler(choose_search_domain, pattern="^srch_dom:")],
            SEARCH_PROFESSION: [
                CallbackQueryHandler(choose_search_profession, pattern="^srch_prof:"),
                CallbackQueryHandler(back_to_search_domain, pattern="^srch_back_domain$"),
            ],
            SEARCH_REGION: [CallbackQueryHandler(choose_search_region, pattern="^srch_region:")],
            SEARCH_CITY: [
                CallbackQueryHandler(choose_search_city, pattern="^srch_city:"),
                CallbackQueryHandler(search_city_page_nav, pattern="^srch_city_page:"),
                CallbackQueryHandler(back_to_search_regions, pattern=f"^{BACK_TO_REGIONS_CB}$"),
            ],
            SEARCH_NEIGHBORHOOD: [
                CallbackQueryHandler(choose_search_district, pattern="^srch_dist:"),
                CallbackQueryHandler(search_district_page_nav, pattern="^srch_dist_page:"),
                CallbackQueryHandler(skip_neighborhood, pattern=f"^{SKIP_NEIGHBORHOOD_CB}$"),
            ],
            SEARCH_RESULTS: [
                CallbackQueryHandler(show_more_results, pattern=f"^{MORE_RESULTS_CB}$"),
                CallbackQueryHandler(choose_nearby_district, pattern=f"^{NEARBY_DISTRICT_CB_PREFIX}"),
                CallbackQueryHandler(choose_nearby_city, pattern=f"^{NEARBY_CITY_CB_PREFIX}"),
                CallbackQueryHandler(end_search_results, pattern=f"^{END_SEARCH_CB}$"),
            ],
        },
        fallbacks=[CommandHandler("cancel", cancel_search)],
        name="search_conversation",
        persistent=False,
    )


# هاندلر مستقل (خارج الـ ConversationHandler) لأن زر "تواصل واتساب" قد يُضغط
# حتى بعد ما تنتهي المحادثة (النتائج تبقى ظاهرة برسائل سابقة).
def build_whatsapp_click_handler() -> CallbackQueryHandler:
    return CallbackQueryHandler(whatsapp_click, pattern="^srch_wa:[0-9]+$")
