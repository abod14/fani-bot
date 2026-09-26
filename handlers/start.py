# أمر /start — رسالة الترحيب الرئيسية، ونقطة الدخول لباقي البوت.

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes

import asyncio
import db

CB_START_SEARCH = "start_search"
CB_START_REGISTER = "start_register"

WELCOME_TEXT = (
    "أهلًا بك في بوت «فني» 👋\n\n"
    "بوت «فني» يربط العملاء بمهنيين وفنيين موثوقين بمختلف المدن.\n\n"
    "اختر ما يناسبك:"
)


def _main_menu_keyboard(show_register: bool = True) -> InlineKeyboardMarkup:
    buttons = [[InlineKeyboardButton("🔍 البحث عن فني", callback_data=CB_START_SEARCH)]]
    if show_register:
        buttons.append(
            [InlineKeyboardButton("📝 التسجيل كفني", callback_data=CB_START_REGISTER)]
        )
    return InlineKeyboardMarkup(buttons)


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    existing = await asyncio.to_thread(db.get_professional_by_telegram_id, user_id)

    if existing:
        status_label = db.STATUS_LABELS_AR.get(existing["status"], existing["status"])
        status_line = (
            f"\n\nأنت مسجّل لدينا كفني ({existing['profession_name']}) "
            f"— حالة طلبك: {status_label}."
        )
        if existing["status"] == db.STATUS_ACTIVE and not existing["is_subscribed"]:
            free_limit = int(await asyncio.to_thread(
                db.get_setting, "free_contacts_limit", str(db.FREE_CONTACTS_LIMIT)
            ))
            status_line += (
                f"\nاستخدمت {existing['free_contacts_used']} من {free_limit} "
                "فرص مجانية. أرسل /subscribe لتفعيل الاشتراك والاستمرار بالظهور بدون حدود."
            )
        elif existing["status"] == db.STATUS_ACTIVE and existing["is_subscribed"]:
            status_line += "\nاشتراكك مفعّل ✅"
        text = WELCOME_TEXT + status_line
        # ما نعرض زر تسجيل من جديد لأنه مسجّل مسبقًا
        keyboard = _main_menu_keyboard(show_register=False)
    else:
        text = WELCOME_TEXT
        keyboard = _main_menu_keyboard(show_register=True)

    await update.message.reply_text(text, reply_markup=keyboard)
