# أمر /delete_account — حق حذف الحساب والبيانات (متطلب أساسي لحماية الخصوصية).
# يحذف نهائيًا كل ما يخص هذا المستخدم: تسجيله كفني (لو مسجّل) وسجلات تواصله ودفعاته،
# وكذلك سجلات بحثه وضغطاته على واتساب بصفته عميل — بعد تأكيد صريح منه.

import asyncio

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import CallbackQueryHandler, CommandHandler, ContextTypes

import db

CONFIRM_CB = "privacy_confirm_delete"
CANCEL_CB = "privacy_cancel_delete"


async def delete_account_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    has_data = await asyncio.to_thread(db.has_any_user_data, user_id)
    if not has_data:
        await update.message.reply_text("لا يوجد لدينا حاليًا أي بيانات مخزّنة باسمك.")
        return

    keyboard = InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("✅ نعم، احذف بياناتي نهائيًا", callback_data=CONFIRM_CB)],
            [InlineKeyboardButton("❌ إلغاء", callback_data=CANCEL_CB)],
        ]
    )
    await update.message.reply_text(
        "⚠️ سيتم حذف كل بياناتك من بوت «فني» نهائيًا وبلا رجعة:\n"
        "تسجيلك كفني (إن وجد) وأرقام تواصلك، وسجلات بحثك وتواصلك السابقة.\n\n"
        "هل أنت متأكد؟",
        reply_markup=keyboard,
    )


async def confirm_delete_account(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = update.effective_user.id
    await asyncio.to_thread(db.delete_all_user_data, user_id)
    await query.edit_message_text(
        "✅ تم حذف جميع بياناتك نهائيًا من بوت «فني».\n"
        "يمكنك التسجيل أو البحث من جديد في أي وقت بإرسال /start."
    )


async def cancel_delete_account(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text("تم الإلغاء، لم يُحذف شيء.")


def build_privacy_handlers() -> list:
    return [
        CommandHandler("delete_account", delete_account_command),
        CallbackQueryHandler(confirm_delete_account, pattern=f"^{CONFIRM_CB}$"),
        CallbackQueryHandler(cancel_delete_account, pattern=f"^{CANCEL_CB}$"),
    ]
