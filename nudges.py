# إشعارات الفنيين اللي خلصت فرصهم المجانية (طلب المالك):
#
# تلغرام (مجاني):
#   • لحظة ما تخلص الفرص: رسالة + زر الاشتراك (مرة وحدة).
#   • كل ما بحث عميل عن مهنته بمنطقته وهو مخفي: رسالة + زر الاشتراك — بدون حد.
# واتساب (للفني المسجّل من واتساب وغير مربوط بتلغرام — رسائل قوالب مدفوعة):
#   • لحظة ما تخلص الفرص: قالب «خلصت فرصك» + زر اشترك (مرة وحدة).
#   • كل بحث عنه: قالب «فيه عميل يدوّر عليك» — 5 بالشهر بالكثير، بعدها يوقف لين يكمل شهر من
#     بداية الدورة ويرجع. ويوقف نهائيًا بعد سنة من أول إشعار (يطلع بلوحة التحكم).
#   • لو الفني راسل البوت آخر 24 ساعة: نرسل رسالة عادية (مجانية) بدل القالب.
# كل إشعار ينسجل بـ notify_log، وأي تفاعل من الفني (ضغط اشتراك / رسالة / اشتراك) يعلّمها «مستجابة».

import asyncio
import logging
import threading
from datetime import datetime, timedelta, timezone

import config
import db
import i18n

log = logging.getLogger("fani.nudges")

WA_MISSED_PER_CYCLE = 5
WA_CYCLE_DAYS = 30
WA_MAX_DAYS = 365
WA_FREE_WINDOW = timedelta(hours=23)     # نافذة واتساب المجانية 24 ساعة (نترك هامش ساعة)
SUB_PAYLOAD = "R:sub"                    # زر «اشترك» بواتساب يرجع هذا للبوت


def _now():
    return datetime.now(timezone.utc)


def _parse(ts):
    try:
        return datetime.fromisoformat(ts) if ts else None
    except ValueError:
        return None


def _is_tg(p) -> bool:
    return (p.get("telegram_user_id") or 0) > 0


def _wa_number(p) -> str | None:
    if p.get("wa_id"):
        return p["wa_id"]
    return None


# ─────────────────────────── الإرسال ───────────────────────────

def _send_tg(p, text_key, **kw) -> bool:
    try:
        from telegram import Bot, InlineKeyboardButton, InlineKeyboardMarkup

        from handlers.subscription import CB_SUBSCRIBE_MENU

        lang = db.get_user_language(p["telegram_user_id"])
        markup = InlineKeyboardMarkup([[InlineKeyboardButton(
            i18n.t("srch_missed_nudge_subscribe_btn", lang), callback_data=CB_SUBSCRIBE_MENU)]])

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


def _send_wa(p, kind: str, free_text: str, template: str, params: list[str]) -> tuple[bool, bool]:
    """يرجّع (نجح؟، مدفوع؟)."""
    wa_id = _wa_number(p)
    if not wa_id:
        return False, False
    api = _wa_api()
    if _in_free_window(wa_id):
        r = api.buttons(wa_id, free_text, [(SUB_PAYLOAD, "💳 اشترك الآن")])
        return bool(r is not None and getattr(r, "status_code", 500) < 400), False
    r = api.template(wa_id, template, params, button_payload=SUB_PAYLOAD)
    return bool(r is not None and getattr(r, "status_code", 500) < 400), True


# ─────────────────────────── خلصت الفرص ───────────────────────────

def notify_exhausted(professional_id: int, kind: str = "exhausted") -> bool:
    p = db.get_professional_by_id(professional_id)
    if not p:
        return False
    limit = int(db.get_setting("free_contacts_limit", str(db.FREE_CONTACTS_LIMIT))) + (p.get("bonus_contacts") or 0)
    if _is_tg(p):
        ok = _send_tg(p, "free_contacts_exhausted", limit=limit)
        db.log_notification(p["id"], kind, "telegram", False, ok)
        return ok
    first = (p["full_name"] or "").split()[0] if p.get("full_name") else ""
    ok, paid = _send_wa(
        p, kind,
        f"⚠️ خلصت فرصك المجانية ({limit}) في «فنّي» يا {first} — رقمك ما يظهر للعملاء الحين.\n\n"
        "اشترك عشان ترجع تظهر وتستقبل عملاء بدون حدود 👇",
        config.WA_TPL_FREE_ENDED, [first or "صديقنا"],
    )
    db.log_notification(p["id"], kind, "whatsapp", paid, ok)
    if ok:
        with db.get_conn() as conn:
            conn.execute("UPDATE professionals SET nudge_first_at = COALESCE(nudge_first_at, ?) WHERE id = ?",
                         (_now().isoformat(), p["id"]))
    return ok


def notify_exhausted_async(professional_id: int):
    threading.Thread(target=notify_exhausted, args=(professional_id,), daemon=True).start()


# ─────────────────────────── فيه عميل يدوّر عليك ───────────────────────────

def _wa_cycle_allows(p) -> bool:
    """5 إشعارات بالدورة (شهر)، وتوقف نهائي بعد سنة من أول إشعار."""
    now = _now()
    first = _parse(p.get("nudge_first_at"))
    if first and now - first > timedelta(days=WA_MAX_DAYS):
        return False
    start = _parse(p.get("wa_nudge_cycle_start"))
    if not start or now - start >= timedelta(days=WA_CYCLE_DAYS):
        with db.get_conn() as conn:
            conn.execute("UPDATE professionals SET wa_nudge_cycle_start = ?, wa_nudge_cycle_count = 0 WHERE id = ?",
                         (now.isoformat(), p["id"]))
        return True
    return (p.get("wa_nudge_cycle_count") or 0) < WA_MISSED_PER_CYCLE


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
            if _is_tg(p):
                ok = _send_tg(p, "srch_missed_nudge", profession=profession_name, city=city, district_suffix=suffix)
                db.log_notification(p["id"], "missed", "telegram", False, ok)
                continue
            if not _wa_number(p) or not _wa_cycle_allows(p):
                continue
            place = f"{city}{suffix}"
            ok, paid = _send_wa(
                p, "missed",
                f"🔔 فيه عميل الحين يدوّر على «{profession_name}» في {place}، لكن رقمك ما ظهر له لأنك خلّصت فرصك المجانية.\n\n"
                "اشترك عشان تظهر لكل العملاء اللي يبحثون عن خدمتك 👇",
                config.WA_TPL_CUSTOMER_SEARCHING, [profession_name, place],
            )
            db.log_notification(p["id"], "missed", "whatsapp", paid, ok)
            if ok:
                with db.get_conn() as conn:
                    conn.execute(
                        "UPDATE professionals SET wa_nudge_cycle_count = wa_nudge_cycle_count + 1, "
                        "nudge_first_at = COALESCE(nudge_first_at, ?) WHERE id = ?",
                        (_now().isoformat(), p["id"]),
                    )
        except Exception:  # noqa: BLE001 — فني واحد ما يوقف الباقين
            log.exception("nudge failed for %s", p.get("id"))
    if missed:
        db.mark_search_nudge_sent([p["id"] for p in missed])


def notify_missed_async(*args):
    threading.Thread(target=notify_missed, args=args, daemon=True).start()


# ─────────────────────────── يدوي من لوحة التحكم ───────────────────────────

def notify_manual(professional_id: int) -> bool:
    """إشعار يدوي (زر بلوحة التحكم) — نفس رسالة «خلصت فرصك» مع زر الاشتراك، بدون حدود الدورة."""
    return notify_exhausted(professional_id, kind="manual")
