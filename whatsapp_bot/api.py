# إرسال الرسائل عبر WhatsApp Cloud API (Graph API من ميتا).
#
# حدود واتساب اللي نلتزم بها هنا (وإلا ترفض ميتا الرسالة):
#   أزرار الرد: 3 كحد أقصى، عنوان الزر ≤ 20 حرف.
#   القائمة: 10 صفوف كحد أقصى، عنوان الصف ≤ 24، وصفه ≤ 72، زر فتح القائمة ≤ 20.
#   نص الرسالة التفاعلية ≤ 1024، الترويسة ≤ 60، التذييل ≤ 60.

import logging

import httpx

import config

log = logging.getLogger("fani.wa")


def clip(text: str, n: int) -> str:
    text = (text or "").strip()
    return text if len(text) <= n else text[: n - 1].rstrip() + "…"


class WhatsAppAPI:
    def __init__(self, token: str | None = None, phone_number_id: str | None = None, sender=None):
        self.token = token if token is not None else config.WA_TOKEN
        self.phone_number_id = phone_number_id if phone_number_id is not None else config.WA_PHONE_NUMBER_ID
        # sender(payload) — قابل للاستبدال بالاختبارات (بدل الاتصال الفعلي بميتا)
        self._sender = sender or self._post

    @property
    def url(self) -> str:
        return f"https://graph.facebook.com/{config.WA_GRAPH_VERSION}/{self.phone_number_id}/messages"

    def _post(self, payload: dict):
        try:
            r = httpx.post(self.url, json=payload, timeout=20,
                           headers={"Authorization": f"Bearer {self.token}"})
            if r.status_code >= 400:
                log.warning("WA send failed %s: %s", r.status_code, r.text[:500])
            return r
        except Exception:
            log.exception("WA send error")
            return None

    def _send(self, to: str, body: dict):
        payload = {"messaging_product": "whatsapp", "recipient_type": "individual", "to": to}
        payload.update(body)
        return self._sender(payload)

    # ─────────── أنواع الرسائل ───────────

    def text(self, to: str, text: str):
        return self._send(to, {"type": "text", "text": {"body": clip(text, 4096), "preview_url": False}})

    def buttons(self, to: str, body: str, buttons: list[tuple[str, str]], header: str | None = None,
                footer: str | None = None):
        """buttons: [(id, title)] — 3 كحد أقصى."""
        inter = {
            "type": "button",
            "body": {"text": clip(body, 1024)},
            "action": {"buttons": [
                {"type": "reply", "reply": {"id": bid[:256], "title": clip(title, 20)}} for bid, title in buttons[:3]
            ]},
        }
        if header:
            inter["header"] = {"type": "text", "text": clip(header, 60)}
        if footer:
            inter["footer"] = {"text": clip(footer, 60)}
        return self._send(to, {"type": "interactive", "interactive": inter})

    def list(self, to: str, body: str, button: str, rows: list[tuple[str, str, str | None]],
             header: str | None = None, footer: str | None = None, section_title: str = "الخيارات"):
        """rows: [(id, title, description|None)] — 10 كحد أقصى."""
        inter = {
            "type": "list",
            "body": {"text": clip(body, 1024)},
            "action": {
                "button": clip(button, 20),
                "sections": [{
                    "title": clip(section_title, 24),
                    "rows": [
                        {"id": rid[:200], "title": clip(title, 24), **({"description": clip(desc, 72)} if desc else {})}
                        for rid, title, desc in rows[:10]
                    ],
                }],
            },
        }
        if header:
            inter["header"] = {"type": "text", "text": clip(header, 60)}
        if footer:
            inter["footer"] = {"text": clip(footer, 60)}
        return self._send(to, {"type": "interactive", "interactive": inter})

    def location_request(self, to: str, body: str):
        return self._send(to, {"type": "interactive", "interactive": {
            "type": "location_request_message",
            "body": {"text": clip(body, 1024)},
            "action": {"name": "send_location"},
        }})

    def cta_url(self, to: str, body: str, display_text: str, url: str, footer: str | None = None):
        inter = {
            "type": "cta_url",
            "body": {"text": clip(body, 1024)},
            "action": {"name": "cta_url", "parameters": {"display_text": clip(display_text, 20), "url": url}},
        }
        if footer:
            inter["footer"] = {"text": clip(footer, 60)}
        return self._send(to, {"type": "interactive", "interactive": inter})
