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
from whatsapp_bot.lang import tr

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
        api.text(wa_id, tr("✅ اشتراكك فعّال حتى {date} — تظهر لجميع العملاء دون حد.", date=_date(p.get("subscription_expires_at"))))
        return "menu", {}
    country = p.get("country") or countries.DEFAULT_COUNTRY
    if not countries.tap_available(country):
        api.text(wa_id, tr("الاشتراك عبر واتساب غير متاح في دولتك حاليًا 🙏 يمكنك الاشتراك بنجوم تلغرام عن طريق بوت «فنّي»: {url}",
                           url="https://t.me/FanniServiceBot?start=subscribe"))
        return "menu", {}
    sar, days = _prices()
    db.supersede_pending_payments(p["id"], "tap")
    payment_id = db.create_pending_payment(p["id"], "tap", None, f"{sar:.2f} SAR")
    try:
        charge = tap_client.create_charge(sar, p["full_name"], p["id"])
    except tap_client.TapNotConfigured:
        api.text(wa_id, tr("⚠️ الدفع غير متاح حاليًا — حاول بعد قليل أو تواصل مع الإدارة."))
        return "menu", {}
    except Exception:  # noqa: BLE001
        log.exception("tap charge failed")
        api.text(wa_id, tr("⚠️ حدث خطأ في بوابة الدفع. حاول مرة أخرى بعد قليل."))
        return "menu", {}
    db.update_payment_external_id(payment_id, charge["id"])
    api.cta_url(
        wa_id,
        tr("💳 اشتراك شهري ({days} يومًا) — {price} ريال\n"
           "تظهر لجميع العملاء دون حدود.\n\n"
           "ادفع بمدى أو فيزا أو آبل باي من الزر أدناه، وبعد إتمام الدفع عُد إلى هنا واكتب «دفعت» ✅",
           days=days, price=f"{sar:.0f}"),
        tr("ادفع الآن"), charge["redirect_url"],
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
    api.text(wa_id, tr("✅ تم تفعيل اشتراكك في «فنّي» — {days} يومًا (حتى {date}).\n"
                       "من الآن ستظهر لجميع العملاء الذين يبحثون عن خدمتك دون حد 👌", days=days, date=_date(expires)))
    return True


def not_paid_yet(api, wa_id):
    api.text(wa_id, tr("لم يصلنا تأكيد الدفع بعد ⏳ إذا كنت قد دفعت فعلًا، فانتظر دقيقة ثم اكتب «دفعت» مرة أخرى."))


def details(api, wa_id, p):
    """زر «التفاصيل» بقوالب «خدمة»: حالة الحساب + خيار الاشتراك + إيقاف الإشعارات."""
    db.mark_notifications_responded(p["id"])
    limit = int(db.get_setting("free_contacts_limit", str(db.FREE_CONTACTS_LIMIT))) + (p.get("bonus_contacts") or 0)
    used = p.get("free_contacts_used") or 0
    if p.get("is_subscribed"):
        line = tr("✅ اشتراكك فعّال حتى {date}، ورقمك يظهر لجميع العملاء.", date=_date(p.get("subscription_expires_at")))
        buttons = [("m:search", tr("🔍 ابحث عن فني"))]
    else:
        sar, days = _prices()
        line = (tr("📊 فرص التواصل المجانية: استُخدمت {used} من {limit}.", used=used, limit=limit)
                + ("\n" + tr("⚠️ رقمك لا يظهر حاليًا في نتائج البحث.") if used >= limit else "")
                + "\n\n" + tr("💳 الاشتراك الشهري ({days} يومًا) بـ {price} ريال يُظهر رقمك لجميع العملاء دون حد.",
                               days=days, price=f"{sar:.0f}"))
        buttons = [("R:sub", tr("💳 اشترك الآن")), ("R:mute", tr("🔕 إيقاف الإشعارات"))]
    from whatsapp_bot.flow import prof_name
    api.buttons(wa_id, tr("حسابك في «فنّي» 👷 {name}\n🛠️ {pname}\n\n{line}", name=p.get("full_name", ""),
                          pname=prof_name(p.get("profession_id"), p.get("profession_name", "")), line=line), buttons)
    return "menu", {}
