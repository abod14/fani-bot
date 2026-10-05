# الاشتراك من داخل واتساب عبر Tap (مدى/فيزا/آبل باي) — بدون الحاجة لتلغرام.
#
# 1) الفني يضغط «💳 اشترك» (من شاشة «أنا فني» أو من إشعار «خلصت فرصك») → ننشئ عملية دفع
#    بـ Tap ونرسل زر «ادفع الآن» (رسالة وحدة).
# 2) يدفع ويرجع يكتب أي شي (مثل «دفعت») → نتحقق من Tap؛ لو مدفوع: نفعّل الاشتراك ونأكد له.

import logging
from datetime import datetime, timezone

import countries
import db
import tap_client

log = logging.getLogger("fani.wa.sub")

PAID_WORDS = {"دفعت", "تم الدفع", "تم", "خلصت الدفع", "paid", "done"}


def _prices():
    from config import SUBSCRIPTION_DAYS, SUBSCRIPTION_PRICE_SAR
    sar = float(db.get_setting("subscription_price_sar", str(SUBSCRIPTION_PRICE_SAR)))
    days = int(db.get_setting("subscription_days", str(SUBSCRIPTION_DAYS)))
    return sar, days


def _date(iso):
    try:
        return datetime.fromisoformat(iso).astimezone(timezone.utc).strftime("%Y-%m-%d")
    except Exception:  # noqa: BLE001
        return iso or ""


def start(api, wa_id, p):
    db.mark_notifications_responded(p["id"])
    if p.get("is_subscribed"):
        api.text(wa_id, f"✅ اشتراكك فعّال لين {_date(p.get('subscription_expires_at'))} — تظهر لكل العملاء بدون حد.")
        return "menu", {}
    country = p.get("country") or countries.DEFAULT_COUNTRY
    if not countries.tap_available(country):
        api.text(wa_id, "الاشتراك من واتساب غير متاح لدولتك حاليًا 🙏 تقدر تشترك بنجوم تلغرام عن طريق بوت «فنّي»: "
                        "https://t.me/FanniServiceBot?start=subscribe")
        return "menu", {}
    sar, days = _prices()
    payment_id = db.create_pending_payment(p["id"], "tap", None, f"{sar:.2f} SAR")
    try:
        charge = tap_client.create_charge(sar, p["full_name"], p["id"])
    except tap_client.TapNotConfigured:
        api.text(wa_id, "⚠️ الدفع غير متاح حاليًا — حاول بعد شوي أو تواصل مع الإدارة.")
        return "menu", {}
    except Exception:  # noqa: BLE001
        log.exception("tap charge failed")
        api.text(wa_id, "⚠️ صار خطأ مع بوابة الدفع. حاول مرة ثانية بعد شوي.")
        return "menu", {}
    db.update_payment_external_id(payment_id, charge["id"])
    api.cta_url(
        wa_id,
        f"💳 اشتراك شهري ({days} يوم) — {sar:.0f} ريال\n"
        "تظهر لكل العملاء بدون حدود.\n\n"
        "ادفع بمدى أو فيزا أو آبل باي من الزر تحت، وبعد ما تخلص ارجع هنا واكتب «دفعت» ✅",
        "ادفع الآن", charge["redirect_url"],
    )
    return "menu", {}


def check_pending(api, wa_id, p) -> bool:
    """لو عنده دفع معلّق ودفع فعلًا: نفعّل ونأكد. يرجّع True لو فعّلنا (عشان ما نكمل الرد العادي)."""
    pay = db.get_latest_pending_payment(p["id"], "tap")
    if not pay:
        return False
    try:
        status = tap_client.get_charge_status(pay["external_id"])
    except Exception:  # noqa: BLE001
        return False
    if not tap_client.is_paid(status):
        return False
    db.mark_payment_paid(pay["id"])
    _, days = _prices()
    expires = db.activate_subscription(p["id"], days)
    api.text(wa_id, f"✅ تم تفعيل اشتراكك في «فنّي» — {days} يوم (لين {_date(expires)}).\n"
                    "من الحين تظهر لكل العملاء اللي يبحثون عن خدمتك بدون حد 👌")
    return True


def not_paid_yet(api, wa_id):
    api.text(wa_id, "لسه ما وصلنا تأكيد الدفع ⏳ لو دفعت فعلًا انتظر دقيقة واكتب «دفعت» مرة ثانية.")
