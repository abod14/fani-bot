# نظام تقييم الفنيين (طلب المالك):
# - بعد تواصل العميل مع فني بـ20 ساعة نسأله: هل تعاملت معه؟ ثم 1–5 نجوم.
#   (20 ساعة = داخل نافذة واتساب المجانية 24 ساعة. لو وافق الموعد وقت النوم
#   22:30–08:00 بتوقيت دولة العميل نقدّمه إلى 22:30 قبلها — ما نؤخّره أبدًا.)
# - عدة فنيين لنفس العميل → رسالة واحدة يختار منها مع من تعامل.
# - تقييم واحد لكل عميل لكل فني، ولا يقيّم إلا من تواصل فعلًا عبر البوت.
# - التقييم لا يؤثر أبدًا على ترتيب الظهور (التناوب العادل منفصل تمامًا — حتى إشعار آخر).
# - يظهر للعملاء بعد 3 تقييمات؛ تنبيه للمالك لو نزل تحت 2.5 بعد 5 تقييمات.
# - أزرار التقييم تبقى صالحة أسبوعًا (يقدر يقيّم لاحقًا لو ما رد وقتها).

import logging
import threading
import time
from datetime import datetime, timedelta, timezone

import db

log = logging.getLogger("fani.ratings")

DELAY_HOURS = 20
QUIET_START = (22, 30)      # بداية وقت النوم (محلي)
QUIET_END_HOUR = 8          # نهايته
WA_WINDOW = timedelta(hours=23, minutes=50)   # هامش أمان قبل انتهاء نافذة الـ24 ساعة
REPLY_VALID_DAYS = 7    # طلب المالك: رسالة التقييم صالحة أسبوعًا
MIN_TO_SHOW = 3
ALERT_MIN_COUNT = 5
ALERT_BELOW = 2.5

STARS = [(5, "⭐⭐⭐⭐⭐", "ممتاز"), (4, "⭐⭐⭐⭐", "جيد جدًا"), (3, "⭐⭐⭐", "جيد"),
         (2, "⭐⭐", "مقبول"), (1, "⭐", "غير مقبول")]

_TZ = {"SA": "Asia/Riyadh", "KW": "Asia/Kuwait", "QA": "Asia/Qatar", "BH": "Asia/Bahrain",
       "AE": "Asia/Dubai", "OM": "Asia/Muscat", "EG": "Africa/Cairo"}
_FIXED = {"AE": 4, "OM": 4, "EG": 2}   # احتياط لو ما توفرت قاعدة المناطق الزمنية (الباقي +3)
_PREFIX = [("966", "SA"), ("965", "KW"), ("974", "QA"), ("973", "BH"), ("971", "AE"), ("968", "OM"), ("20", "EG")]


# ─────────────────────────── الجداول ───────────────────────────

def ensure_tables():
    with db.get_conn() as conn:
        conn.execute("""CREATE TABLE IF NOT EXISTS ratings (
            id INTEGER PRIMARY KEY AUTOINCREMENT, professional_id INTEGER NOT NULL,
            customer_id INTEGER NOT NULL, stars INTEGER NOT NULL, created_at TEXT NOT NULL,
            UNIQUE (professional_id, customer_id))""")
        conn.execute("""CREATE TABLE IF NOT EXISTS rating_requests (
            id INTEGER PRIMARY KEY AUTOINCREMENT, professional_id INTEGER NOT NULL,
            customer_id INTEGER NOT NULL, contacted_at TEXT NOT NULL, due_at TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'pending', sent_at TEXT,
            UNIQUE (professional_id, customer_id))""")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_rr_due ON rating_requests (status, due_at)")
        conn.execute("CREATE TABLE IF NOT EXISTS wa_last_seen (wa_id TEXT PRIMARY KEY, at TEXT NOT NULL)")
        # طلب المالك: التقييم مربوط برقم جوال الفني — لو حذف حسابه ورجع تعود له تقييماته،
        # والمالك يقدر يصفّره من اللوحة (voided=1 = تقييم ملغى لا يُحسب).
        cols = {r[1] for r in conn.execute("PRAGMA table_info(ratings)").fetchall()}
        if "phone" not in cols:
            conn.execute("ALTER TABLE ratings ADD COLUMN phone TEXT")
        if "voided" not in cols:
            conn.execute("ALTER TABLE ratings ADD COLUMN voided INTEGER NOT NULL DEFAULT 0")
        for rid, num in conn.execute("SELECT r.id, p.whatsapp_number FROM ratings r JOIN professionals p "
                                     "ON p.id = r.professional_id WHERE r.phone IS NULL").fetchall():
            conn.execute("UPDATE ratings SET phone=? WHERE id=?", (phone_key(num or ""), rid))
        # الرقم يُخزَّن مشفّرًا (بصمة لا تُعكس) — نحوّل أي رقم قديم مخزّن بشكل مقروء
        for rid, ph in conn.execute("SELECT id, phone FROM ratings WHERE phone IS NOT NULL AND length(phone) != 64").fetchall():
            conn.execute("UPDATE ratings SET phone=? WHERE id=?", (phone_key(ph), rid))
        conn.execute("CREATE INDEX IF NOT EXISTS idx_ratings_phone ON ratings (phone, voided)")


def phone_key(phone: str) -> str:
    """بصمة مشفّرة لرقم الفني (SHA-256) — تربط تقييمه برقمه دون تخزين الرقم نفسه.
    طلب المالك: التقييم لا يُحذف أبدًا (حتى مع «احذف كل شيء») حتى لا يهرب الفني من تقييم سيئ بإعادة التسجيل."""
    import hashlib
    d = db._phone_digits(phone or "")
    return hashlib.sha256(f"fanni-rating:{d}".encode()).hexdigest() if d else ""


def pro_phone(professional_id: int) -> str:
    p = db.get_professional_by_id(professional_id) or {}
    return phone_key(p.get("whatsapp_number") or "")


def _rated_by_phone(conn, phone: str, customer_id: int) -> bool:
    return bool(phone) and bool(conn.execute(
        "SELECT 1 FROM ratings WHERE phone=? AND customer_id=? AND voided=0", (phone, customer_id)).fetchone())


def touch_wa(wa_id: str):
    """آخر رسالة من العميل بواتساب — نتأكد منها قبل الإرسال (نافذة الـ24 ساعة المجانية)."""
    with db.get_conn() as conn:
        conn.execute("INSERT INTO wa_last_seen (wa_id, at) VALUES (?, ?) ON CONFLICT(wa_id) DO UPDATE SET at=excluded.at",
                     (wa_id, datetime.now(timezone.utc).isoformat()))


# ─────────────────────────── التوقيت ───────────────────────────

def _tzinfo(country: str):
    try:
        from zoneinfo import ZoneInfo
        return ZoneInfo(_TZ.get(country, "Asia/Riyadh"))
    except Exception:
        return timezone(timedelta(hours=_FIXED.get(country, 3)))


def customer_country(customer_id: int) -> str:
    """دولة آخر بحث للعميل؛ وإلا من رمز رقم واتساب؛ وإلا السعودية."""
    with db.get_conn() as conn:
        row = conn.execute("SELECT country FROM search_log WHERE customer_telegram_id = ? ORDER BY id DESC LIMIT 1",
                           (customer_id,)).fetchone()
    if row and row[0]:
        return row[0]
    if customer_id < 0:
        digits = str(-customer_id)
        for pre, c in _PREFIX:
            if digits.startswith(pre):
                return c
    return "SA"


def compute_due(contacted_utc: datetime, country: str) -> datetime:
    """بعد 20 ساعة؛ لو وقعت بوقت النوم (22:30–08:00 محلي) تُقدَّم إلى 22:30 اللي قبلها."""
    tz = _tzinfo(country)
    due = (contacted_utc + timedelta(hours=DELAY_HOURS)).astimezone(tz)
    hm = (due.hour, due.minute)
    if hm >= QUIET_START:
        due = due.replace(hour=QUIET_START[0], minute=QUIET_START[1], second=0, microsecond=0)
    elif due.hour < QUIET_END_HOUR:
        due = (due - timedelta(days=1)).replace(hour=QUIET_START[0], minute=QUIET_START[1], second=0, microsecond=0)
    if due.astimezone(timezone.utc) < contacted_utc:   # احتياط (ما يصير عمليًا)
        due = contacted_utc.astimezone(tz)
    return due.astimezone(timezone.utc)


# ─────────────────────────── التسجيل ───────────────────────────

def enqueue(professional_id: int, customer_id: int):
    """يُستدعى عند تواصل جديد. ما نسأل عن فني سبق وقيّمه العميل أو سألناه عنه."""
    try:
        p = db.get_professional_by_id(professional_id) or {}
        if p.get("telegram_user_id") == customer_id:   # الفني نفسه
            return
        with db.get_conn() as conn:
            if conn.execute("SELECT 1 FROM ratings WHERE professional_id=? AND customer_id=?",
                            (professional_id, customer_id)).fetchone() \
                    or _rated_by_phone(conn, pro_phone(professional_id), customer_id):
                return
        now = datetime.now(timezone.utc)
        due = compute_due(now, customer_country(customer_id))
        with db.get_conn() as conn:
            conn.execute("INSERT OR IGNORE INTO rating_requests (professional_id, customer_id, contacted_at, due_at) "
                         "VALUES (?, ?, ?, ?)", (professional_id, customer_id, now.isoformat(), due.isoformat()))
    except Exception:
        log.exception("rating enqueue failed")


def save_rating(professional_id: int, customer_id: int, stars: int) -> bool:
    stars = max(1, min(5, int(stars)))
    phone = pro_phone(professional_id)
    with db.get_conn() as conn:
        if _rated_by_phone(conn, phone, customer_id):
            conn.execute("UPDATE rating_requests SET status='rated' WHERE professional_id=? AND customer_id=?",
                         (professional_id, customer_id))
            return False
        cur = conn.execute("INSERT OR IGNORE INTO ratings (professional_id, customer_id, stars, created_at, phone) "
                           "VALUES (?,?,?,?,?)",
                           (professional_id, customer_id, stars, datetime.now(timezone.utc).isoformat(), phone))
        conn.execute("UPDATE rating_requests SET status='rated' WHERE professional_id=? AND customer_id=?",
                     (professional_id, customer_id))
        new = cur.rowcount > 0
    if new:
        _maybe_alert(professional_id)
    return new


def summary(professional_ids: list[int]) -> dict[int, tuple[float, int]]:
    """متوسط وعدد التقييمات غير الملغاة — مجمّعة برقم جوال الفني (تشمل تقييماته من تسجيل سابق محذوف)."""
    if not professional_ids:
        return {}
    phones = {pid: pro_phone(pid) for pid in professional_ids}
    by_phone = summary_by_phones([ph for ph in phones.values() if ph])
    return {pid: by_phone[ph] for pid, ph in phones.items() if ph in by_phone}


def summary_by_phones(phones: list[str]) -> dict[str, tuple[float, int]]:
    phones = list({p for p in phones if p})
    if not phones:
        return {}
    q = ",".join("?" * len(phones))
    with db.get_conn() as conn:
        rows = conn.execute(f"SELECT phone, AVG(stars), COUNT(*) FROM ratings WHERE voided=0 AND phone IN ({q}) "
                            "GROUP BY phone", phones).fetchall()
    return {r[0]: (round(r[1], 1), r[2]) for r in rows}


def reset_for_professional(professional_id: int) -> int:
    """تصفير تقييم الفني من اللوحة (طلب المالك): نلغي تقييماته الحالية ويبدأ من جديد."""
    phone = pro_phone(professional_id)
    with db.get_conn() as conn:
        n = conn.execute("UPDATE ratings SET voided=1, professional_id = -id WHERE voided=0 AND (phone=? OR professional_id=?)",
                         (phone or "-", professional_id)).rowcount
    try:
        db.set_setting(f"rating_alert_{professional_id}", "")
    except Exception:
        pass
    return n


def forget_customer(customer_id: int, wa_id: str | None = None):
    """حذف بيانات العميل: نحذف طلبات التقييم المعلّقة، ونُبقي تقييماته للفنيين مجهولة الهوية
    (لا تُربط به بعد الحذف) حتى لا يختفي تقييم الفني بحذف عميل."""
    with db.get_conn() as conn:
        conn.execute("DELETE FROM rating_requests WHERE customer_id=?", (customer_id,))
        conn.execute("UPDATE ratings SET customer_id = -(9000000000000 + id) WHERE customer_id=?", (customer_id,))
        if wa_id:
            conn.execute("DELETE FROM wa_last_seen WHERE wa_id=?", (wa_id,))


def forget_professional(professional_id: int):
    """عند حذف الفني: طلبات التقييم المعلّقة عنه تُحذف (تقييماته تبقى مربوطة برقمه)."""
    with db.get_conn() as conn:
        conn.execute("DELETE FROM rating_requests WHERE professional_id=?", (professional_id,))


def badge(professional_id: int, min_count: int = MIN_TO_SHOW) -> str:
    """«⭐ 4.6 (12)» — فاضي لو التقييمات أقل من الحد."""
    s = summary([professional_id]).get(professional_id)
    if not s or s[1] < min_count:
        return ""
    return f"⭐ {s[0]:g} ({s[1]})"


def _maybe_alert(professional_id: int):
    s = summary([professional_id]).get(professional_id)
    if not s or s[1] < ALERT_MIN_COUNT or s[0] >= ALERT_BELOW:
        return
    if db.get_setting(f"rating_alert_{professional_id}", "") == "1":
        return
    p = db.get_professional_by_id(professional_id) or {}
    text = (f"⚠️ تقييم منخفض\n👷 {p.get('full_name', '')} — {p.get('profession_name', '')} ({p.get('city', '')})\n"
            f"⭐ {s[0]:g} من 5 ({s[1]} تقييمات)\nرقم الفني بلوحة التحكم: {professional_id}")
    _send_admin(text)
    try:
        db.set_setting(f"rating_alert_{professional_id}", "1")
    except Exception:
        pass


def _send_admin(text: str):
    def run():
        try:
            import asyncio

            from telegram import Bot

            import config

            async def go():
                async with Bot(config.BOT_TOKEN) as bot:
                    await bot.send_message(config.ADMIN_TELEGRAM_ID, text)
            asyncio.run(go())
        except Exception:
            log.exception("rating admin alert failed")
    threading.Thread(target=run, daemon=True).start()


# ─────────────────────────── اختيار الطلبات المستحقة ───────────────────────────

def _due_batches(channel: str) -> list[tuple[int, list[dict]]]:
    """طلبات حان موعدها مجمّعة لكل عميل (مع باقي طلباته المعلّقة — رسالة وحدة)."""
    now = datetime.now(timezone.utc).isoformat()
    sign = "<" if channel == "wa" else ">"
    with db.get_conn() as conn:
        custs = [r[0] for r in conn.execute(
            f"SELECT DISTINCT customer_id FROM rating_requests WHERE status='pending' AND due_at <= ? AND customer_id {sign} 0",
            (now,)).fetchall()]
        out = []
        for c in custs:
            rows = conn.execute("SELECT * FROM rating_requests WHERE status='pending' AND customer_id=? ORDER BY contacted_at",
                                (c,)).fetchall()
            out.append((c, [dict(r) for r in rows]))
    return out


def _mark(ids: list[int], status: str):
    if not ids:
        return
    q = ",".join("?" * len(ids))
    with db.get_conn() as conn:
        conn.execute(f"UPDATE rating_requests SET status=?, sent_at=? WHERE id IN ({q})",
                     [status, datetime.now(timezone.utc).isoformat(), *ids])


def get_request(req_id: int, customer_id: int) -> dict | None:
    with db.get_conn() as conn:
        r = conn.execute("SELECT * FROM rating_requests WHERE id=? AND customer_id=?", (req_id, customer_id)).fetchone()
    if not r:
        return None
    r = dict(r)
    try:
        if datetime.now(timezone.utc) - datetime.fromisoformat(r.get("sent_at") or r["contacted_at"]) > timedelta(days=REPLY_VALID_DAYS):
            return None
    except Exception:
        return None
    return r


def already_rated(professional_id: int, customer_id: int) -> bool:
    with db.get_conn() as conn:
        return bool(conn.execute("SELECT 1 FROM ratings WHERE professional_id=? AND customer_id=? AND voided=0",
                                 (professional_id, customer_id)).fetchone()) \
            or _rated_by_phone(conn, pro_phone(professional_id), customer_id)


def when_word(contacted_at: str, customer_id: int) -> str:
    tz = _tzinfo(customer_country(customer_id))
    try:
        c = datetime.fromisoformat(contacted_at).astimezone(tz).date()
    except Exception:
        return "أمس"
    return "اليوم" if c == datetime.now(tz).date() else "أمس"


def pro_label(professional_id: int) -> tuple[str, str]:
    p = db.get_professional_by_id(professional_id) or {}
    return p.get("full_name") or "", p.get("profession_name") or ""


# ─────────────────────────── واتساب ───────────────────────────

def wa_last_seen_ok(wa_id: str) -> bool:
    with db.get_conn() as conn:
        r = conn.execute("SELECT at FROM wa_last_seen WHERE wa_id=?", (wa_id,)).fetchone()
    if not r:
        return False
    try:
        return datetime.now(timezone.utc) - datetime.fromisoformat(r[0]) < WA_WINDOW
    except Exception:
        return False


def wa_send_due(api):
    from whatsapp_bot import lang as wlang
    from whatsapp_bot.lang import tr
    for cust, reqs in _due_batches("wa"):
        wa_id = str(-cust)
        ids = [r["id"] for r in reqs]
        if not wa_last_seen_ok(wa_id):
            _mark(ids, "expired")   # خارج النافذة المجانية — ما نرسل قالبًا مدفوعًا
            continue
        try:
            wlang.set_lang(wlang.load(wa_id) or "ar")
            _wa_ask(api, wa_id, cust, reqs, tr)
            _mark(ids, "sent")
        except Exception:
            log.exception("rating WA send failed")
            _mark(ids, "failed")


def _wa_ask(api, wa_id, cust, reqs, tr):
    when = tr(when_word(reqs[0]["contacted_at"], cust))
    if len(reqs) == 1:
        name, prof = pro_label(reqs[0]["professional_id"])
        api.buttons(wa_id, tr("مرحبًا 👋\nتواصلتَ {when} عبر «فنّي» مع {name} ({prof}).\nهل تعاملتَ معه؟",
                              when=when, name=name, prof=prof),
                    [(f"rt:y:{reqs[0]['id']}", tr("نعم")), (f"rt:n:{reqs[0]['id']}", tr("لا"))])
        return
    rows = []
    for r in reqs[:9]:
        name, prof = pro_label(r["professional_id"])
        rows.append((f"rt:y:{r['id']}", name, prof))
    rows.append((f"rt:n:{reqs[0]['id']}", tr("لم أتعامل مع أحد"), None))
    api.list(wa_id, tr("مرحبًا 👋\nتواصلتَ {when} عبر «فنّي» مع عدد من الفنيين.\nمع أيّهم تعاملت؟", when=when),
             tr("اختر الفني"), rows)


def wa_on_choice(api, wa_id: str, cust: int, parts: list[str]):
    """rt:y:<req> / rt:n:<req> / rs:<req>:<stars>"""
    from whatsapp_bot.lang import tr
    head = parts[0]
    try:
        req = get_request(int(parts[2] if head == "rt" else parts[1]), cust)
    except (ValueError, IndexError):
        req = None
    if not req:
        api.text(wa_id, tr("انتهت مدة هذا التقييم 🙏 إذا احتجت فنيًا في أي وقت، اكتب s."))
        return
    if head == "rt" and parts[1] == "n":
        api.text(wa_id, tr("شكرًا لك 🙏 إذا احتجت فنيًا في أي وقت، اكتب s."))
        return
    pid = req["professional_id"]
    if already_rated(pid, cust):
        api.text(wa_id, tr("سبق أن قيّمت هذا الفني، شكرًا لك 🌟"))
        return
    if head == "rt":
        name, _ = pro_label(pid)
        rows = [(f"rs:{req['id']}:{n}", f"{stars} {tr(label)}", None) for n, stars, label in STARS]
        api.list(wa_id, tr("كيف تقيّم عمل {name}؟", name=name), tr("اختر التقييم"), rows)
        return
    save_rating(pid, cust, int(parts[2]))
    api.text(wa_id, tr("شكرًا لك 🌟 تقييمك يساعد غيرك على اختيار الفني المناسب."))


def purge_daily():
    """مرة كل ساعة: حذف من انتهت مدته في قائمة «المحذوفون» (المدة يحددها المالك)."""
    try:
        today = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H")
        if db.get_setting("archive_purged_on", "") == today:
            return
        n = db.purge_expired_archive()
        db.set_setting("archive_purged_on", today)
        if n:
            log.info("purged %s expired deleted-professional archive rows", n)
    except Exception:
        log.exception("archive purge failed")


def start_wa_loop(api, interval: int = 300):
    def run():
        while True:
            try:
                wa_send_due(api)
            except Exception:
                log.exception("rating loop error")
            purge_daily()
            time.sleep(interval)
    threading.Thread(target=run, daemon=True).start()
