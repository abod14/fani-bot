# تنبيهات الفني بتلغرام (مجانية) بعد كل عميل يضغط «تواصل» معه — طلب المالك:
#   • عداد: «عميل ضغط تواصل معك — استخدمت 2 من 3 (باقي 1)»
#   • لحظة ما تخلص فرصه: «خلصت فرصك — اشترك عشان ترجع تظهر».
#
# يُستدعى بعد كل تواصل جديد ينحسب (db.register_contact) من أي مكان: بحث تلغرام، بحث
# واتساب، أو رابط /c/ بلوحة التحكم. يوصل مرة وحدة بس — بالضبط لما يوصل العداد للحد.
# الإرسال عبر بوت تلغرام (مجاني). فني واتساب غير مربوط بتلغرام ما نقدر نراسله مجانًا،
# فيشوف التنبيه بشاشة «🛠️ أنا فني» بواتساب بدلها.

import asyncio
import logging
import threading

import db
import i18n

log = logging.getLogger("fani.limit")


def contact_counter(professional_id: int) -> dict | None:
    """بعد كل تواصل جديد: (used, limit) للفني المربوط بتلغرام وغير المشترك — لعداد الفرص."""
    p = db.get_professional_by_id(professional_id)
    if not p or p.get("is_subscribed") or p.get("status") != db.STATUS_ACTIVE:
        return None
    if not (p.get("telegram_user_id") or 0) > 0:
        return None
    limit = int(db.get_setting("free_contacts_limit", str(db.FREE_CONTACTS_LIMIT))) + (p.get("bonus_contacts") or 0)
    used = p.get("free_contacts_used") or 0
    if used > limit:
        return None
    p["_limit"], p["_used"] = limit, used
    return p


def just_exhausted(professional_id: int) -> dict | None:
    p = db.get_professional_by_id(professional_id)
    if not p or p.get("is_subscribed") or p.get("status") != db.STATUS_ACTIVE:
        return None
    limit = int(db.get_setting("free_contacts_limit", str(db.FREE_CONTACTS_LIMIT))) + (p.get("bonus_contacts") or 0)
    if (p.get("free_contacts_used") or 0) != limit:      # بالضبط وصل الحد الحين (مو قبل ولا بعد)
        return None
    if not (p.get("telegram_user_id") or 0) > 0:
        return None
    p["_limit"] = limit
    return p


def notify_if_exhausted_async(professional_id: int):
    threading.Thread(target=_run, args=(professional_id,), daemon=True).start()


def _run(professional_id: int):
    try:
        p = contact_counter(professional_id)
        if not p:
            return
        from telegram import Bot, InlineKeyboardButton, InlineKeyboardMarkup

        import config
        from handlers.subscription import CB_SUBSCRIBE_MENU

        lang = db.get_user_language(p["telegram_user_id"])

        exhausted = p["_used"] >= p["_limit"]
        if exhausted:
            text = i18n.t("free_contacts_exhausted", lang, limit=p["_limit"])
        else:
            text = i18n.t("contact_counter_notice", lang, used=p["_used"], limit=p["_limit"],
                          left=p["_limit"] - p["_used"])
        markup = InlineKeyboardMarkup([[InlineKeyboardButton(
            i18n.t("srch_missed_nudge_subscribe_btn", lang), callback_data=CB_SUBSCRIBE_MENU)]])

        async def send():
            async with Bot(config.BOT_TOKEN) as bot:
                await bot.send_message(chat_id=p["telegram_user_id"], text=text, reply_markup=markup)

        asyncio.run(send())
    except Exception:  # noqa: BLE001 — تنبيه إضافي؛ ما يوقف التواصل
        log.exception("limit notice failed")
