# (ملغاة — أكتوبر 2026: ما نعطي مكافآت دعوة جديدة؛ الفرص اللي انكسبت قبل تبقى للفني)
# «ادعُ زميلك» — كل فني مسجّل له رابط دعوة خاص (?start=ref_<رقمه>). أي فني جديد يكمل
# تسجيله من هذا الرابط، يكسب الداعي فرص مجانية إضافية (إعداد referral_bonus، الافتراضي 3)
# ويوصله إشعار. الاحتساب كله بـ db.credit_referral (حماية من التلاعب هناك).

import asyncio
from urllib.parse import quote

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import CallbackQueryHandler, CommandHandler, ContextTypes

import db
import i18n

CB_INVITE = "start_invite"
REF_PREFIX = "ref_"


def parse_ref(arg: str | None) -> int | None:
    """يرجّع رقم الفني الداعي من وسم ?start=ref_25، أو None."""
    if arg and arg.startswith(REF_PREFIX) and arg[len(REF_PREFIX):].isdigit():
        return int(arg[len(REF_PREFIX):])
    return None


def referral_link(bot_username: str, professional_id: int) -> str:
    return f"https://t.me/{bot_username}?start={REF_PREFIX}{professional_id}"


async def build_invite(context: ContextTypes.DEFAULT_TYPE, professional: dict, lang: str):
    """نص رسالة الدعوة + أزرار المشاركة (واتساب/تلغرام) برسالة جاهزة فيها الرابط."""
    link = referral_link(context.bot.username, professional["id"])
    bonus = int(await asyncio.to_thread(db.get_setting, "referral_bonus", str(db.REFERRAL_BONUS_DEFAULT)))
    stats = await asyncio.to_thread(db.referral_stats, professional["id"])
    text = i18n.t("ref_invite_msg", lang, bonus=bonus, link=link)
    if stats["count"]:
        text += "\n\n" + i18n.t("ref_stats_line", lang, count=stats["count"], earned=stats["bonus"])

    share_text = i18n.t("ref_share_text", lang, link=link)
    keyboard = InlineKeyboardMarkup(
        [
            [InlineKeyboardButton(i18n.t("ref_share_wa_btn", lang), url=f"https://wa.me/?text={quote(share_text)}")],
            [InlineKeyboardButton(
                i18n.t("ref_share_tg_btn", lang),
                url=f"https://t.me/share/url?url={quote(link)}&text={quote(i18n.t('ref_share_text_short', lang))}",
            )],
        ]
    )
    return text, keyboard


async def invite_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """زر «ادعُ زملاءك» بقائمة البداية (للفنيين المسجّلين)."""
    query = update.callback_query
    if query:
        await query.answer()
    target = update.message or query.message
    lang = await asyncio.to_thread(db.get_user_language, update.effective_user.id)
    # خاصية «ادعُ زميلك» ملغاة (قرار المالك بعد فتح البوت على واتساب) — الأزرار القديمة
    # بالرسائل السابقة ترد بهذا التنبيه بدل ما تعلق
    await target.reply_text(i18n.t("ref_disabled", lang))


async def after_registration(context: ContextTypes.DEFAULT_TYPE, message, new_professional_id: int, lang: str):
    """يُستدعى بعد اكتمال تسجيل فني: (1) يحتسب الدعوة للداعي ويبلّغه، (2) يرسل للفني
    الجديد رابط دعوته الخاص عشان يدعو زملاءه هو كمان."""
    result = await asyncio.to_thread(db.credit_referral, new_professional_id)
    if result:
        referrer, bonus = result
        new = await asyncio.to_thread(db.get_professional_by_id, new_professional_id)
        stats = await asyncio.to_thread(db.referral_stats, referrer["id"])
        r_lang = await asyncio.to_thread(db.get_user_language, referrer["telegram_user_id"])
        try:
            await context.bot.send_message(
                chat_id=referrer["telegram_user_id"],
                text=i18n.t(
                    "ref_credited_notice", r_lang,
                    name=new["full_name"], profession=new["profession_name"], bonus=bonus, count=stats["count"],
                ),
            )
        except Exception:  # noqa: BLE001 — الداعي ممكن حاظر البوت؛ ما نوقف التسجيل بسببه
            pass

    new = await asyncio.to_thread(db.get_professional_by_id, new_professional_id)
    if new:
        text, keyboard = await build_invite(context, new, lang)
        await message.reply_text(text, reply_markup=keyboard)


def build_referral_handlers() -> list:
    return [
        CallbackQueryHandler(invite_command, pattern=f"^{CB_INVITE}$"),
        CommandHandler("invite", invite_command),
    ]
