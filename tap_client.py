# عميل بسيط لواجهة Tap Payments — إنشاء شحنة دفع (Charge) والتحقق من حالتها.
# التحقق يصير بطلب المستخدم نفسه (زر "تحققت من الدفع")، بدون سيرفر webhook منفصل —
# هذا يناسب تشغيل البوت البسيط اللي مو محتاج استضافة برابط عام يستقبل إشعارات خارجية.

import requests

from config import TAP_SECRET_KEY, TAP_REDIRECT_URL

TAP_API_BASE = "https://api.tap.company/v2"

STATUS_PAID_VALUES = {"CAPTURED"}  # الحالة اللي تعني "الدفع تم فعليًا" بتوثيق Tap


class TapNotConfigured(Exception):
    pass


def _headers():
    if not TAP_SECRET_KEY:
        raise TapNotConfigured("TAP_SECRET_KEY غير مضبوط بملف .env")
    return {
        "Authorization": f"Bearer {TAP_SECRET_KEY}",
        "Content-Type": "application/json",
    }


def create_charge(amount_sar: float, professional_name: str, professional_id: int) -> dict:
    """
    ينشئ شحنة دفع مستضافة (hosted checkout) — Tap يرجّع رابط صفحة دفع يدعم
    مدى/فيزا/آبل باي، والعميل يكمل الدفع فيها مباشرة.
    يرجّع dict فيه على الأقل: id (charge id) و redirect_url (رابط صفحة الدفع).
    """
    payload = {
        "amount": amount_sar,
        "currency": "SAR",
        "threeDSecure": True,
        "save_card": False,
        "description": f"اشتراك بوت فني — {professional_name}",
        "customer": {
            "first_name": professional_name,
        },
        "source": {"id": "src_all"},  # يفتح كل طرق الدفع المتاحة (مدى/فيزا/ماستركارد/آبل باي)
        "redirect": {"url": TAP_REDIRECT_URL},
        "metadata": {"professional_id": str(professional_id)},
    }

    resp = requests.post(f"{TAP_API_BASE}/charges/", json=payload, headers=_headers(), timeout=20)
    resp.raise_for_status()
    data = resp.json()

    redirect_url = data.get("transaction", {}).get("url")
    return {"id": data["id"], "redirect_url": redirect_url, "status": data.get("status")}


def create_donation_charge(amount_sar: float, customer_telegram_id: int) -> dict:
    """نفس create_charge لكن لدعم/تبرّع اختياري من عميل (مو اشتراك فني) — الوصف
    والبيانات الوصفية تختلف (customer_telegram_id بدل professional_id)."""
    payload = {
        "amount": amount_sar,
        "currency": "SAR",
        "threeDSecure": True,
        "save_card": False,
        "description": "دعم بوت فني",
        "customer": {"first_name": "عميل بوت فني"},
        "source": {"id": "src_all"},
        "redirect": {"url": TAP_REDIRECT_URL},
        "metadata": {"customer_telegram_id": str(customer_telegram_id), "type": "donation"},
    }

    resp = requests.post(f"{TAP_API_BASE}/charges/", json=payload, headers=_headers(), timeout=20)
    resp.raise_for_status()
    data = resp.json()

    redirect_url = data.get("transaction", {}).get("url")
    return {"id": data["id"], "redirect_url": redirect_url, "status": data.get("status")}


def get_charge_status(charge_id: str) -> str:
    """يرجّع حالة الشحنة الحالية (مثل CAPTURED, INITIATED, DECLINED...)."""
    resp = requests.get(f"{TAP_API_BASE}/charges/{charge_id}", headers=_headers(), timeout=20)
    resp.raise_for_status()
    return resp.json().get("status", "")


def is_paid(status: str) -> bool:
    return status in STATUS_PAID_VALUES
