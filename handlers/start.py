# أمر /start — رسالة الترحيب الرئيسية، ونقطة الدخول لباقي البوت.
# أول مرة يفتح فيها المستخدم البوت، نسأله عن لغته (عربي/إنجليزي/أردو) ونحفظها،
# وبعدها كل رسائل الواجهة تُعرض بلغته المختارة (أسماء المدن/الأحياء تبقى عربية دائمًا).

import asyncio

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import CallbackQueryHandler, CommandHandler, ContextTypes

import config
import db
import i18n

CB_START_SEARCH = "start_search"
CB_START_REGISTER = "start_register"
LANG_CB_PREFIX = "set_lang:"


def _language_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("🇸🇦 العربية", callback_data=f"{LANG_CB_PREFIX}ar")],
            [InlineKeyboardButton("🇬🇧 English", callback_data=f"{LANG_CB_PREFIX}en")],
            [InlineKeyboardButton("اردو", callback_data=f"{LANG_CB_PREFIX}ur")],
        ]
    )


def _main_menu_keyboard(lang: str, show_register: bool = True) -> InlineKeyboardMarkup:
    buttons = [[InlineKeyboardButton(i18n.t("menu_search", lang), callback_data=CB_START_SEARCH)]]
    if show_register:
        buttons.append(
            [InlineKeyboardButton(i18n.t("menu_register", lang), callback_data=CB_START_REGISTER)]
        )
    buttons.append([InlineKeyboardButton(i18n.t("menu_channel", lang), url=config.CHANNEL_URL)])
    return InlineKeyboardMarkup(buttons)


async def _build_welcome_message(user_id: int, lang: str):
    existing = await asyncio.to_thread(db.get_professional_by_telegram_id, user_id)

    if existing:
        status_label = i18n.t(f"status_{existing['status']}", lang)
        text = i18n.t("welcome", lang) + i18n.t(
            "status_line", lang, profession=existing["profession_name"], status=status_label
        )
        if existing["status"] == db.STATUS_ACTIVE and not existing["is_subscribed"]:
            free_limit = int(await asyncio.to_thread(
                db.get_setting, "free_contacts_limit", str(db.FREE_CONTACTS_LIMIT)
            ))
            text += i18n.t(
                "free_contacts_line", lang, used=existing["free_contacts_used"], limit=free_limit
            )
        elif existing["status"] == db.STATUS_ACTIVE and existing["is_subscribed"]:
            text += i18n.t("subscribed_line", lang)
        # توضيح صريح: كونك مسجّل كفني ما يمنعك تستخدم البوت كعميل بنفس الحساب —
        # كثير مستخدمين (وحتى أثناء اختبار البوت) يلخبطهم ظهور حالة تسجيلهم
        # كفني ويظنون إنه خطأ يمنعهم من البحث. هذا التنبيه لأي حساب مسجّل،
        # مو حل خاص بحساب معيّن.
        text += i18n.t("dual_role_hint", lang)
        keyboard = _main_menu_keyboard(lang, show_register=False)
    else:
        text = i18n.t("welcome", lang)
        keyboard = _main_menu_keyboard(lang, show_register=True)

    return text, keyboard


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # نمسح أي بيانات محادثة سابقة عالقة (تسجيل/بحث لم يكتمل) — يمنع مشاكل مثل
    # ظهور رسائل بلغة قديمة أو ردود غير متوقعة لو ضغط المستخدم /start أثناء
    # محادثة لم تُنهَ بشكل صحيح.
    context.user_data.clear()
    user_id = update.effective_user.id

    if not await asyncio.to_thread(db.has_chosen_language, user_id):
        await update.message.reply_text(i18n.t("lang_prompt"), reply_markup=_language_keyboard())
        return

    lang = await asyncio.to_thread(db.get_user_language, user_id)
    text, keyboard = await _build_welcome_message(user_id, lang)
    await update.message.reply_text(text, reply_markup=keyboard)


async def language_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """أمر /language — يسمح بتغيير اللغة في أي وقت لاحقًا."""
    await update.message.reply_text(i18n.t("lang_prompt"), reply_markup=_language_keyboard())


async def choose_language(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    lang = query.data.split(":", 1)[1]
    user_id = update.effective_user.id
    await asyncio.to_thread(db.set_user_language, user_id, lang)

    await query.edit_message_text(i18n.t("lang_saved", lang))
    text, keyboard = await _build_welcome_message(user_id, lang)
    await query.message.reply_text(text, reply_markup=keyboard)


def build_language_handlers() -> list:
    return [
        CommandHandler("language", language_command),
        CallbackQueryHandler(choose_language, pattern=f"^{LANG_CB_PREFIX}"),
    ]
