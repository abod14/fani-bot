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

BTN = [{"type": "QUICK_REPLY", "text": "اشترك الآن"}]
TEMPLATES = [
    {
        "name": config.WA_TPL_FREE_ENDED,
        "language": "ar",
        "category": "UTILITY",
        "components": [
            {"type": "BODY",
             "text": "⚠️ خلصت فرصك المجانية في «فنّي» يا {{1}}، ورقمك ما يظهر للعملاء الحين.\n"
                     "اشترك عشان ترجع تظهر وتستقبل عملاء بدون حدود.",
             "example": {"body_text": [["عبدالله"]]}},
            {"type": "BUTTONS", "buttons": BTN},
        ],
    },
    {
        "name": config.WA_TPL_CUSTOMER_SEARCHING,
        "language": "ar",
        "category": "UTILITY",
        "components": [
            {"type": "BODY",
             "text": "🔔 فيه عميل يدوّر على «{{1}}» في {{2}}، لكن رقمك ما ظهر له لأنك خلّصت فرصك المجانية.\n"
                     "اشترك عشان تظهر لكل العملاء اللي يبحثون عن خدمتك.",
             "example": {"body_text": [["سباك", "جدة — حي الصفا"]]}},
            {"type": "BUTTONS", "buttons": BTN},
        ],
    },
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
        for t in TEMPLATES:
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
