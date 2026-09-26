# تدفق /search (الشكل الجديد) — الترتيب: المهنة (مجال ثم مهنة) → المدينة → الحي (اختياري)
# ثم نتائج مُرتّبة بنظام تناوب عادل، صفحات من 5، وزر "تواصل عبر واتساب" يسجّل الضغطة
# ويستهلك من الفرص المجانية الثلاث لكل فني قبل ما يحتاج اشتراك.

import asyncio

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
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

SEARCH_DOMAIN, SEARCH_PROFESSION, SEARCH_CITY, SEARCH_NEIGHBORHOOD, SEARCH_RESULTS = range(200, 205)

SKIP_NEIGHBORHOOD_CB = "srch_skip_nb"
MORE_RESULTS_CB = "srch_more"


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

    await query.edit_message_text(f"مهنة: {profession['name']}\n\nما هي مدينتك؟ أرسل اسمها:")
    return SEARCH_CITY


# ─────────────────────────── الخطوة 2: المدينة ───────────────────────────

async def got_search_city(update: Update, context: ContextTypes.DEFAULT_TYPE):
    city = update.message.text.strip()
    if len(city) < 2:
        await update.message.reply_text("اسم المدينة غير واضح، أرسله مرة أخرى:")
        return SEARCH_CITY

    context.user_data["city"] = city
    keyboard = InlineKeyboardMarkup(
        [[InlineKeyboardButton("تخطي (كل أحياء المدينة)", callback_data=SKIP_NEIGHBORHOOD_CB)]]
    )
    await update.message.reply_text(
        "ما هو الحي؟ (اختياري — تقدر تتخطى وتبحث بكل أحياء المدينة)",
        reply_markup=keyboard,
    )
    return SEARCH_NEIGHBORHOOD


# ─────────────────────────── الخطوة 3: الحي ───────────────────────────

async def got_neighborhood_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["neighborhood"] = update.message.text.strip()
    return await _run_search(update.message, context, is_edit=False, customer_telegram_id=update.effective_user.id)


async def skip_neighborhood(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    context.user_data["neighborhood"] = None
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
            + ".\nجرّب مدينة أو حي آخر عبر /search."
        )
        if is_edit:
            await message.edit_text(text)
        else:
            await message.reply_text(text)
        context.user_data.clear()
        return ConversationHandler.END

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
            SEARCH_CITY: [MessageHandler(filters.TEXT & ~filters.COMMAND, got_search_city)],
            SEARCH_NEIGHBORHOOD: [
                CallbackQueryHandler(skip_neighborhood, pattern=f"^{SKIP_NEIGHBORHOOD_CB}$"),
                MessageHandler(filters.TEXT & ~filters.COMMAND, got_neighborhood_text),
            ],
            SEARCH_RESULTS: [
                CallbackQueryHandler(show_more_results, pattern=f"^{MORE_RESULTS_CB}$"),
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
