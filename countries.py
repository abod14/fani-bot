# الدول المدعومة بالبوت — السعودية + مصر + دول الخليج.
#
# - أسماء الدول بثلاث لغات (عربي/إنجليزي/أردو) لأزرار الاختيار.
# - قواعد أرقام الجوال لكل دولة (تطبيع الرقم لصيغة دولية موحّدة +رمز الدولة).
# - الدول المفعّلة تُقرأ من جدول settings (مفتاح enabled_countries) عشان الأدمن يقدر
#   يقفل/يفتح دولة من لوحة التحكم بدون تعديل كود؛ الافتراضي: كل الدول مفعّلة.
# - الدفع عبر Tap (بالريال) متاح للسعودية فقط؛ باقي الدول نجوم تلغرام (Stars) فقط.

import re

DEFAULT_COUNTRY = "SA"

# national_re: صيغة الرقم المحلي بدون رمز الدولة وبدون الصفر البادئ.
COUNTRIES = [
    {
        "code": "SA", "flag": "🇸🇦", "dial": "966",
        "name": {"ar": "السعودية", "en": "Saudi Arabia", "ur": "سعودی عرب"},
        "national_re": r"5\d{8}", "example": "0501234567",
    },
    {
        "code": "EG", "flag": "🇪🇬", "dial": "20",
        "name": {"ar": "مصر", "en": "Egypt", "ur": "مصر"},
        "national_re": r"1[0125]\d{8}", "example": "01012345678",
    },
    {
        "code": "AE", "flag": "🇦🇪", "dial": "971",
        "name": {"ar": "الإمارات", "en": "UAE", "ur": "متحدہ عرب امارات"},
        "national_re": r"5\d{8}", "example": "0501234567",
    },
    {
        "code": "KW", "flag": "🇰🇼", "dial": "965",
        "name": {"ar": "الكويت", "en": "Kuwait", "ur": "کویت"},
        "national_re": r"[4569]\d{7}", "example": "51234567",
    },
    {
        "code": "QA", "flag": "🇶🇦", "dial": "974",
        "name": {"ar": "قطر", "en": "Qatar", "ur": "قطر"},
        "national_re": r"[3567]\d{7}", "example": "33123456",
    },
    {
        "code": "BH", "flag": "🇧🇭", "dial": "973",
        "name": {"ar": "البحرين", "en": "Bahrain", "ur": "بحرین"},
        "national_re": r"[36]\d{7}", "example": "36123456",
    },
    {
        "code": "OM", "flag": "🇴🇲", "dial": "968",
        "name": {"ar": "عُمان", "en": "Oman", "ur": "عمان"},
        "national_re": r"[79]\d{7}", "example": "91234567",
    },
]

_BY_CODE = {c["code"]: c for c in COUNTRIES}
ALL_CODES = [c["code"] for c in COUNTRIES]


def get(code: str | None) -> dict | None:
    return _BY_CODE.get((code or "").upper())


def name(code: str | None, lang: str = "ar") -> str:
    c = get(code)
    if not c:
        return code or ""
    return c["name"].get(lang) or c["name"]["ar"]


def label(code: str, lang: str = "ar") -> str:
    """نص زر الدولة: العلم + الاسم بلغة المستخدم."""
    c = get(code)
    return f"{c['flag']} {name(code, lang)}" if c else code


def enabled_codes() -> list[str]:
    """الدول المفعّلة حاليًا (من الإعدادات)، بنفس ترتيب COUNTRIES. السعودية دائمًا
    مفعّلة حتى لو أحد مسحها بالخطأ من الإعدادات."""
    import db  # استيراد متأخر لتفادي استيراد دائري

    raw = db.get_setting("enabled_countries", ",".join(ALL_CODES))
    chosen = {c.strip().upper() for c in raw.split(",") if c.strip()}
    chosen.add(DEFAULT_COUNTRY)
    return [code for code in ALL_CODES if code in chosen]


def tap_available(code: str | None) -> bool:
    """Tap (مدى/فيزا بالريال) للسعودية فقط — باقي الدول الدفع بنجوم تلغرام فقط."""
    return (code or DEFAULT_COUNTRY) == "SA"


def normalize_phone(number: str, country_code: str) -> str | None:
    """يطبّع رقم جوال لصيغة دولية موحّدة (+رمز_الدولة + الرقم) مهما كتبه الفني:
    محلي بصفر أو بدونه، أو دولي بـ + أو 00. يقبل أيضًا رقم دولي كامل لأي دولة
    مدعومة ثانية (مثلًا فني بمصر يستخدم رقم سعودي). يرجّع None لو الرقم غير صحيح."""
    digits = re.sub(r"\D", "", number or "")
    if digits.startswith("00"):
        digits = digits[2:]
    if not digits:
        return None

    # 1) رقم دولي كامل (برمز أي دولة مدعومة) — نتأكد إن الباقي يطابق صيغة تلك الدولة
    for c in COUNTRIES:
        if digits.startswith(c["dial"]):
            rest = digits[len(c["dial"]):]
            if rest.startswith("0"):
                rest = rest[1:]
            if re.fullmatch(c["national_re"], rest):
                return f"+{c['dial']}{rest}"

    # 2) رقم محلي للدولة المختارة (بصفر بادئ أو بدونه)
    c = get(country_code) or _BY_CODE[DEFAULT_COUNTRY]
    local = digits[1:] if digits.startswith("0") else digits
    if re.fullmatch(c["national_re"], local):
        return f"+{c['dial']}{local}"
    return None


def country_of_phone(number: str) -> str | None:
    """يحدد دولة رقم دولي مطبّع (+...) — يُستخدم لبناء روابط واتساب/تلغرام صحيحة."""
    digits = re.sub(r"\D", "", number or "")
    for c in COUNTRIES:
        if digits.startswith(c["dial"]) and re.fullmatch(c["national_re"], digits[len(c["dial"]):]):
            return c["code"]
    return None
