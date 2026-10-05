# إشعارات الفنيين اللي خلصت فرصهم المجانية (طلب المالك):
#
# تلغرام (مجاني) — لأي فني عنده حساب تلغرام وما أوقفها:
#   • لحظة ما تخلص الفرص: رسالة + زر الاشتراك + زر «إيقاف الإشعارات».
#   • كل ما بحث عميل عن مهنته بمنطقته وهو مخفي: نفس الشي — بدون حد.
# واتساب (رسائل قوالب مدفوعة) — لكل فني عنده رقم واتساب (حتى لو عنده تلغرام، لأن قليل يفتح
# تلغرام)، وما أوقفها:
#   • لحظة ما تخلص الفرص: إشعار واحد.
#   • «فيه عميل يدوّر عليك»: 3 بالشهر الأول (من أول إشعار)، بعدها 1 بالشهر، لين سنة ثم يوقف.
#     الأدمن يقدر يعيد التشغيل من لوحة التحكم.
#   • لو الفني راسل البوت آخر 24 ساعة: رسالة عادية مجانية بدل القالب.
# كل إشعار ينسجل بـ notify_log، وأي تفاعل من الفني يعلّمها «مستجابة».

import asyncio
import logging
import threading
from datetime import datetime, timedelta, timezone

import config
import contact_links
import db
import i18n

log = logging.getLogger("fani.nudges")

WA_FIRST_MONTH_MAX = 3
WA_LATER_MONTH_MAX = 1
WA_MONTH = timedelta(days=30)
WA_MAX_DAYS = 365
WA_FREE_WINDOW = timedelta(hours=23)     # نافذة واتساب المجانية 24 ساعة (نترك هامش ساعة)
SUB_PAYLOAD = "R:sub"                    # زر «اشترك الآن» بواتساب
MUTE_PAYLOAD = "R:mute"                  # زر «إيقاف الإشعارات» بواتساب
TG_MUTE_CB = "ntf_off"                   # زر «إيقاف الإشعارات» بتلغرام


def _now():
    return datetime.now(timezone.utc)


def _parse(ts):
    try:
        return datetime.fromisoformat(ts) if ts else None
    except ValueError:
        return None


def _tg_ok(p) -> bool:
    return (p.get("telegram_user_id") or 0) > 0 and not p.get("tg_notify_off")


def wa_number(p) -> str | None:
    if p.get("wa_id"):
        return p["wa_id"]
    if p.get("whatsapp_number") and p.get("has_whatsapp", 1):
        d = contact_links.intl_digits(p["whatsapp_number"], p.get("country"))
        return d or None
    return None


def _wa_ok(p) -> bool:
    return bool(wa_number(p)) and not p.get("wa_notify_off")


# ─────────────────────────── الإرسال ───────────────────────────

def _send_tg(p, text_key, **kw) -> bool:
    try:
        from telegram import Bot, InlineKeyboardButton, InlineKeyboardMarkup

        from handlers.subscription import CB_SUBSCRIBE_MENU

        lang = db.get_user_language(p["telegram_user_id"])
        markup = InlineKeyboardMarkup([
            [InlineKeyboardButton(i18n.t("srch_missed_nudge_subscribe_btn", lang), callback_data=CB_SUBSCRIBE_MENU)],
            [InlineKeyboardButton(i18n.t("notify_off_btn", lang), callback_data=TG_MUTE_CB)],
        ])

        async def go():
            async with Bot(config.BOT_TOKEN) as bot:
                await bot.send_message(chat_id=p["telegram_user_id"], text=i18n.t(text_key, lang, **kw),
                                       reply_markup=markup)

        asyncio.run(go())
        return True
    except Exception:  # noqa: BLE001 — حاظر البوت أو غيره
        log.info("telegram nudge failed for %s", p.get("id"), exc_info=True)
        return False


def _wa_api():
    from whatsapp_bot.api import WhatsAppAPI
    return WhatsAppAPI()


def _in_free_window(wa_id: str) -> bool:
    with db.get_conn() as conn:
        try:
            r = conn.execute("SELECT updated_at FROM wa_sessions WHERE wa_id = ?", (wa_id,)).fetchone()
        except Exception:  # noqa: BLE001 — جدول الجلسات ما انشأ بعد
            return False
    t = _parse(r["updated_at"]) if r else None
    return bool(t and _now() - t < WA_FREE_WINDOW)


def _send_wa(p, free_text: str, template: str, params: list[str]) -> tuple[bool, bool]:
    """يرجّع (نجح؟، مدفوع؟)."""
    to = wa_number(p)
    if not to:
        return False, False
    api = _wa_api()
    if _in_free_window(to):
        r = api.buttons(to, free_text, [(SUB_PAYLOAD, "💳 اشترك الآن"), (MUTE_PAYLOAD, "🔕 إيقاف الإشعارات")])
        return bool(r is not None and getattr(r, "status_code", 500) < 400), False
    r = api.template(to, template, params, button_payloads=[SUB_PAYLOAD, MUTE_PAYLOAD])
    return bool(r is not None and getattr(r, "status_code", 500) < 400), True


def _start_wa_clock(p):
    with db.get_conn() as conn:
        conn.execute("UPDATE professionals SET nudge_first_at = COALESCE(nudge_first_at, ?) WHERE id = ?",
                     (_now().isoformat(), p["id"]))


# ─────────────────────────── خلصت الفرص ───────────────────────────

def notify_exhausted(professional_id: int, kind: str = "exhausted") -> bool:
    p = db.get_professional_by_id(professional_id)
    if not p:
        return False
    limit = int(db.get_setting("free_contacts_limit", str(db.FREE_CONTACTS_LIMIT))) + (p.get("bonus_contacts") or 0)
    manual = kind == "manual"
    any_ok = False
    if (p.get("telegram_user_id") or 0) > 0 and (manual or not p.get("tg_notify_off")):
        ok = _send_tg(p, "free_contacts_exhausted", limit=limit)
        db.log_notification(p["id"], kind, "telegram", False, ok)
        any_ok |= ok
    if wa_number(p) and (manual or not p.get("wa_notify_off")):
        first = (p.get("full_name") or "").split()[0] if p.get("full_name") else ""
        ok, paid = _send_wa(
            p,
            f"⚠️ يا {first}، انتهت فرصك المجانية للتواصل مع العملاء في «فنّي».\n\nجدد اشتراكك من هنا 👇",
            config.WA_TPL_FREE_ENDED, [first or "صديقنا"],
        )
        db.log_notification(p["id"], kind, "whatsapp", paid, ok)
        if ok:
            _start_wa_clock(p)
        any_ok |= ok
    return any_ok


def notify_exhausted_async(professional_id: int):
    threading.Thread(target=notify_exhausted, args=(professional_id,), daemon=True).start()


# ─────────────────────────── فيه عميل يدوّر عليك ───────────────────────────

def wa_schedule_state(p) -> dict:
    """{allowed: bool, month: رقم الشهر (0 = الأول), stopped: مرت سنة}."""
    first = _parse(p.get("nudge_first_at"))
    if not first:
        return {"allowed": True, "month": 0, "stopped": False}
    age = _now() - first
    if age > timedelta(days=WA_MAX_DAYS):
        return {"allowed": False, "month": age // WA_MONTH, "stopped": True}
    month = age // WA_MONTH
    window_start = first + month * WA_MONTH
    sent = db.count_wa_notifications_since(p["id"], window_start.isoformat(), "missed")
    cap = WA_FIRST_MONTH_MAX if month == 0 else WA_LATER_MONTH_MAX
    return {"allowed": sent < cap, "month": month, "stopped": False}


def notify_missed(profession_id, profession_name, city, neighborhood, district_id, city_id):
    try:
        missed = db.find_subscription_missed_professionals(profession_id, city, neighborhood, district_id, city_id)
    except Exception:  # noqa: BLE001
        log.exception("find missed failed")
        return
    nb = neighborhood if isinstance(neighborhood, str) else ("، ".join(neighborhood) if neighborhood else "")
    suffix = f" — {nb}" if nb else ""
    for p in missed:
        try:
            if _tg_ok(p):
                ok = _send_tg(p, "srch_missed_nudge", profession=profession_name, city=city, district_suffix=suffix)
                db.log_notification(p["id"], "missed", "telegram", False, ok)
            if _wa_ok(p) and wa_schedule_state(p)["allowed"]:
                place = f"{city}{suffix}"
                ok, paid = _send_wa(
                    p,
                    f"🔔 فيه عميل الحين يدوّر على «{profession_name}» في {place}، لكن رقمك ما ظهر له لأنك خلّصت فرصك المجانية.\n\n"
                    "اشترك عشان تظهر لكل العملاء اللي يبحثون عن خدمتك 👇",
                    config.WA_TPL_CUSTOMER_SEARCHING, [profession_name, place],
                )
                db.log_notification(p["id"], "missed", "whatsapp", paid, ok)
                if ok:
                    _start_wa_clock(p)
        except Exception:  # noqa: BLE001 — فني واحد ما يوقف الباقين
            log.exception("nudge failed for %s", p.get("id"))
    if missed:
        db.mark_search_nudge_sent([p["id"] for p in missed])


def notify_missed_async(*args):
    threading.Thread(target=notify_missed, args=args, daemon=True).start()


# ─────────────────────────── يدوي من لوحة التحكم ───────────────────────────

def notify_manual(professional_id: int) -> bool:
    """إشعار يدوي (زر بلوحة التحكم) — «خلصت فرصك» + زر الاشتراك، على تلغرام وواتساب، حتى لو موقفها."""
    return notify_exhausted(professional_id, kind="manual")
