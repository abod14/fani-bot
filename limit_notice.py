# لحظة ما تخلص فرص الفني المجانية → إشعار واحد «خلصت فرصك» مع زر الاشتراك (طلب المالك).
# تلغرام مجاني؛ فني واتساب غير مربوط بتلغرام ياخذ قالب واتساب (مدفوع) — التفاصيل بـ nudges.py.
# (العداد بعد كل تواصل انلغى بطلب المالك.)

import db
import nudges


def just_exhausted(professional_id: int) -> dict | None:
    p = db.get_professional_by_id(professional_id)
    if not p or p.get("is_subscribed") or p.get("status") != db.STATUS_ACTIVE:
        return None
    limit = int(db.get_setting("free_contacts_limit", str(db.FREE_CONTACTS_LIMIT))) + (p.get("bonus_contacts") or 0)
    if (p.get("free_contacts_used") or 0) != limit:      # بالضبط وصل الحد الحين (مو قبل ولا بعد)
        return None
    return p


def notify_if_exhausted_async(professional_id: int):
    if just_exhausted(professional_id):
        nudges.notify_exhausted_async(professional_id)
