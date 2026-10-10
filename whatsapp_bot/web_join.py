# التسجيل من الموقع (fanniapp.com/join.html) — طلب المالك.
# الفني يعبّئ نموذجًا واحدًا (الاسم/المهنة/الخدمات/المدينة/الأحياء)، ثم يؤكّد برسالة واتساب جاهزة
# فيها رمز مثل FN-K7M4Q يرسلها من رقمه إلى البوت. الرسالة منه = نعرف رقمه الحقيقي (بلا رمز تحقق مدفوع)،
# والتسجيل يُحفظ بنفس دالة تسجيل واتساب (_save) — نفس البطاقة والتنبيهات وعرض ربط تلغرام.
# ما يُنشر أي تسجيل قبل التأكيد، والطلبات غير المؤكدة تُحذف بعد يومين.

import json
import re
import secrets
import time
from collections import defaultdict, deque
from datetime import datetime, timedelta, timezone

from flask import Blueprint, jsonify, request

import config
import countries
import db
import professions_repo as professions

bp = Blueprint("web_join", __name__)

CODE_RE = re.compile(r"FN-([A-Z0-9]{5})", re.I)
CODE_ALPHABET = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"   # بلا 0/O/1/I/L المتشابهة
VALID_HOURS = 48
MAX_DISTRICTS = 5
LANGS = ("ar", "en", "ur")

CONFIRM_TEXT = {
    "ar": "تأكيد تسجيلي في «فنّي»: {code}",
    "en": "Confirm my Fanni registration: {code}",
    "ur": "«فنی» میں میری رجسٹریشن کی تصدیق: {code}",
}


def ensure_table():
    with db.get_conn() as conn:
        conn.execute("""CREATE TABLE IF NOT EXISTS web_registrations (
            code TEXT PRIMARY KEY, data_json TEXT NOT NULL, lang TEXT NOT NULL DEFAULT 'ar',
            created_at TEXT NOT NULL, used_at TEXT, used_by TEXT)""")


def purge_old():
    cutoff = (datetime.now(timezone.utc) - timedelta(hours=VALID_HOURS)).isoformat()
    with db.get_conn() as conn:
        conn.execute("DELETE FROM web_registrations WHERE created_at < ?", (cutoff,))


# ─────────────────────────── حماية بسيطة من الإغراق ───────────────────────────

_hits: dict[str, deque] = defaultdict(deque)


def _rate_ok(limit: int = 15, window: int = 3600) -> bool:
    ip = (request.headers.get("X-Forwarded-For") or request.remote_addr or "?").split(",")[0].strip()
    q, now = _hits[ip], time.time()
    while q and now - q[0] > window:
        q.popleft()
    if len(q) >= limit:
        return False
    q.append(now)
    return True


def _lang() -> str:
    lg = (request.args.get("lang") or (request.get_json(silent=True) or {}).get("lang") or "ar").strip()
    return lg if lg in LANGS else "ar"


def _svc_name(ar: str, lang: str) -> str:
    if lang == "ar":
        return ar
    from whatsapp_bot.lang_texts import SERVICES
    return (SERVICES.get(ar) or {}).get(lang) or db.service_translation(ar, lang) or ar


def bot_number() -> str:
    return getattr(config, "WA_BOT_NUMBER", "") or "15556341384"


# ─────────────────────────── بيانات النموذج ───────────────────────────

@bp.get("/wa/api/join/meta")
def meta():
    lang = _lang()
    domains = []
    for d in professions.get_domains(lang):
        profs = [{"id": p["id"], "name": p["name"], "wide": p["allow_city_wide"],
                  "services": [{"ar": s, "name": _svc_name(s, lang)} for s in p["services"]]}
                 for p in professions.get_professions_by_domain(d["id"], lang)]
        if profs:
            domains.append({"id": d["id"], "name": d["name"], "professions": profs})
    ctry = [{"code": c, "name": countries.name(c, lang)} for c in countries.enabled_codes("wa")]
    return jsonify(domains=domains, countries=ctry, bot=bot_number(), max_districts=MAX_DISTRICTS)


@bp.get("/wa/api/join/regions")
def regions():
    c = request.args.get("country") or "SA"
    if c not in countries.enabled_codes("wa"):
        return jsonify(regions=[])
    return jsonify(regions=[{"id": r["id"], "name": r["name"]} for r in db.list_sa_regions(c)])


@bp.get("/wa/api/join/cities")
def cities():
    try:
        rid = int(request.args.get("region") or 0)
    except ValueError:
        rid = 0
    return jsonify(cities=[{"id": c["id"], "name": c["name"], "has_d": bool(c.get("has_districts"))}
                           for c in db.list_sa_major_cities_by_region(rid)])


@bp.get("/wa/api/join/districts")
def districts():
    try:
        cid = int(request.args.get("city") or 0)
    except ValueError:
        cid = 0
    return jsonify(districts=[{"id": d["id"], "name": d["name"]} for d in db.list_sa_districts_by_city(cid)])


# ─────────────────────────── الإرسال ───────────────────────────

ERR = {
    "name": {"ar": "اكتب اسمك بالحروف العربية أو الإنجليزية (حرفان على الأقل).",
             "en": "Write your name in Arabic or English letters (at least 2).",
             "ur": "اپنا نام عربی یا انگریزی حروف میں لکھیں (کم از کم 2 حروف)۔"},
    "prof": {"ar": "اختر مهنتك.", "en": "Choose your profession.", "ur": "اپنا پیشہ منتخب کریں۔"},
    "city": {"ar": "اختر مدينتك.", "en": "Choose your city.", "ur": "اپنا شہر منتخب کریں۔"},
    "dist": {"ar": "اختر حيًا واحدًا على الأقل (حتى 5)، أو «المدينة كاملة» إن كانت متاحة لمهنتك.",
             "en": "Choose at least one district (up to 5), or «Whole city» if available for your profession.",
             "ur": "کم از کم ایک محلہ منتخب کریں (زیادہ سے زیادہ 5)، یا «پورا شہر» اگر آپ کے پیشے کے لیے دستیاب ہو۔"},
    "busy": {"ar": "محاولات كثيرة، حاول بعد قليل.", "en": "Too many attempts, try again later.",
             "ur": "بہت زیادہ کوششیں، تھوڑی دیر بعد کوشش کریں۔"},
}


def _err(key: str, lang: str):
    return jsonify(ok=False, error=ERR[key][lang], field=key), 400


@bp.post("/wa/api/join/submit")
def submit():
    lang = _lang()
    if not _rate_ok():
        return _err("busy", lang)
    f = request.get_json(silent=True) or {}
    name = db.arabic_name(str(f.get("name") or ""))
    if not name:
        return _err("name", lang)

    dom1, p1 = professions.get_profession(str(f.get("pid") or ""), "ar")
    if not p1:
        return _err("prof", lang)
    dom2, p2 = professions.get_profession(str(f.get("p2id") or ""), "ar") if f.get("p2id") else (None, None)
    if p2 and p2["id"] == p1["id"]:
        p2 = None
    allowed = list(p1["services"]) + [s for s in ((p2 or {}).get("services") or []) if s not in p1["services"]]
    services = [s for s in (f.get("services") or []) if s in allowed]

    try:
        city = db.get_sa_city_by_id(int(f.get("city_id") or 0))
    except (TypeError, ValueError):
        city = None
    if not city or (city.get("country") or "SA") not in countries.enabled_codes("wa"):
        return _err("city", lang)
    has_d = bool(city.get("has_districts"))
    wide = bool(p1.get("allow_city_wide") or (p2 or {}).get("allow_city_wide"))
    whole = bool(f.get("whole")) and wide
    chosen: list[int] = []
    if has_d and not whole:
        valid = {d["id"] for d in db.list_sa_districts_by_city(city["id"])}
        for x in f.get("districts") or []:
            try:
                x = int(x)
            except (TypeError, ValueError):
                continue
            if x in valid and x not in chosen:
                chosen.append(x)
        if not chosen or len(chosen) > MAX_DISTRICTS:
            return _err("dist", lang)

    r = {"name": name, "pid": p1["id"], "pname": p1["name"], "domain": (dom1 or {}).get("name", ""),
         "services": services, "all_services": allowed, "wide": wide,
         "p2id": p2["id"] if p2 else None, "p2name": p2["name"] if p2 else None,
         "city": city["name"], "city_id": city["id"], "country": city.get("country") or "SA",
         "has_d": has_d, "whole": whole or not has_d, "chosen": chosen}
    ensure_table()
    purge_old()
    code = "FN-" + "".join(secrets.choice(CODE_ALPHABET) for _ in range(5))
    with db.get_conn() as conn:
        conn.execute("INSERT INTO web_registrations (code, data_json, lang, created_at) VALUES (?,?,?,?)",
                     (code, json.dumps(r, ensure_ascii=False), lang, datetime.now(timezone.utc).isoformat()))
    text = CONFIRM_TEXT[lang].format(code=code)
    from urllib.parse import quote
    return jsonify(ok=True, code=code, wa_url=f"https://wa.me/{bot_number()}?text={quote(text)}")


# ─────────────────────────── التأكيد من واتساب ───────────────────────────

def find_code(body: str) -> str | None:
    m = CODE_RE.search(body or "")
    return ("FN-" + m.group(1).upper()) if m else None


def confirm(api, wa_id: str, code: str):
    """رسالة الفني بالرمز: نحفظ تسجيله على رقمه (رقم المرسل) بنفس مسار تسجيل واتساب."""
    from whatsapp_bot import lang as wlang
    from whatsapp_bot import register
    from whatsapp_bot.lang import tr
    ensure_table()
    with db.get_conn() as conn:
        row = conn.execute("SELECT * FROM web_registrations WHERE code = ?", (code,)).fetchone()
    if row and row["lang"] in LANGS:
        wlang.save(wa_id, row["lang"])
        wlang.set_lang(row["lang"])
    if not row:
        api.text(wa_id, tr("لم نجد طلب التسجيل لهذا الرمز، أو انتهت صلاحيته (48 ساعة) 🙏\n"
                           "سجّل من جديد من الموقع، أو اضغط «🛠️ أنا فني» هنا."))
        return None, {}
    if row["used_at"]:
        p = db.get_professional_by_wa_id(register._digits(wa_id))
        if p:
            return register._status(api, wa_id, p)
        api.text(wa_id, tr("هذا الرمز استُخدم من قبل."))
        return None, {}
    p = db.get_professional_by_wa_id(register._digits(wa_id))
    if p and p.get("status") != db.STATUS_REJECTED:
        api.text(wa_id, tr("رقمك مسجّل مسبقًا في «فنّي» 👇"))
        return register._status(api, wa_id, p)
    r = json.loads(row["data_json"])
    state, data = register._save(api, wa_id, {"r": r})
    with db.get_conn() as conn:
        conn.execute("UPDATE web_registrations SET used_at=?, used_by=? WHERE code=?",
                     (datetime.now(timezone.utc).isoformat(), register._digits(wa_id), code))
        conn.execute("UPDATE professionals SET source='web' WHERE wa_id=? AND source='whatsapp'",
                     (register._digits(wa_id),))
    return state, data
