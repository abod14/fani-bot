# طبقة قراءة بيانات المهن — تُقرأ الآن مباشرة من قاعدة البيانات (جدولا domains/professions)
# بدل ملف professions.json الثابت، عشان أي تعديل من لوحة التحكم (إضافة/تعديل/حذف مهنة أو
# مجال) ينعكس فورًا بدون إعادة تشغيل البوت.
#
# البذر الأولي من data/professions.json يصير مرة وحدة عبر db.seed_professions_from_json_if_empty
# (يُستدعى من main.py عند التشغيل). بعدها قاعدة البيانات هي المصدر الوحيد للحقيقة.
#
# نفس هذا المصدر يُستخدم من /register و /search، وشكل القيم المرجعة متوافق مع الشكل
# القديم (id/name/services) حتى ما نحتاج نعدّل الهاندلرز.
#
# دعم تعدد اللغات: كل الدوال تقبل lang اختياري ('ar' الافتراضي)، وترجّع الاسم
# بالإنجليزي/الأردو لو موجود، وإلا ترجع الاسم العربي كاحتياط (ما نعرض حقل فاضي أبدًا).

import json

import db


def _localized_name(row: dict, lang: str) -> str:
    if lang == "en":
        return row.get("name_en") or row["name"]
    if lang == "ur":
        return row.get("name_ur") or row["name"]
    return row["name"]


def _profession_dict(row: dict, lang: str = "ar") -> dict:
    """يحوّل صف قاعدة البيانات لنفس الشكل القديم (id, name, services, ...)."""
    return {
        "id": row["id"],
        "name": _localized_name(row, lang),
        "isco_code": row.get("isco_code"),
        "status": row.get("status"),
        "services": json.loads(row["services_json"]) if row.get("services_json") else [],
        "allow_city_wide": bool(row.get("allow_city_wide")),
    }


def _domain_dict(row: dict, lang: str = "ar") -> dict:
    return {"id": row["id"], "name": _localized_name(row, lang)}


def get_domains(lang: str = "ar"):
    return [_domain_dict(d, lang) for d in db.list_domains()]


def get_domain(domain_id: str, lang: str = "ar"):
    row = db.get_domain_by_id(domain_id)
    return _domain_dict(row, lang) if row else None


def get_professions_by_domain(domain_id: str, lang: str = "ar"):
    return [_profession_dict(p, lang) for p in db.list_professions_by_domain(domain_id)]


def get_profession(profession_id: str, lang: str = "ar"):
    """يرجّع (domain, profession) أو (None, None)."""
    row = db.get_profession_by_id(profession_id)
    if not row:
        return None, None
    domain_row = db.get_domain_by_id(row["domain_id"])
    domain = _domain_dict(domain_row, lang) if domain_row else None
    return domain, _profession_dict(row, lang)
