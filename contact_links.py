# روابط التواصل المباشر مع الفني (ضغطة وحدة تفتح واتساب/تلغرام).
#
# المشكلة: زر الرابط (url) بتلغرام يفتح مباشرة، لكن البوت ما يدري إن العميل ضغطه —
# وإحنا نحتاج نعرف عشان نحسب فرص الفني المجانية. والزر العادي (callback) يخلي البوت
# يدري، لكنه يحتاج رسالة ثانية فيها زر الفتح (خطوة زيادة) وكانت تعرض الرقم.
#
# الحل: زر رابط يروح لسيرفرنا أولًا (/c/<رمز>)، السيرفر يسجّل الضغطة ثم يحوّل فورًا
# لواتساب/تلغرام. العميل يحس إنه ضغطة وحدة، والرقم ما يظهر بالبطاقة ولا بالرابط
# (الرمز موقّع ومشفّر الشكل، فيه فقط رقم الفني الداخلي ورقم العميل).

import base64
import hashlib
import hmac
import re
import time
from urllib.parse import quote

import config
import countries

TOKEN_MAX_AGE_SECONDS = 60 * 24 * 3600  # بطاقة عمرها شهرين ما زالت تفتح


def enabled() -> bool:
    return bool(config.PUBLIC_BASE_URL)


def _key() -> bytes:
    # مفتاح التوقيع مشتق من توكن البوت (موجود أصلًا عند البوت ولوحة التحكم) — ما
    # نحتاج سر جديد بملف .env، ومحد يقدر يزوّر رابط يحسب ضغطات على فني ثاني.
    return hashlib.sha256(("fani-contact-link:" + config.BOT_TOKEN).encode()).digest()


def _b64(b: bytes) -> str:
    return base64.urlsafe_b64encode(b).decode().rstrip("=")


def _unb64(s: str) -> bytes:
    return base64.urlsafe_b64decode(s + "=" * (-len(s) % 4))


def make_token(professional_id: int, customer_id: int, channel: str, prof_slot: int = 1) -> str:
    """channel: 'w' واتساب أو 't' تلغرام. prof_slot: أي مهنة بحث عنها العميل (1 أو 2)
    عشان الرسالة الجاهزة بواتساب تذكر المهنة الصحيحة."""
    payload = f"{professional_id}.{customer_id}.{channel}.{prof_slot}.{int(time.time())}".encode()
    sig = hmac.new(_key(), payload, hashlib.sha256).digest()[:12]
    return f"{_b64(payload)}.{_b64(sig)}"


def parse_token(token: str, now: float | None = None) -> dict | None:
    try:
        p64, s64 = token.split(".", 1)
        payload, sig = _unb64(p64), _unb64(s64)
        if not hmac.compare_digest(sig, hmac.new(_key(), payload, hashlib.sha256).digest()[:12]):
            return None
        pid, cid, channel, slot, ts = payload.decode().split(".")
        if channel not in ("w", "t"):
            return None
        if (now or time.time()) - int(ts) > TOKEN_MAX_AGE_SECONDS:
            return None
        return {"professional_id": int(pid), "customer_id": int(cid), "channel": channel, "prof_slot": int(slot)}
    except Exception:
        return None


def build_url(professional_id: int, customer_id: int, channel: str, prof_slot: int = 1) -> str:
    return f"{config.PUBLIC_BASE_URL.rstrip('/')}/c/{make_token(professional_id, customer_id, channel, prof_slot)}"


# ─────────────── بناء روابط واتساب/تلغرام الفعلية (نُقلت من handlers/search.py) ───────────────

def intl_digits(number: str, country: str | None) -> str:
    """الرقم بصيغة دولية (أرقام فقط بدون +) حسب دولة الفني — يعالج الأرقام المحلية
    المكتوبة يدويًا (مثل 01012345678 لمصر أو 51234567 للكويت)."""
    normalized = countries.normalize_phone(number, country or countries.DEFAULT_COUNTRY)
    if normalized:
        return normalized.lstrip("+")
    # رقم ما يطابق صيغة الدولة — المنطق القديم (توافق مع تسجيلات سعودية قديمة)
    digits = re.sub(r"\D", "", number)
    if digits.startswith("00"):
        digits = digits[2:]
    if digits.startswith("0") and not digits.startswith("966"):
        digits = "966" + digits[1:]
    elif not digits.startswith("966") and len(digits) == 9 and digits.startswith("5"):
        digits = "966" + digits
    return digits


def wa_link(number: str, text: str | None = None, country: str | None = None) -> str:
    link = f"https://wa.me/{intl_digits(number, country)}"
    if text:
        link += f"?text={quote(text)}"
    return link


def tg_link(number: str, country: str | None = None) -> str:
    return f"https://t.me/+{intl_digits(number, country)}"


def profession_for_slot(p: dict, slot: int) -> str:
    return (p.get("profession2_name") if slot == 2 and p.get("profession2_name") else p["profession_name"])
