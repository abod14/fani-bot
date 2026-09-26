# طبقة قراءة بيانات المهن — تُقرأ الآن مباشرة من قاعدة البيانات (جدولا domains/professions)
# بدل ملف professions.json الثابت، عشان أي تعديل من لوحة التحكم (إضافة/تعديل/حذف مهنة أو
# مجال) ينعكس فورًا بدون إعادة تشغيل البوت.
#
# البذر الأولي من data/professions.json يصير مرة وحدة عبر db.seed_professions_from_json_if_empty
# (يُستدعى من main.py عند التشغيل). بعدها قاعدة البيانات هي المصدر الوحيد للحقيقة.
#
# نفس هذا المصدر يُستخدم من /register و /search، وشكل القيم المرجعة متوافق مع الشكل
# القديم (id/name/services) حتى ما نحتاج نعدّل الهاندلرز.

import json

import db


def _profession_dict(row: dict) -> dict:
    """يحوّل صف قاعدة البيانات لنفس الشكل القديم (id, name, services, ...)."""
    return {
        "id": row["id"],
        "name": row["name"],
        "isco_code": row.get("isco_code"),
        "status": row.get("status"),
        "services": json.loads(row["services_json"]) if row.get("services_json") else [],
    }


def _domain_dict(row: dict) -> dict:
    return {"id": row["id"], "name": row["name"]}


def get_domains():
    return [_domain_dict(d) for d in db.list_domains()]


def get_domain(domain_id: str):
    row = db.get_domain_by_id(domain_id)
    return _domain_dict(row) if row else None


def get_professions_by_domain(domain_id: str):
    return [_profession_dict(p) for p in db.list_professions_by_domain(domain_id)]


def get_profession(profession_id: str):
    """يرجّع (domain, profession) أو (None, None)."""
    row = db.get_profession_by_id(profession_id)
    if not row:
        return None, None
    domain_row = db.get_domain_by_id(row["domain_id"])
    domain = _domain_dict(domain_row) if domain_row else None
    return domain, _profession_dict(row)
