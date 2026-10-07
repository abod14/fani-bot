# متغيرات الإعداد — تُقرأ من متغيرات البيئة (Environment Variables)
# لا تكتب التوكن أو رقم الأدمن هنا مباشرة؛ ضعهم في ملف .env (راجع .env.example)

import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).parent

BOT_TOKEN = os.environ.get("BOT_TOKEN", "")
ADMIN_TELEGRAM_ID = os.environ.get("ADMIN_TELEGRAM_ID", "")

PROFESSIONS_JSON_PATH = BASE_DIR / "data" / "professions.json"
DB_PATH = BASE_DIR / "fani_bot.db"

SAUDI_REGIONS_JSON_PATH = BASE_DIR / "data" / "saudi_geo" / "regions.json"
SAUDI_CITIES_JSON_PATH = BASE_DIR / "data" / "saudi_geo" / "cities.json"
SAUDI_DISTRICTS_JSON_PATH = BASE_DIR / "data" / "saudi_geo" / "districts.json"

# مناطق/مدن/أحياء دول التوسع (مصر + الإمارات + الكويت + قطر + البحرين + عُمان) —
# يُولَّد من data/extra_geo/build_extra_geo.py
EXTRA_GEO_JSON_PATH = BASE_DIR / "data" / "extra_geo" / "geo.json"

if not BOT_TOKEN:
    raise RuntimeError(
        "BOT_TOKEN غير موجود. أنشئ ملف .env (انسخ من .env.example) وضع فيه توكن البوت."
    )

if not ADMIN_TELEGRAM_ID:
    raise RuntimeError(
        "ADMIN_TELEGRAM_ID غير موجود. أنشئ ملف .env وضع فيه رقم حسابك بتلغرام "
        "(احصل عليه من بوت @userinfobot)."
    )

ADMIN_TELEGRAM_ID = int(ADMIN_TELEGRAM_ID)

# الرابط العام لسيرفرك (لوحة التحكم) — مثل http://185.197.249.218:5050 أو دومينك لاحقًا.
# لو موجود: أزرار التواصل ببطاقة الفني تفتح واتساب/تلغرام بضغطة وحدة (عبر /c/ باللوحة
# اللي تسجّل الضغطة ثم تحوّل). لو فاضي: الطريقة القديمة (رسالة ثانية فيها زر الفتح).
PUBLIC_BASE_URL = os.environ.get("PUBLIC_BASE_URL", "").strip()

# ───────────────────────── بوت واتساب (تجريبي) ─────────────────────────
# من صفحة WhatsApp ← API Setup بتطبيق ميتا. يُكتبون بملف .env عبر whatsapp_bot/setup.sh.
WA_TOKEN = os.environ.get("WA_TOKEN", "").strip()
WA_PHONE_NUMBER_ID = os.environ.get("WA_PHONE_NUMBER_ID", "").strip()
WA_VERIFY_TOKEN = os.environ.get("WA_VERIFY_TOKEN", "").strip()
WA_APP_SECRET = os.environ.get("WA_APP_SECRET", "").strip()  # اختياري: للتحقق من توقيع رسائل ميتا
WA_GRAPH_VERSION = os.environ.get("WA_GRAPH_VERSION", "v23.0").strip()
WA_PORT = int(os.environ.get("WA_PORT", "5070"))
WA_WABA_ID = os.environ.get("WA_WABA_ID", "").strip()   # حساب واتساب للأعمال — لإنشاء القوالب
# أسماء قوالب الإشعارات المدفوعة (تُنشأ مرة وحدة بـ scripts/wa_templates.py وتنتظر موافقة ميتا)
# ميتا صنّفت النسخة الأولى «تسويق» (أغلى) — النسخة الإخبارية (خدمة) تُجرَّب أول، ولو مو مقبولة
# ننتقل للي بعدها تلقائيًا.
WA_TPL_FREE_ENDED = os.environ.get("WA_TPL_FREE_ENDED",
                                   "fanni_account_update,fanni_account_alert,fanni_free_ended").split(",")
WA_TPL_MONTHLY_SUMMARY = os.environ.get("WA_TPL_MONTHLY_SUMMARY", "fanni_monthly_summary").split(",")
# قالب «رمز التحقق» (تصنيف AUTHENTICATION) — لتسجيل فني على رقم غير رقم المرسل
WA_TPL_VERIFY = os.environ.get("WA_TPL_VERIFY", "fanni_verify_code").split(",")
WA_TPL_CUSTOMER_SEARCHING = os.environ.get("WA_TPL_CUSTOMER_SEARCHING", "fanni_request_alert,fanni_customer_searching").split(",")

# ───────────────────────── قناة تلغرام المرتبطة بالبوت ─────────────────────────
# يوزر القناة (بدون @) — تُستخدم للتحقق من اشتراك الفني قبل إكمال التسجيل، ولزر
# "قناتنا" بقائمة البداية. لازم تضيف البوت كـ"مشرف" (Admin) داخل هذي القناة حتى
# يقدر يتحقق فعليًا من الاشتراك (getChatMember) — بدونها التحقق ما يشتغل.
CHANNEL_USERNAME = os.environ.get("CHANNEL_USERNAME", "faniboot")
CHANNEL_URL = f"https://t.me/{CHANNEL_USERNAME}"

# ───────────────────────── إعدادات الاشتراك (خطوة 7) ─────────────────────────

# مفتاح Tap السري (Secret Key) — من لوحة تحكم Tap (تجريبي أو حقيقي).
# لو تركته فاضي، زر الاشتراك عبر Tap يعطي رسالة "غير مفعّل حاليًا" بدل ما يفشل بخطأ.
TAP_SECRET_KEY = os.environ.get("TAP_SECRET_KEY", "")

# رابط صفحتك اللي يرجع لها العميل بعد الدفع بـ Tap (مجرد صفحة تأكيد، التفعيل الفعلي
# يصير لما الفني يضغط زر "تحققت من الدفع" بالبوت نفسه — ما نحتاج سيرفر webhook منفصل).
TAP_REDIRECT_URL = os.environ.get("TAP_REDIRECT_URL", "https://tap.company")

# سعر الاشتراك الشهري بالريال السعودي (لـ Tap) وبنجوم تلغرام (لـ Stars).
# عدّل هذي الأرقام بملف .env حسب السعر اللي تقرره.
SUBSCRIPTION_PRICE_SAR = float(os.environ.get("SUBSCRIPTION_PRICE_SAR", "30"))
SUBSCRIPTION_PRICE_STARS = int(os.environ.get("SUBSCRIPTION_PRICE_STARS", "150"))
SUBSCRIPTION_DAYS = int(os.environ.get("SUBSCRIPTION_DAYS", "30"))

# ───────────────────────── لوحة تحكم الأدمن (صفحة ويب، خطوة 8) ─────────────────────────
# تعمل كسيرفر Flask منفصل (python admin_panel/app.py)، لكن تقرأ/تكتب نفس ملف قاعدة
# البيانات (fani_bot.db) اللي يستخدمه البوت مباشرة — بدون أي تزامن إضافي، لأن SQLite
# يدعم قراءة/كتابة من أكثر من عملية على نفس الملف.
ADMIN_PANEL_USERNAME = os.environ.get("ADMIN_PANEL_USERNAME", "admin")
ADMIN_PANEL_PASSWORD = os.environ.get("ADMIN_PANEL_PASSWORD", "")
ADMIN_PANEL_SECRET_KEY = os.environ.get("ADMIN_PANEL_SECRET_KEY", "")
