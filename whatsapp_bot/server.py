# سيرفر بوت واتساب «فني» (تجريبي) — يستقبل رسائل واتساب من ميتا (Webhook) ويرد عليها.
#
# التشغيل على السيرفر يتم عبر whatsapp_bot/setup.sh (خدمة systemd باسم fani-wa).
# يستمع على 127.0.0.1 فقط؛ ميتا توصله عبر رابط https (نفق cloudflared للتجربة،
# أو دومين حقيقي لاحقًا).

import hashlib
import hmac
import json
import logging
import sys
import threading
from collections import deque
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from flask import Flask, abort, request  # noqa: E402

import config  # noqa: E402
import db  # noqa: E402
from whatsapp_bot import flow  # noqa: E402
from whatsapp_bot.api import WhatsAppAPI  # noqa: E402

log = logging.getLogger("fani.wa")
app = Flask(__name__)
api = WhatsAppAPI()

# ميتا ممكن تعيد إرسال نفس الرسالة لو تأخر ردنا — نتجاهل المكرر
_seen: deque = deque(maxlen=5000)
_seen_set: set = set()
_seen_lock = threading.Lock()


def _first_time(message_id: str) -> bool:
    with _seen_lock:
        if not message_id or message_id in _seen_set:
            return False
        if len(_seen) == _seen.maxlen:
            _seen_set.discard(_seen[0])
        _seen.append(message_id)
        _seen_set.add(message_id)
        return True


@app.get("/wa/health")
def health():
    return "ok"


@app.get("/wa/webhook")
def verify():
    """خطوة التحقق اللي تسويها ميتا مرة وحدة لما تحفظ رابط الـ Webhook."""
    if (config.WA_VERIFY_TOKEN and request.args.get("hub.mode") == "subscribe"
            and request.args.get("hub.verify_token") == config.WA_VERIFY_TOKEN):
        return request.args.get("hub.challenge", ""), 200
    abort(403)


@app.post("/wa/webhook")
def receive():
    raw = request.get_data()
    if config.WA_APP_SECRET:
        expected = "sha256=" + hmac.new(config.WA_APP_SECRET.encode(), raw, hashlib.sha256).hexdigest()
        if not hmac.compare_digest(request.headers.get("X-Hub-Signature-256", ""), expected):
            abort(403)
    try:
        payload = json.loads(raw or b"{}")
    except ValueError:
        return "bad json", 400

    for entry in payload.get("entry", []):
        for change in entry.get("changes", []):
            value = change.get("value", {})
            pnid = (value.get("metadata") or {}).get("phone_number_id")
            if config.WA_PHONE_NUMBER_ID and pnid and pnid != config.WA_PHONE_NUMBER_ID:
                continue
            names = {c.get("wa_id"): ((c.get("profile") or {}).get("name") or "") for c in value.get("contacts", [])}
            for m in value.get("messages", []):   # «statuses» (تم التسليم/القراءة) نتجاهلها
                if not _first_time(m.get("id", "")):
                    continue
                wa_id = m.get("from", "")
                name = (names.get(wa_id) or "").split()[0] if names.get(wa_id) else ""
                # نرد على ميتا فورًا (200) ونعالج الرسالة بالخلفية
                threading.Thread(target=_process, args=(wa_id, name, m), daemon=True).start()
    return "ok", 200


def _process(wa_id: str, name: str, message: dict):
    try:
        flow.handle(api, wa_id, name, message)
    except Exception:
        log.exception("failed to handle WhatsApp message")


def main():
    logging.basicConfig(format="%(asctime)s %(levelname)s %(name)s: %(message)s", level=logging.INFO)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("werkzeug").setLevel(logging.WARNING)
    db.init_db()
    flow.ensure_tables()
    missing = [k for k in ("WA_TOKEN", "WA_PHONE_NUMBER_ID", "WA_VERIFY_TOKEN") if not getattr(config, k)]
    if missing:
        log.warning("WhatsApp settings missing in .env: %s", ", ".join(missing))
    log.info("Fanni WhatsApp bot listening on 127.0.0.1:%s", config.WA_PORT)
    app.run(host="127.0.0.1", port=config.WA_PORT, threaded=True)


if __name__ == "__main__":
    main()
