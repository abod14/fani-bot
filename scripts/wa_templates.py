# إنشاء قوالب إشعارات واتساب (مرة وحدة) ومتابعة موافقة ميتا عليها.
#
#   cd /root/fani-bot && venv/bin/python scripts/wa_templates.py create 2153603535505078
#   cd /root/fani-bot && venv/bin/python scripts/wa_templates.py status 2153603535505078
#   cd /root/fani-bot && venv/bin/python scripts/wa_templates.py test 2153603535505078 9665XXXXXXXX
#     (يرسل كل قالب «مقبول» لرقمك عشان تشوف شكله — كل رسالة تنحسب بسعرها)
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


DETAILS_BTN = [{"type": "QUICK_REPLY", "text": "التفاصيل"}]


def _tpl_details(name, text, example):
    return {"name": name, "language": "ar", "category": "UTILITY",
            "components": [{"type": "BODY", "text": text, "example": {"body_text": [example]}},
                           {"type": "BUTTONS", "buttons": DETAILS_BTN}]}


TEMPLATES = [
    # «تم تسجيلك» — للفني اللي سجّله مسوّق على رقمه + زر «حسابي» (بطاقته وحالته ورابط القناة)
    {"name": "fanni_registered", "language": "ar", "category": "UTILITY",
     "components": [{"type": "BODY",
                     "text": "تم تسجيلك في «فنّي» يا {{1}} بمهنة «{{2}}»، وأصبح رقمك يظهر للعملاء "
                             "الذين يبحثون عن خدمتك في منطقتك.",
                     "example": {"body_text": [["عبدالله", "سباك"]]}},
                    {"type": "BUTTONS", "buttons": [{"type": "QUICK_REPLY", "text": "حسابي"}]}]},
    # رمز التحقق (تسجيل فني على رقم آخر) — نص ميتا الجاهز، تصنيف «مصادقة» (الأرخص)
    {"name": "fanni_verify_code", "language": "ar", "category": "AUTHENTICATION",
     "components": [{"type": "BODY", "add_security_recommendation": True},
                    {"type": "FOOTER", "code_expiration_minutes": 10},
                    {"type": "BUTTONS", "buttons": [{"type": "OTP", "otp_type": "COPY_CODE", "text": "نسخ الرمز"}]}]},
    # كشف حساب بحت بلا ذكر للاشتراك + زر «التفاصيل» فقط — أقرب لتصنيف «خدمة»
    _tpl_details("fanni_account_update",
                 "تحديث حسابك في «فنّي» يا {{1}}: رصيد فرص التواصل المجانية في حسابك انتهى، "
                 "وظهور رقمك في نتائج البحث متوقف حاليًا.",
                 ["عبدالله"]),
    _tpl_details("fanni_monthly_summary",
                 "ملخص حسابك الشهري في «فنّي»: بحث {{1}} من العملاء عن «{{2}}» في منطقتك خلال الشهر الماضي، "
                 "ولم يظهر لهم رقمك.",
                 ["7", "سباك"]),
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
    if len(sys.argv) < 3 or sys.argv[1] not in ("create", "status", "test"):
        print("الاستخدام: venv/bin/python scripts/wa_templates.py create|status <WABA_ID>  أو  test <WABA_ID> <رقمك>")
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
    if action == "test":
        if len(sys.argv) < 4:
            print("اكتب رقمك بعد الأمر، مثال: ... test 2153603535505078 966501234567")
            return
        to = "".join(ch for ch in sys.argv[3] if ch.isdigit())
        examples = {t["name"]: t["components"][0]["example"]["body_text"][0] for t in TEMPLATES
                    if "example" in t["components"][0]}
        st = requests.get(url, headers=headers, params={"fields": "name,status", "limit": 100}, timeout=30).json()
        approved = [t["name"] for t in st.get("data", []) if t.get("status") == "APPROVED" and t["name"] in examples]
        if not approved:
            print("⏳ ولا قالب مقبول بعد (لازم APPROVED) — جرّب بعدين.")
            return
        send_url = f"https://graph.facebook.com/{config.WA_GRAPH_VERSION}/{config.WA_PHONE_NUMBER_ID}/messages"
        for name in approved:
            comps = [{"type": "body", "parameters": [{"type": "text", "text": v} for v in examples[name]]}]
            nbtn = sum(len(c.get("buttons", [])) for t in TEMPLATES if t["name"] == name
                       for c in t["components"] if c.get("type") == "BUTTONS")
            comps += [{"type": "button", "sub_type": "quick_reply", "index": str(i),
                       "parameters": [{"type": "payload", "payload": p}]} for i, p in enumerate(["R:sub", "R:mute"][:nbtn])]
            r = requests.post(send_url, headers=headers, timeout=30, json={
                "messaging_product": "whatsapp", "to": to, "type": "template",
                "template": {"name": name, "language": {"code": "ar"}, "components": comps}})
            print(("✅ انرسل: " if r.ok else "❌ ما انرسل: ") + name + ("" if r.ok else f" — {r.json().get('error', {}).get('message')}"))
        return
    r = requests.get(url, headers=headers, params={"fields": "name,status,category,rejected_reason", "limit": 50}, timeout=30)
    names = {t["name"] for t in TEMPLATES}
    print("\nحالة القوالب:")
    for t in r.json().get("data", []):
        if t["name"] in names:
            extra = f" — سبب الرفض: {t.get('rejected_reason')}" if t.get("status") == "REJECTED" else ""
            print(f"  • {t['name']}: {t['status']} ({t.get('category')}){extra}")


if __name__ == "__main__":
    main()
