# رسالة دعم/تبرّع اختيارية من العميل (مو الفني) — تظهر بعد كل 10 ضغطات تواصل
# (واتساب/تلغرام) بشكل تراكمي، وتقترح مبلغ صغير (5/10/15 ريال افتراضيًا، قابل
# للتعديل من الإعدادات). اختيارية بالكامل: ما توقف ولا تحجب أي جزء من البحث —
# العميل حر يدفع أو يضغط "لا شكرًا" أو يتجاهلها ويكمل عادي.
#
# نفس طريقتي الدفع المستخدمتين باشتراك الفنيين (Tap + Telegram Stars)، لكن بجدول
# مستقل تمامًا (donation_payments) لأنه ما له علاقة بأي professional_id.

import asyncio

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, LabeledPrice, Update
from telegram.ext import CallbackQueryHandler, ContextTypes, MessageHandler, filters

import db
import i18n
import tap_client

DONATE_EVERY_N_CONTACTS = 10
DEFAULT_DONATION_AMOUNTS_SAR = [5, 10, 15]
STARS_PER_SAR = 5  # نفس نسبة اشتراك الفنيين (30 ريال = 150 نجمة)

CB_DONATE_AMOUNT_PREFIX = "donate_amt:"
CB_DONATE_TAP_PREFIX = "donate_tap:"
CB_DONATE_STARS_PREFIX = "donate_stars:"
CB_DONATE_DISMISS = "donate_dismiss"
CB_TAP_VERIFY_PREFIX = "donate_tap_verify:"
STARS_PAYLOAD_PREFIX = "donate_stars:"


def _donation_amounts() -> list[int]:
    raw = db.get_setting("donation_amounts_sar", ",".join(str(a) for a in DEFAULT_DONATION_AMOUNTS_SAR))
    try:
        return [int(x.strip()) for x in raw.split(",") if x.strip()]
    except ValueError:
        return DEFAULT_DONATION_AMOUNTS_SAR


def _stars_for_sar(sar: int) -> int:
    return sar * STARS_PER_SAR


def _amount_keyboard(lang: str) -> InlineKeyboardMarkup:
    amounts = _donation_amounts()
    buttons = [
        [InlineKeyboardButton(i18n.t("donate_amount_btn", lang, sar=sar), callback_data=f"{CB_DONATE_AMOUNT_PREFIX}{sar}")]
        for sar in amounts
    ]
    buttons.append([InlineKeyboardButton(i18n.t("donate_dismiss_btn", lang), callback_data=CB_DONATE_DISMISS)])
    return InlineKeyboardMarkup(buttons)


def _method_keyboard(sar: int, lang: str) -> InlineKeyboardMarkup:
    stars = _stars_for_sar(sar)
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton(i18n.t("donate_tap_btn", lang, sar=sar), callback_data=f"{CB_DONATE_TAP_PREFIX}{sar}")],
            [InlineKeyboardButton(i18n.t("donate_stars_btn", lang, stars=stars), callback_data=f"{CB_DONATE_STARS_PREFIX}{sar}")],
        ]
    )


async def maybe_prompt_donation(context: ContextTypes.DEFAULT_TYPE, customer_telegram_id: int, lang: str):
    """تُستدعى بعد كل ضغطة تواصل ناجحة — لو العدد التراكمي وصل لمضاعف 10، تُرسل
    رسالة دعم اختيارية كرسالة إضافية منفصلة (بعد ما تكمل رسالة التواصل نفسها
    عاديًا)، بدون أي تأثير على تدفق البحث/التواصل."""
    count = await asyncio.to_thread(db.count_contact_clicks_by_customer, customer_telegram_id)
    if count == 0 or count % DONATE_EVERY_N_CONTACTS != 0:
        return

    try:
        await context.bot.send_message(
            chat_id=customer_telegram_id,
            text=i18n.t("donate_prompt", lang, count=count),
            reply_markup=_amount_keyboard(lang),
        )
    except Exception:
        # ما نكسر تدفق التواصل الأساسي بسبب فشل إرسال رسالة الدعم الاختيارية
        pass


async def choose_donation_amount(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lang = await asyncio.to_thread(db.get_user_language, update.effective_user.id)
    query = update.callback_query
    await query.answer()
    sar = int(query.data.split(":", 1)[1])
    await query.edit_message_text(i18n.t("donate_method_prompt", lang, sar=sar), reply_markup=_method_keyboard(sar, lang))


async def dismiss_donation(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lang = await asyncio.to_thread(db.get_user_language, update.effective_user.id)
    query = update.callback_query
    await query.answer()
    await query.edit_message_text(i18n.t("donate_dismissed", lang))


# ─────────────────────────── مسار Tap ───────────────────────────

async def donate_via_tap(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lang = await asyncio.to_thread(db.get_user_language, update.effective_user.id)
    query = update.callback_query
    await query.answer()
    sar = int(query.data.split(":", 1)[1])
    customer_id = update.effective_user.id

    donation_id = await asyncio.to_thread(db.create_pending_donation, customer_id, "tap", None, float(sar))

    try:
        charge = await asyncio.to_thread(tap_client.create_donation_charge, float(sar), customer_id)
    except tap_client.TapNotConfigured:
        await query.edit_message_text(i18n.t("donate_tap_not_configured", lang))
        return
    except Exception:
        await query.edit_message_text(i18n.t("donate_tap_error", lang))
        return

    await asyncio.to_thread(db.update_donation_external_id, donation_id, charge["id"])

    keyboard = InlineKeyboardMarkup(
        [
            [InlineKeyboardButton(i18n.t("donate_pay_now_btn", lang), url=charge["redirect_url"])],
            [InlineKeyboardButton(i18n.t("donate_verify_btn", lang), callback_data=f"{CB_TAP_VERIFY_PREFIX}{charge['id']}")],
        ]
    )
    await query.edit_message_text(i18n.t("donate_tap_instructions", lang), reply_markup=keyboard)


async def verify_donation_tap(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lang = await asyncio.to_thread(db.get_user_language, update.effective_user.id)
    query = update.callback_query
    charge_id = query.data.split(":", 1)[1]

    try:
        status = await asyncio.to_thread(tap_client.get_charge_status, charge_id)
    except tap_client.TapNotConfigured:
        await query.answer(i18n.t("donate_tap_not_configured", lang), show_alert=True)
        return
    except Exception:
        await query.answer(i18n.t("donate_tap_verify_error", lang), show_alert=True)
        return

    if not tap_client.is_paid(status):
        await query.answer(i18n.t("donate_tap_not_paid_yet", lang), show_alert=True)
        return

    donation = await asyncio.to_thread(db.get_donation_by_external_id, "tap", charge_id)
    if donation and donation["status"] == "paid":
        await query.answer(i18n.t("donate_already_paid", lang), show_alert=True)
        return

    if donation:
        await asyncio.to_thread(db.mark_donation_paid, donation["id"])

    await query.answer()
    await query.edit_message_text(i18n.t("donate_thanks", lang))


# ─────────────────────────── مسار Telegram Stars ───────────────────────────

async def donate_via_stars(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    sar = int(query.data.split(":", 1)[1])
    stars = _stars_for_sar(sar)
    customer_id = update.effective_user.id

    donation_id = await asyncio.to_thread(db.create_pending_donation, customer_id, "stars", None, float(sar))

    await context.bot.send_invoice(
        chat_id=update.effective_chat.id,
        title="دعم بوت فني",
        description="مساهمة اختيارية لدعم تشغيل وتطوير بوت فني — شكرًا لك 🙏",
        payload=f"{STARS_PAYLOAD_PREFIX}{donation_id}",
        provider_token="",
        currency="XTR",
        prices=[LabeledPrice("دعم بوت فني", stars)],
    )


async def donation_stars_successful_payment(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """نفس فكرة stars_successful_payment باشتراك الفنيين، لكن payload تبدأ
    بـ donate_stars: فقط — الفاتورة الأخرى (اشتراك الفني) تبدأ بـ sub_stars:،
    فنميّز بينهم من البادئة قبل ما نحاول نعالج الدفع هنا."""
    payment = update.message.successful_payment
    payload = payment.invoice_payload
    if not payload.startswith(STARS_PAYLOAD_PREFIX):
        return  # مو دفعة تبرّع — خلّها لهاندلر اشتراك الفنيين يعالجها

    lang = await asyncio.to_thread(db.get_user_language, update.effective_user.id)
    try:
        donation_id = int(payload.split(":", 1)[1])
    except (ValueError, IndexError):
        await update.message.reply_text(i18n.t("donate_stars_match_error", lang))
        return

    await asyncio.to_thread(db.mark_donation_paid, donation_id)
    await asyncio.to_thread(
        db.update_donation_external_id, donation_id, payment.telegram_payment_charge_id
    )
    await update.message.reply_text(i18n.t("donate_thanks", lang))


def build_donation_handlers() -> list:
    return [
        CallbackQueryHandler(choose_donation_amount, pattern=f"^{CB_DONATE_AMOUNT_PREFIX}"),
        CallbackQueryHandler(dismiss_donation, pattern=f"^{CB_DONATE_DISMISS}$"),
        CallbackQueryHandler(donate_via_tap, pattern=f"^{CB_DONATE_TAP_PREFIX}"),
        CallbackQueryHandler(verify_donation_tap, pattern=f"^{CB_TAP_VERIFY_PREFIX}"),
        CallbackQueryHandler(donate_via_stars, pattern=f"^{CB_DONATE_STARS_PREFIX}"),
        # ملاحظة: PreCheckoutQueryHandler وMessageHandler(filters.SUCCESSFUL_PAYMENT)
        # مسجّلين مرة وحدة فقط بـ subscription.py (تلغرام يسمح بمعالج وحيد لكل نوع) —
        # stars_successful_payment هناك تستدعي donation_stars_successful_payment هنا
        # لو كانت الدفعة تبرّع، راجع main.py/subscription.py للتفاصيل.
    ]
