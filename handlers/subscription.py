# تدفق الاشتراك — قائمة اختيار الطريقة (Tap / Stars)، ثم كل طريقة بمسارها.
# Tap: رابط دفع خارجي + زر "تحققت من الدفع" (بدون سيرفر webhook منفصل).
# Stars: فاتورة Telegram الرسمية (send_invoice بعملة XTR).

import asyncio

from telegram import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    LabeledPrice,
    Update,
)
from telegram.ext import (
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    PreCheckoutQueryHandler,
    filters,
)

import db
import tap_client
from config import SUBSCRIPTION_DAYS, SUBSCRIPTION_PRICE_SAR, SUBSCRIPTION_PRICE_STARS

CB_SUBSCRIBE_MENU = "sub_menu"
CB_SUBSCRIBE_TAP = "sub_tap"
CB_SUBSCRIBE_STARS = "sub_stars"
CB_TAP_VERIFY_PREFIX = "sub_tap_verify:"

STARS_PAYLOAD_PREFIX = "sub_stars:"


def _require_registered_professional(update_effective_user_id: int):
    return db.get_professional_by_telegram_id(update_effective_user_id)


def _current_prices():
    """يقرأ أسعار الاشتراك من جدول settings (تعديلات اللوحة)، وإلا يرجع للقيم
    الافتراضية بـ config.py. هذا يخلي تعديل السعر من اللوحة يأثر فورًا بدون إعادة تشغيل."""
    sar = float(db.get_setting("subscription_price_sar", str(SUBSCRIPTION_PRICE_SAR)))
    stars = int(db.get_setting("subscription_price_stars", str(SUBSCRIPTION_PRICE_STARS)))
    days = int(db.get_setting("subscription_days", str(SUBSCRIPTION_DAYS)))
    return sar, stars, days


def _subscription_menu_keyboard(sar: float, stars: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton(
                f"💳 الدفع عبر Tap (مدى/فيزا/آبل باي) — {sar:.0f} ريال",
                callback_data=CB_SUBSCRIBE_TAP,
            )],
            [InlineKeyboardButton(
                f"⭐ الدفع عبر Telegram Stars — {stars} نجمة",
                callback_data=CB_SUBSCRIBE_STARS,
            )],
        ]
    )


# ─────────────────────────── نقطة الدخول: /subscribe ───────────────────────────

async def subscribe_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    target = update.message or update.callback_query.message
    if update.callback_query:
        await update.callback_query.answer()

    professional = await asyncio.to_thread(
        _require_registered_professional, update.effective_user.id
    )
    if not professional:
        await target.reply_text("لازم تسجّل كفني أولاً عبر /register قبل ما تشترك.")
        return

    if professional["status"] != db.STATUS_ACTIVE:
        await target.reply_text(
            "حسابك لسه قيد المراجعة أو غير مفعّل — الاشتراك متاح فقط للفنيين النشطين."
        )
        return

    sar, stars, days = await asyncio.to_thread(_current_prices)
    await target.reply_text(
        f"اختر طريقة الدفع للاشتراك الشهري ({days} يوم):",
        reply_markup=_subscription_menu_keyboard(sar, stars),
    )


# ─────────────────────────── مسار Tap ───────────────────────────

async def subscribe_via_tap(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    professional = await asyncio.to_thread(
        _require_registered_professional, update.effective_user.id
    )
    if not professional:
        await query.edit_message_text("لازم تسجّل كفني أولاً عبر /register.")
        return

    sar, stars, days = await asyncio.to_thread(_current_prices)

    payment_id = await asyncio.to_thread(
        db.create_pending_payment, professional["id"], "tap", None, f"{sar:.2f} SAR"
    )

    try:
        charge = await asyncio.to_thread(
            tap_client.create_charge,
            sar, professional["full_name"], professional["id"],
        )
    except tap_client.TapNotConfigured:
        await query.edit_message_text(
            "⚠️ الدفع عبر Tap غير مفعّل حاليًا (يحتاج ضبط TAP_SECRET_KEY بملف .env). "
            "جرّب الاشتراك عبر Telegram Stars بدلًا عنه، أو تواصل مع الدعم."
        )
        return
    except Exception:
        await query.edit_message_text(
            "⚠️ صار خطأ أثناء التواصل مع Tap. حاول مرة أخرى بعد شوي، أو جرّب Stars."
        )
        return

    await asyncio.to_thread(db.update_payment_external_id, payment_id, charge["id"])

    keyboard = InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("💳 الدفع الآن", url=charge["redirect_url"])],
            [InlineKeyboardButton(
                "✅ تحققت من الدفع", callback_data=f"{CB_TAP_VERIFY_PREFIX}{charge['id']}"
            )],
        ]
    )
    await query.edit_message_text(
        "اضغط للدفع عبر Tap (مدى / فيزا / آبل باي)، وبعد ما تخلّص الدفع ارجع واضغط "
        "'تحققت من الدفع' عشان نفعّل اشتراكك:",
        reply_markup=keyboard,
    )


async def verify_tap_payment(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    charge_id = query.data.split(":", 1)[1]

    professional = await asyncio.to_thread(
        _require_registered_professional, update.effective_user.id
    )
    if not professional:
        await query.answer("لازم تسجّل كفني أولاً.", show_alert=True)
        return

    try:
        status = await asyncio.to_thread(tap_client.get_charge_status, charge_id)
    except tap_client.TapNotConfigured:
        await query.answer("الدفع عبر Tap غير مفعّل حاليًا.", show_alert=True)
        return
    except Exception:
        await query.answer("تعذّر التحقق الآن، حاول بعد شوي.", show_alert=True)
        return

    if not tap_client.is_paid(status):
        await query.answer(
            "لسه ما وصلنا تأكيد الدفع. لو دفعت فعلًا، انتظر دقيقة وجرّب الزر مرة ثانية.",
            show_alert=True,
        )
        return

    payment = await asyncio.to_thread(db.get_payment_by_external_id, "tap", charge_id)
    if payment and payment["status"] == "paid":
        await query.answer("اشتراكك مفعّل مسبقًا ✅", show_alert=True)
        return

    if payment:
        await asyncio.to_thread(db.mark_payment_paid, payment["id"])

    _, _, days = await asyncio.to_thread(_current_prices)
    await asyncio.to_thread(db.activate_subscription, professional["id"], days)
    await query.answer()
    await query.edit_message_text(
        f"✅ تم تفعيل اشتراكك لمدة {days} يوم. راح تظهر بنتائج البحث بدون حدود "
        "الفرص المجانية طول فترة الاشتراك."
    )


# ─────────────────────────── مسار Telegram Stars ───────────────────────────

async def subscribe_via_stars(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    professional = await asyncio.to_thread(
        _require_registered_professional, update.effective_user.id
    )
    if not professional:
        await query.edit_message_text("لازم تسجّل كفني أولاً عبر /register.")
        return

    sar, stars, days = await asyncio.to_thread(_current_prices)

    payment_id = await asyncio.to_thread(
        db.create_pending_payment,
        professional["id"], "stars", None, f"{stars} XTR",
    )

    await context.bot.send_invoice(
        chat_id=update.effective_chat.id,
        title="اشتراك بوت فني",
        description=f"اشتراك شهري ({days} يوم) لتظهر بنتائج البحث بدون حدود.",
        payload=f"{STARS_PAYLOAD_PREFIX}{professional['id']}:{payment_id}",
        provider_token="",  # لازم يكون فاضي لمدفوعات Stars تحديدًا
        currency="XTR",
        prices=[LabeledPrice("اشتراك شهري", stars)],
    )


async def stars_precheckout(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # تلغرام يطلب تأكيد أخير قبل إتمام الدفع — لازم نرد خلال ثوانٍ قليلة
    await update.pre_checkout_query.answer(ok=True)


async def stars_successful_payment(update: Update, context: ContextTypes.DEFAULT_TYPE):
    payment = update.message.successful_payment
    payload = payment.invoice_payload  # الشكل: sub_stars:<professional_id>:<payment_id>

    try:
        _, professional_id_str, payment_id_str = payload.split(":")
        professional_id = int(professional_id_str)
        payment_id = int(payment_id_str)
    except (ValueError, AttributeError):
        await update.message.reply_text(
            "تم استلام الدفع لكن صار خطأ بمطابقة الطلب. تواصل مع الدعم رجاءً."
        )
        return

    await asyncio.to_thread(db.mark_payment_paid, payment_id)
    await asyncio.to_thread(
        db.update_payment_external_id, payment_id, payment.telegram_payment_charge_id
    )
    _, _, days = await asyncio.to_thread(_current_prices)
    await asyncio.to_thread(db.activate_subscription, professional_id, days)

    await update.message.reply_text(
        f"✅ تم الدفع وتفعيل اشتراكك لمدة {days} يوم. راح تظهر بنتائج البحث "
        "بدون حدود الفرص المجانية طول فترة الاشتراك."
    )


# ─────────────────────────── تجميع الهاندلرز ───────────────────────────

def build_subscription_handlers() -> list:
    return [
        CommandHandler("subscribe", subscribe_command),
        CallbackQueryHandler(subscribe_command, pattern=f"^{CB_SUBSCRIBE_MENU}$"),
        CallbackQueryHandler(subscribe_via_tap, pattern=f"^{CB_SUBSCRIBE_TAP}$"),
        CallbackQueryHandler(verify_tap_payment, pattern=f"^{CB_TAP_VERIFY_PREFIX}"),
        CallbackQueryHandler(subscribe_via_stars, pattern=f"^{CB_SUBSCRIBE_STARS}$"),
        PreCheckoutQueryHandler(stars_precheckout),
        MessageHandler(filters.SUCCESSFUL_PAYMENT, stars_successful_payment),
    ]
