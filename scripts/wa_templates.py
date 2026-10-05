# إنشاء قوالب إشعارات واتساب (مرة وحدة) ومتابعة موافقة ميتا عليها.
#
#   cd /root/fani-bot && venv/bin/python scripts/wa_templates.py create 2153603535505078
#   cd /root/fani-bot && venv/bin/python scripts/wa_templates.py status 2153603535505078
#
# الرقم = WABA ID (حساب واتساب للأعمال). التوكن يُقرأ من .env (WA_TOKEN) — ما ينطبع أبدًا.
# بعد ما تصير الحالة APPROVED، البوت يستخدم القوالب لحاله.

import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import requests  # noqa: E402

import config  # noqa: E402

BTN = [{"type": "QUICK_REPLY", "text": "التفاصيل والاشتراك"}, {"type": "QUICK_REPLY", "text": "إيقاف الإشعارات"}]
def _tpl(name, category, text, example):
    return {"name": name, "language": "ar", "category": category,
            "components": [{"type": "BODY", "text": text, "example": {"body_text": [example]}},
                           {"type": "BUTTONS", "buttons": BTN}]}


TEMPLATES = [
    # النسخة الإخبارية (تنبيه حساب) — أرخص لو ميتا قبلتها «خدمة»
    _tpl("fanni_account_alert", "UTILITY",
         "تنبيه حسابك في «فنّي»: يا {{1}}، انتهت فرصك المجانية للتواصل مع العملاء، وظهور رقمك بنتائج البحث متوقف حاليًا.",
         ["عبدالله"]),
    _tpl("fanni_request_alert", "UTILITY",
         "تنبيه حسابك في «فنّي»: وصل طلب بحث عن «{{1}}» في {{2}}، ولم يظهر رقمك لأن فرصك المجانية انتهت.",
         ["سباك", "جدة — حي الصفا"]),
    # النسخة الأولى (صنّفتها ميتا «تسويق») — احتياط
    _tpl("fanni_free_ended", "MARKETING",
         "⚠️ يا {{1}}، انتهت فرصك المجانية للتواصل مع العملاء في «فنّي».\nجدد اشتراكك من هنا 👇", ["عبدالله"]),
    _tpl("fanni_customer_searching", "MARKETING",
         "🔔 فيه عميل يدوّر على «{{1}}» في {{2}}، لكن رقمك ما ظهر له لأنك خلّصت فرصك المجانية.\n"
         "اشترك عشان تظهر لكل العملاء اللي يبحثون عن خدمتك.", ["سباك", "جدة — حي الصفا"]),
]


def main():
    if len(sys.argv) < 3 or sys.argv[1] not in ("create", "status"):
        print("الاستخدام: venv/bin/python scripts/wa_templates.py create|status <WABA_ID>")
        return
    action, waba = sys.argv[1], sys.argv[2].strip()
    if not config.WA_TOKEN:
        print("❌ WA_TOKEN مو موجود بملف .env")
        return
    url = f"https://graph.facebook.com/{config.WA_GRAPH_VERSION}/{waba}/message_templates"
    headers = {"Authorization": f"Bearer {config.WA_TOKEN}"}
    if action == "create":
        existing = {t["name"] for t in requests.get(url, headers=headers, params={"fields": "name", "limit": 100},
                                                   timeout=30).json().get("data", [])}
        for t in TEMPLATES:
            if t["name"] in existing:
                print(f"• {t['name']}: موجود من قبل — تخطّيته")
                continue
            r = requests.post(url, headers=headers, json=t, timeout=30)
            data = r.json()
            if r.ok:
                print(f"✅ {t['name']}: انرسل لميتا — الحالة: {data.get('status')} | التصنيف: {data.get('category')}")
            else:
                msg = (data.get("error") or {}).get("error_user_msg") or (data.get("error") or {}).get("message")
                print(f"❌ {t['name']}: {msg}")
    r = requests.get(url, headers=headers, params={"fields": "name,status,category,rejected_reason", "limit": 50}, timeout=30)
    names = {t["name"] for t in TEMPLATES}
    print("\nحالة القوالب:")
    for t in r.json().get("data", []):
        if t["name"] in names:
            extra = f" — سبب الرفض: {t.get('rejected_reason')}" if t.get("status") == "REJECTED" else ""
            print(f"  • {t['name']}: {t['status']} ({t.get('category')}){extra}")


if __name__ == "__main__":
    main()
