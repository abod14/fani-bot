# إشعار الأدمن بتسجيل جديد + أزرار قبول/رفض، وتحديث حالة الفني بعد قرار الأدمن.

import asyncio

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import CallbackQueryHandler, ContextTypes

import db
from config import ADMIN_TELEGRAM_ID

CB_APPROVE_PREFIX = "admin_approve:"
CB_REJECT_PREFIX = "admin_reject:"


def _admin_keyboard(row_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("✅ قبول", callback_data=f"{CB_APPROVE_PREFIX}{row_id}"),
                InlineKeyboardButton("❌ رفض", callback_data=f"{CB_REJECT_PREFIX}{row_id}"),
            ]
        ]
    )


async def notify_admin_new_registration(context: ContextTypes.DEFAULT_TYPE, row_id: int):
    p = await asyncio.to_thread(db.get_professional_by_id, row_id)
    if not p:
        return

    import json as _json
    services = "، ".join(_json.loads(p["services_json"])) or "لا يوجد"

    text = (
        "🆕 طلب تسجيل فني جديد\n\n"
        f"الاسم: {p['full_name']}\n"
        f"المدينة: {p['city']}\n"
        f"الحي: {p['neighborhood'] or 'لم يُحدد'}\n"
        f"رقم التواصل: {p['whatsapp_number']} ({'واتساب ✅' if p.get('has_whatsapp', 1) else 'اتصال فقط بدون واتساب 📞'})\n"
        f"حساب التلغرام: {p['telegram_contact_number'] or 'غير متاح'}\n"
        f"المجال: {p['domain_name']}\n"
        f"المهنة: {p['profession_name']}\n"
        f"الخدمات: {services}"
    )

    await context.bot.send_message(
        chat_id=ADMIN_TELEGRAM_ID,
        text=text,
        reply_markup=_admin_keyboard(row_id),
    )


async def handle_admin_decision(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query

    if update.effective_user.id != ADMIN_TELEGRAM_ID:
        await query.answer("هذا الإجراء متاح للأدمن فقط.", show_alert=True)
        return

    await query.answer()
    data = query.data
    is_approve = data.startswith(CB_APPROVE_PREFIX)
    row_id = int(data.split(":", 1)[1])

    p = await asyncio.to_thread(db.get_professional_by_id, row_id)
    if not p:
        await query.edit_message_text("⚠️ لم يعد هذا الطلب موجودًا.")
        return

    new_status = db.STATUS_ACTIVE if is_approve else db.STATUS_REJECTED
    await asyncio.to_thread(db.set_status, row_id, new_status)

    decision_label = "تم القبول ✅" if is_approve else "تم الرفض ❌"
    await query.edit_message_text(query.message.text + f"\n\n— {decision_label}")

    if is_approve:
        professional_text = (
            "تمت الموافقة على تسجيلك، وأصبحت الآن ظاهرًا للعملاء عند البحث."
        )
    else:
        professional_text = (
            "نعتذر، لم تتم الموافقة على طلب تسجيلك في الوقت الحالي."
        )

    try:
        await context.bot.send_message(chat_id=p["telegram_user_id"], text=professional_text)
    except Exception:
        # الفني ممكن يكون حظر البوت أو غيره — ما نوقف تنفيذ باقي الكود بسبب هذا
        pass


def build_admin_handler() -> CallbackQueryHandler:
    return CallbackQueryHandler(
        handle_admin_decision, pattern=f"^({CB_APPROVE_PREFIX}|{CB_REJECT_PREFIX})[0-9]+$"
    )
