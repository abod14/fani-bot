# لغات بوت واتساب: عربي (الافتراضي) + English + اردو — نفس لغات بوت تلغرام.
#
# - كل نص يرسله البوت يمر عبر tr("النص العربي {x}", x=...) — النص العربي نفسه هو المفتاح،
#   والترجمات في lang_texts.TEXTS. لو ما فيه ترجمة يرجع العربي (ما تطلع رسالة فاضية أبدًا).
# - لغة كل مستخدم محفوظة بجدول wa_languages، وتُضبط لكل رسالة واردة (set_lang) قبل معالجتها.
# - أسماء المدن والأحياء تبقى عربية دائمًا (بيانات رسمية) — نفس قرار تلغرام.
# - ما ينحفظ بقاعدة البيانات (اسم المهنة، الخدمات) يبقى عربي دائمًا؛ الترجمة للعرض فقط.

import re
import threading

import db

LANGS = ("ar", "en", "ur")
LANG_LABELS = {"ar": "العربية", "en": "English", "ur": "اردو"}

_local = threading.local()


def set_lang(lang: str | None):
    _local.lang = lang if lang in LANGS else "ar"


def get_lang() -> str:
    return getattr(_local, "lang", "ar")


def tr(ar: str, **kw) -> str:
    """ترجمة نص (المفتاح = النص العربي) للغة المستخدم الحالي، ثم تعبئة المتغيرات."""
    lang = get_lang()
    text = ar
    if lang != "ar":
        from whatsapp_bot.lang_texts import TEXTS
        text = (TEXTS.get(ar) or {}).get(lang) or ar
    return text.format(**kw) if kw else text


def tr_service(ar: str) -> str:
    """اسم خدمة للعرض بلغة المستخدم (الخدمات تنحفظ عربي)."""
    lang = get_lang()
    if lang == "ar":
        return ar
    from whatsapp_bot.lang_texts import SERVICES
    import db
    return (SERVICES.get(ar) or {}).get(lang) or db.service_translation(ar, lang) or ar


# ─────────── التخزين ───────────

def ensure_table():
    with db.get_conn() as conn:
        conn.execute("CREATE TABLE IF NOT EXISTS wa_languages (wa_id TEXT PRIMARY KEY, lang TEXT NOT NULL)")


def load(wa_id: str) -> str | None:
    with db.get_conn() as conn:
        try:
            r = conn.execute("SELECT lang FROM wa_languages WHERE wa_id = ?", (wa_id,)).fetchone()
        except Exception:  # noqa: BLE001 — الجدول ما انشأ بعد
            return None
    return r["lang"] if r else None


def save(wa_id: str, lang: str):
    if lang not in LANGS:
        return
    ensure_table()
    with db.get_conn() as conn:
        conn.execute("INSERT INTO wa_languages (wa_id, lang) VALUES (?, ?) "
                     "ON CONFLICT(wa_id) DO UPDATE SET lang = excluded.lang", (wa_id, lang))


def forget(wa_id: str):
    with db.get_conn() as conn:
        try:
            conn.execute("DELETE FROM wa_languages WHERE wa_id = ?", (wa_id,))
        except Exception:  # noqa: BLE001
            pass


# ─────────── الكشف التلقائي من أول رسالة ───────────

_URDU_ONLY = re.compile("[ٹڈڑںےۓہھگکیۂ]")
_LATIN = re.compile("[A-Za-z]")
_ARABIC = re.compile("[؀-ۿ]")


def detect(text: str) -> str | None:
    """لغة رسالة نصية: en لو حروف لاتينية بس (كلمة 3 أحرف فأكثر)، ur لو فيها حروف أردية خاصة.
    الاختصارات (s / d / 0) ما تحدد لغة."""
    t = (text or "").strip()
    if len(t) < 3:
        return None
    if _URDU_ONLY.search(t):
        return "ur"
    if _LATIN.search(t) and not _ARABIC.search(t):
        return "en"
    if _ARABIC.search(t):
        return "ar"
    return None
