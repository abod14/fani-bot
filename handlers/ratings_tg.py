# التقييم في تلغرام (نفس منطق واتساب في ratings.py): إرسال الأسئلة المستحقة + أزرارها.

import asyncio
import logging

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import CallbackQueryHandler, ContextTypes

import db
import i18n
import ratings

log = logging.getLogger("fani.ratings")


def _lang(uid: int) -> str:
    try:
        return db.get_user_language(uid) or "ar"
    except Exception:
        return "ar"


def _stars_kb(req_id: int, lang: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[InlineKeyboardButton(f"{stars} {i18n.t(f'rt_s{n}', lang)}", callback_data=f"rs:{req_id}:{n}")]
                                 for n, stars, _ in ratings.STARS])


async def send_due_job(context: ContextTypes.DEFAULT_TYPE):
    batches = await asyncio.to_thread(ratings._due_batches, "tg")
    for cust, reqs in batches:
        ids = [r["id"] for r in reqs]
        lang = await asyncio.to_thread(_lang, cust)
        when = i18n.t("rt_today" if ratings.when_word(reqs[0]["contacted_at"], cust) == "اليوم" else "rt_yesterday", lang)
        try:
            if len(reqs) == 1:
                name, prof = await asyncio.to_thread(ratings.pro_label, reqs[0]["professional_id"])
                kb = InlineKeyboardMarkup([[InlineKeyboardButton(i18n.t("rt_yes", lang), callback_data=f"rt:y:{ids[0]}"),
                                            InlineKeyboardButton(i18n.t("rt_no", lang), callback_data=f"rt:n:{ids[0]}")]])
                await context.bot.send_message(cust, i18n.t("rt_ask_one", lang, when=when, name=name, prof=prof), reply_markup=kb)
            else:
                rows = []
                for r in reqs[:9]:
                    name, prof = await asyncio.to_thread(ratings.pro_label, r["professional_id"])
                    rows.append([InlineKeyboardButton(f"{name} — {prof}", callback_data=f"rt:y:{r['id']}")])
                rows.append([InlineKeyboardButton(i18n.t("rt_none", lang), callback_data=f"rt:n:{ids[0]}")])
                await context.bot.send_message(cust, i18n.t("rt_ask_many", lang, when=when), reply_markup=InlineKeyboardMarkup(rows))
            await asyncio.to_thread(ratings._mark, ids, "sent")
        except Exception:
            log.exception("rating TG send failed")
            await asyncio.to_thread(ratings._mark, ids, "failed")


async def on_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    uid = update.effective_user.id
    lang = await asyncio.to_thread(_lang, uid)
    parts = (q.data or "").split(":")
    head = parts[0]
    try:
        req = await asyncio.to_thread(ratings.get_request, int(parts[2] if head == "rt" else parts[1]), uid)
    except (ValueError, IndexError):
        req = None

    async def say(text, kb=None):
        try:
            await q.edit_message_text(text, reply_markup=kb)
        except Exception:
            await q.message.reply_text(text, reply_markup=kb)

    if not req:
        return await say(i18n.t("rt_expired", lang))
    if head == "rt" and parts[1] == "n":
        return await say(i18n.t("rt_no_thanks", lang))
    pid = req["professional_id"]
    if await asyncio.to_thread(ratings.already_rated, pid, uid):
        return await say(i18n.t("rt_already", lang))
    if head == "rt":
        name, _ = await asyncio.to_thread(ratings.pro_label, pid)
        return await say(i18n.t("rt_how", lang, name=name), _stars_kb(req["id"], lang))
    await asyncio.to_thread(ratings.save_rating, pid, uid, int(parts[2]))
    await say(i18n.t("rt_thanks", lang))


def build_rating_handlers() -> list:
    return [CallbackQueryHandler(on_callback, pattern=r"^r[ts]:")]
