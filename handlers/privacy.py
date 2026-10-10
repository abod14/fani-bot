# أمر /delete_account — حق حذف الحساب والبيانات (متطلب أساسي لحماية الخصوصية).
# يحذف نهائيًا كل ما يخص هذا المستخدم: تسجيله كفني (لو مسجّل) وسجلات تواصله ودفعاته،
# وكذلك سجلات بحثه وضغطاته على واتساب بصفته عميل — بعد تأكيد صريح منه.

import asyncio

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (ApplicationHandlerStop, CallbackQueryHandler, CommandHandler, ContextTypes,
                          MessageHandler, filters)

import db
import i18n

CONFIRM_CB = "privacy_confirm_delete"
CANCEL_CB = "privacy_cancel_delete"
CONFIRM_ALL_CB = "privacy_confirm_delete_all"   # فني: حذف كلي فوري (بلا أرشيف 90 يومًا)


async def delete_account_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    lang = await asyncio.to_thread(db.get_user_language, user_id)
    has_data = await asyncio.to_thread(db.has_any_user_data, user_id)
    if not has_data:
        await update.message.reply_text(i18n.t("privacy_no_data", lang))
        return

    is_pro = await asyncio.to_thread(db.get_professional_by_telegram_id, user_id)
    rows = [[InlineKeyboardButton(i18n.t("privacy_confirm_btn", lang), callback_data=CONFIRM_CB)]]
    if is_pro:
        rows.append([InlineKeyboardButton(i18n.t("privacy_confirm_all_btn", lang), callback_data=CONFIRM_ALL_CB)])
    rows.append([InlineKeyboardButton(i18n.t("privacy_cancel_btn", lang), callback_data=CANCEL_CB)])
    keyboard = InlineKeyboardMarkup(rows)
    await update.message.reply_text(i18n.t("privacy_confirm_prompt", lang), reply_markup=keyboard)


async def confirm_delete_account(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = update.effective_user.id
    lang = await asyncio.to_thread(db.get_user_language, user_id)
    archived = await asyncio.to_thread(db.delete_all_user_data, user_id)
    if archived and query.data == CONFIRM_ALL_CB:
        await asyncio.to_thread(db.purge_archive, archived)
        archived = []
    if not archived:
        await query.edit_message_text(i18n.t("privacy_deleted", lang))
        return
    # فني: حُذف من البوت نهائيًا، وبياناته الأساسية في أرشيف اللوحة — نسأله عن السبب (اختياري)
    aid = archived[0]
    kb = InlineKeyboardMarkup([[InlineKeyboardButton(i18n.t(f"delr_{code}", lang), callback_data=f"delr:{aid}:{code}")]
                               for code in REASON_CODES])
    await query.edit_message_text(i18n.t("privacy_deleted_pro", lang) + "\n\n" + i18n.t("delr_question", lang),
                                  reply_markup=kb)


REASON_CODES = ["few", "fee", "job", "move", "bot", "other", "skip"]


async def on_delete_reason(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    lang = await asyncio.to_thread(db.get_user_language, update.effective_user.id)
    try:
        _, aid, code = query.data.split(":")
        aid = int(aid)
    except ValueError:
        return
    if code == "other":
        context.user_data["del_reason_arch"] = aid
        await query.edit_message_text(i18n.t("delr_write", lang))
        return
    if code != "skip" and code in REASON_CODES:
        await asyncio.to_thread(db.set_deletion_reason, aid, i18n.t(f"delr_{code}", "ar"), "pro")
    await query.edit_message_text(i18n.t("delr_thanks", lang))


async def on_delete_reason_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """يلتقط نص «سبب آخر» قبل باقي المعالجات (مجموعة -2) — لا يفعل شيئًا لغير من ينتظر سببه."""
    aid = context.user_data.pop("del_reason_arch", None) if context.user_data is not None else None
    if not aid:
        return
    lang = await asyncio.to_thread(db.get_user_language, update.effective_user.id)
    await asyncio.to_thread(db.set_deletion_reason, aid, update.message.text, "pro")
    await update.message.reply_text(i18n.t("delr_thanks_text", lang))
    raise ApplicationHandlerStop


def build_delete_reason_text_handler():
    return MessageHandler(filters.TEXT & ~filters.COMMAND, on_delete_reason_text)


async def cancel_delete_account(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    lang = await asyncio.to_thread(db.get_user_language, update.effective_user.id)
    await query.edit_message_text(i18n.t("privacy_cancelled", lang))


def build_privacy_handlers() -> list:
    return [
        CommandHandler("delete_account", delete_account_command),
        CallbackQueryHandler(confirm_delete_account, pattern=f"^{CONFIRM_CB}$"),
        CallbackQueryHandler(confirm_delete_account, pattern=f"^{CONFIRM_ALL_CB}$"),
        CallbackQueryHandler(cancel_delete_account, pattern=f"^{CANCEL_CB}$"),
        CallbackQueryHandler(on_delete_reason, pattern=r"^delr:\d+:\w+$"),
    ]
