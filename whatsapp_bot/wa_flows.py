# نماذج واتساب (WhatsApp Flows) لتسجيل الفني: شاشة فيها مربعات اختيار ☑️ للخدمات، وشاشة للأحياء —
# الفني يحدد أكثر من خيار ويضغط «تم» مرة وحدة (بدل ضغطة ورسالة لكل خيار).
#
# - النموذجان ثابتان (بدون سيرفر endpoint): القائمة نفسها (الخدمات/الأحياء) تنرسل مع الرسالة.
# - يُنشآن مرة وحدة بالأمر: venv/bin/python scripts/wa_flows.py create <WABA_ID>
#   والأمر يحفظ أرقامهما بالإعدادات (wa_flow_services / wa_flow_districts / wa_flow_mode).
# - لو النموذج مو موجود أو فشل إرساله ← البوت يرجع للقائمة العادية تلقائيًا.

import json

import db

FLOW_VERSION = "7.0"
SERVICES_SCREEN = "SERVICES"
DISTRICTS_SCREEN = "DISTRICTS"
MAX_OPTIONS = 20          # حد واتساب لعدد الخيارات بمربعات الاختيار
TITLE_MAX = 30


def _item_schema():
    return {"type": "array",
            "items": {"type": "object",
                      "properties": {"id": {"type": "string"}, "title": {"type": "string"},
                                     "description": {"type": "string"}}},
            "__example__": [{"id": "0", "title": "خيار", "description": "وصف"}]}


def _flow_json(screen: str, title: str, label: str, max_items: int | None, done: str) -> dict:
    group = {"type": "CheckboxGroup", "name": "picked", "label": label,
             "data-source": "${data.items}", "required": True, "min-selected-items": 1}
    if max_items:
        group["max-selected-items"] = max_items
    return {
        "version": FLOW_VERSION,
        "screens": [{
            "id": screen,
            "title": title,
            "terminal": True,
            "success": True,
            "data": {"heading": {"type": "string", "__example__": "اختر"}, "items": _item_schema()},
            "layout": {"type": "SingleColumnLayout", "children": [
                {"type": "TextBody", "text": "${data.heading}"},
                group,
                {"type": "Footer", "label": done,
                 "on-click-action": {"name": "complete", "payload": {"picked": "${form.picked}"}}},
            ]},
        }],
    }


FLOWS = {
    # key ← (اسم النموذج بميتا، JSON)
    "services": ("fanni_services", _flow_json(SERVICES_SCREEN, "الخدمات", "الخدمات التي أقدمها", None, "✅ تم التحديد")),
    "districts": ("fanni_districts", _flow_json(DISTRICTS_SCREEN, "الأحياء", "الأحياء التي أعمل فيها", 5, "✅ تم التحديد")),
}


def flow_id(key: str) -> str | None:
    return db.get_setting(f"wa_flow_{key}", "") or None


def mode() -> str:
    return db.get_setting("wa_flow_mode", "draft") or "draft"


def clip_title(t: str) -> str:
    t = (t or "").strip()
    return t if len(t) <= TITLE_MAX else t[:TITLE_MAX - 1] + "…"


def send(api, wa_id: str, key: str, body: str, cta: str, heading: str, items: list[dict], token: str) -> bool:
    """يرسل النموذج؛ يرجع False لو مو مجهّز أو فشل (عشان نرجع للقائمة العادية)."""
    fid = flow_id(key)
    if not fid or not items:
        return False
    screen = SERVICES_SCREEN if key == "services" else DISTRICTS_SCREEN
    items = [{k: v for k, v in it.items() if v} for it in items[:MAX_OPTIONS]]
    r = api.flow(wa_id, body, cta, fid, screen, {"heading": heading, "items": items}, token, mode=mode())
    return r is not None and getattr(r, "status_code", 500) < 400


def parse_reply(inter: dict) -> tuple[str, list[str]] | None:
    """رد النموذج (nfm_reply) ← (نوعه من الـ token، المعرّفات المختارة)."""
    nfm = inter.get("nfm_reply") or {}
    try:
        resp = json.loads(nfm.get("response_json") or "{}")
    except ValueError:
        return None
    token = str(resp.get("flow_token") or "")
    picked = resp.get("picked") or []
    if isinstance(picked, str):
        picked = [picked]
    return token.split(":", 1)[0], [str(x) for x in picked]
