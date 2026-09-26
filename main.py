# نقطة تشغيل بوت «فني».
# تشغيل: python main.py  (بعد تجهيز .env — راجع README.md)

import logging

from telegram.ext import ApplicationBuilder, CommandHandler

import db
from config import (
    BOT_TOKEN,
    PROFESSIONS_JSON_PATH,
    SAUDI_CITIES_JSON_PATH,
    SAUDI_DISTRICTS_JSON_PATH,
    SAUDI_REGIONS_JSON_PATH,
)
from handlers.admin import build_admin_handler
from handlers.privacy import build_privacy_handlers
from handlers.register import build_register_conversation
from handlers.search import build_search_conversation, build_whatsapp_click_handler
from handlers.start import start_command
from handlers.subscription import build_subscription_handlers

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)


async def help_command(update, context):
    await update.message.reply_text(
        "بوت «فني» — دليل المهنيين والفنيين\n\n"
        "الأوامر المتاحة:\n"
        "/start — القائمة الرئيسية\n"
        "/register — التسجيل كفني\n"
        "/search — البحث عن فني\n"
        "/subscribe — تفعيل/تجديد الاشتراك (للفنيين)\n"
        "/delete_account — حذف بياناتك نهائيًا من البوت\n"
        "/cancel — إلغاء أي عملية جارية\n"
        "/help — عرض هذه الرسالة"
    )


def main():
    db.init_db()
    db.seed_professions_from_json_if_empty(PROFESSIONS_JSON_PATH)
    db.seed_saudi_geo_if_empty(SAUDI_REGIONS_JSON_PATH, SAUDI_CITIES_JSON_PATH, SAUDI_DISTRICTS_JSON_PATH)

    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("help", help_command))

    app.add_handler(build_register_conversation())
    app.add_handler(build_search_conversation())
    app.add_handler(build_whatsapp_click_handler())
    app.add_handler(build_admin_handler())
    for handler in build_subscription_handlers():
        app.add_handler(handler)
    for handler in build_privacy_handlers():
        app.add_handler(handler)

    logger.info("بوت «فني» يعمل الآن (polling)...")
    app.run_polling(allowed_updates=["message", "callback_query"])


if __name__ == "__main__":
    main()
