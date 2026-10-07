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

# اتصال دائم مع ميتا بدل فتح اتصال جديد لكل رسالة (يوفّر جزء من الثانية بكل رد).
# ميتا تقفل الاتصال الخامل بسرعة، فنخلي مدة الإبقاء قصيرة (20 ثانية) ونعيد المحاولة مرة
# وحدة لو لقينا الاتصال مقفول (كان يسبب إن البوت ما يرد بعد ما يسكت دقيقتين).
_client = httpx.Client(timeout=20, http2=False, limits=httpx.Limits(max_keepalive_connections=10, keepalive_expiry=20))
_RETRYABLE = (httpx.RemoteProtocolError, httpx.ConnectError, httpx.ReadError, httpx.WriteError, httpx.PoolTimeout)


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
        for attempt in (1, 2):
            try:
                r = _client.post(self.url, json=payload, headers={"Authorization": f"Bearer {self.token}"})
                if r.status_code >= 400:
                    log.warning("WA send failed %s: %s", r.status_code, r.text[:500])
                return r
            except _RETRYABLE as e:
                if attempt == 1:
                    log.info("WA connection dropped (%s) — retrying on a fresh connection", type(e).__name__)
                    continue
                log.exception("WA send error after retry")
                return None
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

    def template(self, to: str, name: str, body_params: "list[str]", button_payloads: "list[str] | None" = None,
                 lang: str = "ar"):
        """رسالة قالب (مدفوعة) — الطريقة الوحيدة نبدأ فيها محادثة مع شخص ما راسلنا آخر 24 ساعة."""
        components = []
        if body_params:
            components.append({"type": "body", "parameters": [{"type": "text", "text": clip(p, 60)} for p in body_params]})
        for i, payload in enumerate(button_payloads or []):
            components.append({"type": "button", "sub_type": "quick_reply", "index": str(i),
                               "parameters": [{"type": "payload", "payload": payload}]})
        return self._send(to, {"type": "template", "template": {
            "name": name, "language": {"code": lang}, "components": components}})

    def auth_code(self, to: str, name: str, code: str, lang: str = "ar"):
        """قالب رمز تحقق (AUTHENTICATION) مع زر «نسخ الرمز» — مدفوع دائمًا."""
        return self._send(to, {"type": "template", "template": {
            "name": name, "language": {"code": lang}, "components": [
                {"type": "body", "parameters": [{"type": "text", "text": code}]},
                {"type": "button", "sub_type": "url", "index": "0", "parameters": [{"type": "text", "text": code}]},
            ]}})

    def cta_url(self, to: str, body: str, display_text: str, url: str, footer: str | None = None):
        inter = {
            "type": "cta_url",
            "body": {"text": clip(body, 1024)},
            "action": {"name": "cta_url", "parameters": {"display_text": clip(display_text, 20), "url": url}},
        }
        if footer:
            inter["footer"] = {"text": clip(footer, 60)}
        return self._send(to, {"type": "interactive", "interactive": inter})
