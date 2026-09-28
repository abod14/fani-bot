# نقطة تشغيل بوت «فني».
# تشغيل محلي (Polling): python main.py  (بعد تجهيز .env — راجع README.md)
# تشغيل على استضافة مثل Render (Webhook): يتفعّل تلقائيًا لو كان متغير البيئة
# RENDER_EXTERNAL_URL موجود (Render يضبطه تلقائيًا) — لا حاجة لأي إعداد يدوي إضافي.

import asyncio
import logging
import os

from telegram.ext import ApplicationBuilder, CallbackQueryHandler, CommandHandler

import db
import i18n
from config import (
    BOT_TOKEN,
    PROFESSIONS_JSON_PATH,
    SAUDI_CITIES_JSON_PATH,
    SAUDI_DISTRICTS_JSON_PATH,
    SAUDI_REGIONS_JSON_PATH,
)
from handlers.admin import build_admin_handler
from handlers.donation import build_donation_handlers
from handlers.privacy import build_privacy_handlers
from handlers.register import build_register_conversation
from handlers.search import (
    build_search_conversation,
    build_telegram_click_handler,
    build_whatsapp_click_handler,
)
from handlers.start import build_language_handlers, start_command
from handlers.subscription import (
    EXPIRY_CHECK_INTERVAL_SECONDS,
    build_subscription_handlers,
    check_expired_subscriptions,
)
from translations_data import DOMAIN_TRANSLATIONS, PROFESSION_TRANSLATIONS

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)


async def help_command(update, context):
    lang = db.get_user_language(update.effective_user.id)
    await update.message.reply_text(i18n.t("help_text", lang))


async def handle_stale_callback(update, context):
    """يلتقط أي ضغطة على زر قديم يخص محادثة /search أو /register بعد ما انتهت
    مهلتها (conversation_timeout) بسبب تأخّر العميل بالرد — بدون هذا الهاندلر،
    الزر يبقى "يدور" بدون أي رد لأن تلغرام ينتظر answerCallbackQuery ولا أحد
    يرسله. نجاوب فورًا ونرشد العميل يبدأ من جديد بدل ما يحس إن البوت معلّق.

    مُسجَّل عمدًا بعد كل هاندلرز /search و/register الفعلية (بنفس المجموعة
    الافتراضية 0) — فيتلقط بس الضغطات اللي ما قدر أي هاندلر سابق يتعرف عليها،
    ولا يتعارض مع أزرار واتساب/تلغرام (srch_wa:/srch_tg:) اللي تبقى شغالة عمدًا
    حتى بعد انتهاء المحادثة."""
    query = update.callback_query
    lang = await asyncio.to_thread(db.get_user_language, update.effective_user.id)
    await query.answer(i18n.t("stale_session_alert", lang), show_alert=True)
    command = "/search" if query.data.startswith("srch_") else "/register"
    await query.message.reply_text(i18n.t("stale_session_restart", lang, command=command))


def main():
    # بايثون 3.12+ ما عاد يسوي event loop تلقائي بالخيط الرئيسي (Main Thread) —
    # وهذا يكسر run_webhook/run_polling الداخليين بمكتبة python-telegram-bot.
    # نجهّز واحد يدويًا هنا لضمان التوافق مهما كان إصدار بايثون على الاستضافة.
    try:
        asyncio.get_event_loop()
    except RuntimeError:
        asyncio.set_event_loop(asyncio.new_event_loop())

    db.init_db()
    # مزامنة (UPSERT) بدل البذر لمرة واحدة فقط — أي تحديث لملفات المهن/المدن/الأحياء
    # بالمستودع ينعكس تلقائيًا على قاعدة البيانات الحية في كل إعادة تشغيل، بدون حذف
    # أي بيانات فنيين مسجّلين مسبقًا.
    db.sync_professions_from_json(PROFESSIONS_JSON_PATH)
    db.sync_saudi_geo_from_json(SAUDI_REGIONS_JSON_PATH, SAUDI_CITIES_JSON_PATH, SAUDI_DISTRICTS_JSON_PATH)
    db.apply_name_translations(DOMAIN_TRANSLATIONS, PROFESSION_TRANSLATIONS)

    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("help", help_command))

    app.add_handler(build_register_conversation())
    app.add_handler(build_search_conversation())
    app.add_handler(build_whatsapp_click_handler())
    app.add_handler(build_telegram_click_handler())
    # هاندلرز "التقاط الجلسات المنتهية" — لازم تُسجَّل بعد كل هاندلرز /search
    # و/register أعلاه (بنفس المجموعة الافتراضية)، عشان تلتقط بس الضغطات اللي
    # ما قدر أي هاندلر سابق (المحادثة النشطة، أو أزرار واتساب/تلغرام الدائمة)
    # يتعرّف عليها — راجع تعليق handle_stale_callback لتفاصيل السبب.
    app.add_handler(CallbackQueryHandler(handle_stale_callback, pattern="^srch_"))
    app.add_handler(CallbackQueryHandler(handle_stale_callback, pattern="^reg_"))
    app.add_handler(build_admin_handler())
    for handler in build_subscription_handlers():
        app.add_handler(handler)
    for handler in build_donation_handlers():
        app.add_handler(handler)
    for handler in build_privacy_handlers():
        app.add_handler(handler)
    for handler in build_language_handlers():
        app.add_handler(handler)

    # مهمة دورية: فحص الاشتراكات المنتهية وتنبيه الفنيين تلقائيًا بتلغرام (كل ساعة).
    app.job_queue.run_repeating(
        check_expired_subscriptions, interval=EXPIRY_CHECK_INTERVAL_SECONDS, first=60
    )

    external_url = os.environ.get("RENDER_EXTERNAL_URL", "")
    if external_url:
        port = int(os.environ.get("PORT", "10000"))
        webhook_path = BOT_TOKEN  # مسار سري (نفس التوكن) بدل مسار عام يخمنه أي أحد
        logger.info("بوت «فني» يعمل الآن (webhook) على المنفذ %s...", port)
        app.run_webhook(
            listen="0.0.0.0",
            port=port,
            url_path=webhook_path,
            webhook_url=f"{external_url}/{webhook_path}",
            allowed_updates=["message", "callback_query"],
        )
    else:
        logger.info("بوت «فني» يعمل الآن (polling)...")
        app.run_polling(allowed_updates=["message", "callback_query"])


if __name__ == "__main__":
    main()
