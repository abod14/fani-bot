# إنشاء نموذجَي واتساب (مربعات اختيار الخدمات والأحياء لتسجيل الفني) — مرة وحدة.
#
#   cd /root/fani-bot && venv/bin/python scripts/wa_flows.py create 2153603535505078
#   cd /root/fani-bot && venv/bin/python scripts/wa_flows.py status
#   cd /root/fani-bot && venv/bin/python scripts/wa_flows.py publish
#   cd /root/fani-bot && venv/bin/python scripts/wa_flows.py off      (يرجع البوت للقوائم العادية)
#
# بعد «create» البوت يستخدم النموذجين فورًا بوضع «تجربة» (draft). بعد «publish» ينتقل للوضع الرسمي.

import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import requests  # noqa: E402

import config  # noqa: E402
import db  # noqa: E402
from whatsapp_bot import wa_flows  # noqa: E402

G = f"https://graph.facebook.com/{config.WA_GRAPH_VERSION}"


def _h():
    return {"Authorization": f"Bearer {config.WA_TOKEN}"}


def _err(r):
    try:
        e = r.json().get("error") or {}
        return e.get("error_user_msg") or e.get("message") or r.text[:300]
    except ValueError:
        return r.text[:300]


def create(waba):
    existing = {f["name"]: f["id"] for f in requests.get(f"{G}/{waba}/flows", headers=_h(), timeout=30)
                .json().get("data", [])}
    for key, (name, fj) in wa_flows.FLOWS.items():
        fid = existing.get(name)
        if not fid:
            r = requests.post(f"{G}/{waba}/flows", headers=_h(), timeout=30,
                              json={"name": name, "categories": ["SIGN_UP"]})
            if not r.ok:
                print(f"❌ {name}: {_err(r)}")
                continue
            fid = r.json()["id"]
        r = requests.post(f"{G}/{fid}/assets", headers=_h(), timeout=60,
                          data={"name": "flow.json", "asset_type": "FLOW_JSON"},
                          files={"file": ("flow.json", json.dumps(fj, ensure_ascii=False).encode(), "application/json")})
        if not r.ok:
            print(f"❌ {name}: {_err(r)}")
            continue
        errs = r.json().get("validation_errors") or []
        if errs:
            print(f"⚠️ {name}: أخطاء في النموذج:")
            for e in errs:
                print("   -", e.get("error"), "|", e.get("message"))
            continue
        db.set_setting(f"wa_flow_{key}", fid)
        print(f"✅ {name}: جاهز (وضع تجربة) — البوت يستخدمه الآن")
    if not db.get_setting("wa_flow_mode", ""):
        db.set_setting("wa_flow_mode", "draft")


def status():
    for key, (name, _) in wa_flows.FLOWS.items():
        fid = wa_flows.flow_id(key)
        if not fid:
            print(f"• {name}: غير مُنشأ")
            continue
        r = requests.get(f"{G}/{fid}", headers=_h(), params={"fields": "name,status,validation_errors"}, timeout=30)
        d = r.json()
        print(f"• {name}: {d.get('status')} | الأخطاء: {len(d.get('validation_errors') or [])}")
    print("وضع البوت:", wa_flows.mode())


def publish():
    ok = True
    for key, (name, _) in wa_flows.FLOWS.items():
        fid = wa_flows.flow_id(key)
        if not fid:
            print(f"❌ {name}: شغّل create أولًا")
            ok = False
            continue
        r = requests.post(f"{G}/{fid}/publish", headers=_h(), timeout=30)
        print(("✅ نُشر: " if r.ok else "❌ ما نُشر: ") + name + ("" if r.ok else f" — {_err(r)}"))
        ok = ok and r.ok
    if ok:
        db.set_setting("wa_flow_mode", "published")
        print("البوت الآن يستخدم الوضع الرسمي.")


def off():
    for key in wa_flows.FLOWS:
        db.set_setting(f"wa_flow_{key}", "")
    print("تم إيقاف النماذج — البوت يستخدم القوائم العادية.")


def main():
    if not config.WA_TOKEN:
        print("❌ WA_TOKEN غير موجود في .env")
        return
    a = sys.argv[1] if len(sys.argv) > 1 else ""
    if a == "create" and len(sys.argv) > 2:
        create(sys.argv[2].strip())
    elif a == "status":
        status()
    elif a == "publish":
        publish()
    elif a == "off":
        off()
    else:
        print("الاستخدام: create <WABA_ID> | status | publish | off")


if __name__ == "__main__":
    main()
