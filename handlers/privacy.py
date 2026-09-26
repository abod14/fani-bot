# أمر /delete_account — حق حذف الحساب والبيانات (متطلب أساسي لحماية الخصوصية).
# يحذف نهائيًا كل ما يخص هذا المستخدم: تسجيله كفني (لو مسجّل) وسجلات تواصله ودفعاته،
# وكذلك سجلات بحثه وضغطاته على واتساب بصفته عميل — بعد تأكيد صريح منه.

import asyncio

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import CallbackQueryHandler, CommandHandler, ContextTypes

import db
import i18n

CONFIRM_CB = "privacy_confirm_delete"
CANCEL_CB = "privacy_cancel_delete"


async def delete_account_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    lang = await asyncio.to_thread(db.get_user_language, user_id)
    has_data = await asyncio.to_thread(db.has_any_user_data, user_id)
    if not has_data:
        await update.message.reply_text(i18n.t("privacy_no_data", lang))
        return

    keyboard = InlineKeyboardMarkup(
        [
            [InlineKeyboardButton(i18n.t("privacy_confirm_btn", lang), callback_data=CONFIRM_CB)],
            [InlineKeyboardButton(i18n.t("privacy_cancel_btn", lang), callback_data=CANCEL_CB)],
        ]
    )
    await update.message.reply_text(i18n.t("privacy_confirm_prompt", lang), reply_markup=keyboard)


async def confirm_delete_account(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = update.effective_user.id
    lang = await asyncio.to_thread(db.get_user_language, user_id)
    await asyncio.to_thread(db.delete_all_user_data, user_id)
    await query.edit_message_text(i18n.t("privacy_deleted", lang))


async def cancel_delete_account(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    lang = await asyncio.to_thread(db.get_user_language, update.effective_user.id)
    await query.edit_message_text(i18n.t("privacy_cancelled", lang))


def build_privacy_handlers() -> list:
    return [
        CommandHandler("delete_account", delete_account_command),
        CallbackQueryHandler(confirm_delete_account, pattern=f"^{CONFIRM_CB}$"),
        CallbackQueryHandler(cancel_delete_account, pattern=f"^{CANCEL_CB}$"),
    ]
