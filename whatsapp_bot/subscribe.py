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
        api.text(wa_id, f"✅ اشتراكك فعّال حتى {_date(p.get('subscription_expires_at'))} — تظهر لجميع العملاء دون حد.")
        return "menu", {}
    country = p.get("country") or countries.DEFAULT_COUNTRY
    if not countries.tap_available(country):
        api.text(wa_id, "الاشتراك عبر واتساب غير متاح في دولتك حاليًا 🙏 يمكنك الاشتراك بنجوم تلغرام عن طريق بوت «فنّي»: "
                        "https://t.me/FanniServiceBot?start=subscribe")
        return "menu", {}
    sar, days = _prices()
    db.supersede_pending_payments(p["id"], "tap")
    payment_id = db.create_pending_payment(p["id"], "tap", None, f"{sar:.2f} SAR")
    try:
        charge = tap_client.create_charge(sar, p["full_name"], p["id"])
    except tap_client.TapNotConfigured:
        api.text(wa_id, "⚠️ الدفع غير متاح حاليًا — حاول بعد قليل أو تواصل مع الإدارة.")
        return "menu", {}
    except Exception:  # noqa: BLE001
        log.exception("tap charge failed")
        api.text(wa_id, "⚠️ حدث خطأ في بوابة الدفع. حاول مرة أخرى بعد قليل.")
        return "menu", {}
    db.update_payment_external_id(payment_id, charge["id"])
    api.cta_url(
        wa_id,
        f"💳 اشتراك شهري ({days} يومًا) — {sar:.0f} ريال\n"
        "تظهر لجميع العملاء دون حدود.\n\n"
        "ادفع بمدى أو فيزا أو آبل باي من الزر أدناه، وبعد إتمام الدفع عُد إلى هنا واكتب «دفعت» ✅",
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
    api.text(wa_id, f"✅ تم تفعيل اشتراكك في «فنّي» — {days} يومًا (حتى {_date(expires)}).\n"
                    "من الآن ستظهر لجميع العملاء الذين يبحثون عن خدمتك دون حد 👌")
    return True


def not_paid_yet(api, wa_id):
    api.text(wa_id, "لم يصلنا تأكيد الدفع بعد ⏳ إذا كنت قد دفعت فعلًا، فانتظر دقيقة ثم اكتب «دفعت» مرة أخرى.")


def details(api, wa_id, p):
    """زر «التفاصيل» بقوالب «خدمة»: حالة الحساب + خيار الاشتراك + إيقاف الإشعارات."""
    db.mark_notifications_responded(p["id"])
    limit = int(db.get_setting("free_contacts_limit", str(db.FREE_CONTACTS_LIMIT))) + (p.get("bonus_contacts") or 0)
    used = p.get("free_contacts_used") or 0
    if p.get("is_subscribed"):
        line = f"✅ اشتراكك فعّال حتى {_date(p.get('subscription_expires_at'))}، ورقمك يظهر لجميع العملاء."
        buttons = [("m:search", "🔍 ابحث عن فني")]
    else:
        sar, days = _prices()
        line = (f"📊 فرص التواصل المجانية: استُخدمت {used} من {limit}."
                + ("\n⚠️ رقمك لا يظهر حاليًا في نتائج البحث." if used >= limit else "")
                + f"\n\n💳 الاشتراك الشهري ({days} يومًا) بـ {sar:.0f} ريال يُظهر رقمك لجميع العملاء دون حد.")
        buttons = [("R:sub", "💳 اشترك الآن"), ("R:mute", "🔕 إيقاف الإشعارات")]
    api.buttons(wa_id, f"حسابك في «فنّي» 👷 {p.get('full_name', '')}\n🛠️ {p.get('profession_name', '')}\n\n{line}", buttons)
    return "menu", {}
