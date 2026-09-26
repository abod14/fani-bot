# نقطة تشغيل بوت «فني».
# تشغيل: python main.py  (بعد تجهيز .env — راجع README.md)

import logging

from telegram.ext import ApplicationBuilder, CommandHandler

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
from handlers.privacy import build_privacy_handlers
from handlers.register import build_register_conversation
from handlers.search import build_search_conversation, build_whatsapp_click_handler
from handlers.start import build_language_handlers, start_command
from handlers.subscription import build_subscription_handlers
from translations_data import DOMAIN_TRANSLATIONS, PROFESSION_TRANSLATIONS

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)


async def help_command(update, context):
    lang = db.get_user_language(update.effective_user.id)
    await update.message.reply_text(i18n.t("help_text", lang))


def main():
    db.init_db()
    db.seed_professions_from_json_if_empty(PROFESSIONS_JSON_PATH)
    db.seed_saudi_geo_if_empty(SAUDI_REGIONS_JSON_PATH, SAUDI_CITIES_JSON_PATH, SAUDI_DISTRICTS_JSON_PATH)
    db.apply_name_translations(DOMAIN_TRANSLATIONS, PROFESSION_TRANSLATIONS)

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
    for handler in build_language_handlers():
        app.add_handler(handler)

    logger.info("بوت «فني» يعمل الآن (polling)...")
    app.run_polling(allowed_updates=["message", "callback_query"])


if __name__ == "__main__":
    main()
