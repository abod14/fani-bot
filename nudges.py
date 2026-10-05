# إشعارات الفنيين اللي خلصت فرصهم المجانية (طلب المالك):
#
# تلغرام (مجاني) — لأي فني عنده حساب تلغرام وما أوقفها:
#   • لحظة ما تخلص الفرص: رسالة + زر الاشتراك + زر «إيقاف الإشعارات».
#   • كل ما بحث عميل عن مهنته بمنطقته وهو مخفي: نفس الشي — بدون حد.
# واتساب (رسائل قوالب مدفوعة) — لكل فني عنده رقم واتساب (حتى لو عنده تلغرام، لأن قليل يفتح
# تلغرام)، وما أوقفها:
#   • لحظة ما تخلص الفرص: إشعار واحد.
#   • «فيه عميل يدوّر عليك»: لحظيًا بالشهر الأول (3 بالكثير، من أول إشعار).
#   • من الشهر الثاني لين السنة: ملخص شهري واحد «X عميل بحثوا عن خدمتك ولم يظهر رقمك» (قالب
#     «خدمة» — أرخص)، ويُرسل فقط لو فيه بحث فعلًا. بعد سنة يوقف، والأدمن يقدر يعيد التشغيل.
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
DETAILS_PAYLOAD = "R:details"            # زر «التفاصيل» بقوالب «خدمة» (بلا ذكر للاشتراك)
# أزرار كل قالب (لازم تطابق القالب المسجّل عند ميتا بالعدد والترتيب)
TEMPLATE_BUTTONS = {"fanni_account_update": [DETAILS_PAYLOAD], "fanni_monthly_summary": [DETAILS_PAYLOAD]}
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
    # نجرّب القوالب بالترتيب (الأرخص «خدمة» أول) — المرفوض/قيد المراجعة يرجع خطأ مجاني
    for name in ([template] if isinstance(template, str) else template):
        name = name.strip()
        r = api.template(to, name, params, button_payloads=TEMPLATE_BUTTONS.get(name, [SUB_PAYLOAD, MUTE_PAYLOAD]))
        if r is not None and getattr(r, "status_code", 500) < 400:
            return True, True
    return False, True


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
    if month >= 1:
        # بعد الشهر الأول: ما فيه إشعار لحظي — يوصله ملخص شهري بدلها (run_monthly_summaries)
        return {"allowed": False, "month": month, "stopped": False}
    sent = db.count_wa_notifications_since(p["id"], first.isoformat(), "missed")
    return {"allowed": sent < WA_FIRST_MONTH_MAX, "month": month, "stopped": False}


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
                    f"🔔 يبحث عميل الآن عن «{profession_name}» في {place}، لكن رقمك لم يظهر له لأن فرصك المجانية انتهت.\n\n"
                    "اشترك لتظهر لجميع العملاء الذين يبحثون عن خدمتك 👇",
                    config.WA_TPL_CUSTOMER_SEARCHING, [profession_name, place],
                )
                db.log_notification(p["id"], "missed", "whatsapp", paid, ok)
                if ok:
                    _start_wa_clock(p)
        except Exception:  # noqa: BLE001 — فني واحد ما يوقف الباقين
            log.exception("nudge failed for %s", p.get("id"))
    if missed:
        db.mark_search_nudge_sent([p["id"] for p in missed])
        db.record_missed_searches([p["id"] for p in missed])


def notify_missed_async(*args):
    threading.Thread(target=notify_missed, args=args, daemon=True).start()


# ─────────────────────────── الملخص الشهري (من الشهر الثاني لين سنة) ───────────────────────────

def run_monthly_summaries() -> int:
    """يُستدعى كل ساعة من خادم واتساب. لكل فني بدأت دورته: لو كمل شهر جديد ولسه ما وصله
    ملخص هذا الشهر، وفيه عملاء بحثوا عنه بالشهر اللي فات → ملخص واحد. يرجّع عدد المرسَل."""
    sent_n = 0
    now = _now()
    for p in db.summary_candidates():
        try:
            if not _wa_ok(p):
                continue
            first = _parse(p.get("nudge_first_at"))
            if not first:
                continue
            age = now - first
            if age > timedelta(days=WA_MAX_DAYS) or age < WA_MONTH:
                continue
            month = age // WA_MONTH
            this_start = first + month * WA_MONTH
            if db.count_wa_notifications_since(p["id"], this_start.isoformat(), "summary"):
                continue      # وصله ملخص هذا الشهر
            prev_start = first + (month - 1) * WA_MONTH
            count = db.count_missed_searches(p["id"], prev_start.isoformat(), this_start.isoformat())
            if count <= 0:
                continue      # ما أحد بحث عنه — ما نرسل شي (توفير)
            prof = p.get("profession_name") or "خدمتك"
            ok, paid = _send_wa(
                p,
                f"📊 ملخص حسابك الشهري في «فنّي»: عدد العملاء الذين بحثوا عن «{prof}» في منطقتك "
                f"خلال الشهر الماضي ولم يظهر لهم رقمك: {count}.\n\nلتظهر لهم، جدّد اشتراكك 👇",
                config.WA_TPL_MONTHLY_SUMMARY, [str(count), prof],
            )
            db.log_notification(p["id"], "summary", "whatsapp", paid, ok)
            sent_n += int(ok)
        except Exception:  # noqa: BLE001
            log.exception("summary failed for %s", p.get("id"))
    return sent_n


def start_summary_loop(interval_seconds: int = 3600):
    def loop():
        import time
        while True:
            try:
                n = run_monthly_summaries()
                if n:
                    log.info("monthly summaries sent: %s", n)
            except Exception:  # noqa: BLE001
                log.exception("summary loop error")
            time.sleep(interval_seconds)
    threading.Thread(target=loop, daemon=True, name="monthly-summaries").start()


# ─────────────────────────── يدوي من لوحة التحكم ───────────────────────────

def notify_manual(professional_id: int) -> bool:
    """إشعار يدوي (زر بلوحة التحكم) — «خلصت فرصك» + زر الاشتراك، على تلغرام وواتساب، حتى لو موقفها."""
    return notify_exhausted(professional_id, kind="manual")
