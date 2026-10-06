# محادثة البحث في بوت واتساب «فني» (تجريبي).
#
# نفس منطق بوت تلغرام ونفس قاعدة البيانات: المهنة ← الموقع (إرسال الموقع أو يدوي:
# دولة ← منطقة ← مدينة ← حي) ← النتائج بالتناوب العادل ← التواصل (يُخصم من فرص الفني
# المجانية، ونفس تنبيه «فوّتّ عميل» يوصل للفني على تلغرام).
#
# توفير التكلفة (واتساب يحاسب على الرسائل): النتائج ترسل كقائمة وحدة (9 فنيين بالرسالة)
# بدل بطاقة لكل فني، والتواصل رسالة وحدة فيها بطاقة الفني وزر يفتح محادثته.

import json
import re
import threading
from datetime import datetime, timedelta, timezone

import contact_links
import countries
import db
import i18n
import professions_repo as professions
from whatsapp_bot import top

TELEGRAM_REGISTER_URL = "https://t.me/FanniServiceBot?start=wa_bot"
RESULTS_PER_PAGE = 9
RESULTS_TTL_MIN = 24 * 60   # بعد يوم: القائمة القديمة ما تعطي أرقام، يلزم بحث جديد


def _now_minute() -> int:
    import time
    return int(time.time() // 60)
LIST_PAGE = 8          # عناصر كل صفحة بالقوائم الطويلة (+ صفّي التنقل = 10، حد واتساب)
SESSION_TTL = timedelta(hours=3)          # احتياطي لأي حالة ثانية
SEARCH_STEP_TTL = timedelta(minutes=3)    # بحث ما خلص (مهنة/موقع/حي) وتأخر 3 دقايق → يبدأ من جديد (طلب المالك)
RESULTS_TTL = timedelta(hours=24)         # بعد ظهور النتائج: صالحة يوم كامل («عرض المزيد» والتواصل)
REG_STEP_TTL = timedelta(hours=2)         # تسجيل فني ما خلص


def _ttl_for(state: str | None) -> timedelta:
    if state == "results":
        return RESULTS_TTL
    if (state or "").startswith("r_"):
        return REG_STEP_TTL
    if state in ("prof", "loc", "loc_reg", "loc_city", "dist"):
        return SEARCH_STEP_TTL
    return SESSION_TTL

_locks: dict[str, threading.Lock] = {}
_locks_guard = threading.Lock()


def _lock_for(wa_id: str) -> threading.Lock:
    with _locks_guard:
        return _locks.setdefault(wa_id, threading.Lock())


# ─────────────────────────── الجلسات (بقاعدة البيانات) ───────────────────────────

def ensure_tables():
    with db.get_conn() as conn:
        conn.execute(
            "CREATE TABLE IF NOT EXISTS wa_sessions (wa_id TEXT PRIMARY KEY, state TEXT, data TEXT, updated_at TEXT)"
        )


def _load(wa_id: str) -> tuple[str | None, dict]:
    with db.get_conn() as conn:
        row = conn.execute("SELECT state, data, updated_at FROM wa_sessions WHERE wa_id = ?", (wa_id,)).fetchone()
    if not row:
        return None, {}
    try:
        if datetime.now(timezone.utc) - datetime.fromisoformat(row["updated_at"]) > _ttl_for(row["state"]):
            return None, {}
    except Exception:
        return None, {}
    return row["state"], json.loads(row["data"] or "{}")


def _save(wa_id: str, state: str | None, data: dict):
    with db.get_conn() as conn:
        conn.execute(
            "INSERT INTO wa_sessions (wa_id, state, data, updated_at) VALUES (?, ?, ?, ?) "
            "ON CONFLICT(wa_id) DO UPDATE SET state=excluded.state, data=excluded.data, updated_at=excluded.updated_at",
            (wa_id, state, json.dumps(data, ensure_ascii=False), datetime.now(timezone.utc).isoformat()),
        )


def customer_id(wa_id: str) -> int:
    """رقم العميل بسجلات البحث/التواصل: سالب حتى ما يتعارض أبدًا مع أرقام حسابات تلغرام."""
    return -int(re.sub(r"\D", "", wa_id) or 0)


# ─────────────────────────── أدوات نصية ───────────────────────────

_TASHKEEL = re.compile(r"[ً-ْـ]")


def norm(s: str) -> str:
    s = _TASHKEEL.sub("", (s or "").strip().lower())
    return s.translate(str.maketrans({"أ": "ا", "إ": "ا", "آ": "ا", "ة": "ه", "ى": "ي"}))


# اختصارات (طلب المالك): s للبداية، x لإنهاء المحادثة، d لحذف البيانات — ونقبل نفس
# الزر بلوحة المفاتيح العربية (s=س، x=ء، d=ي) لو المستخدم ناسي يغيّر اللغة. والصفر/o تبقى للبداية.
RESET_WORDS = {norm(w) for w in [
    "s", "س", "o", "0", "٠", "ابدأ", "ابدا", "القائمة", "قائمة", "منيو", "menu", "start", "مرحبا", "هلا", "اهلا",
    "السلام عليكم", "السلام", "هاي", "hi", "hello", "الغاء", "إلغاء",
]}


DISAPPEAR_TIP = "🧹 هل تريد حذف المحادثة تلقائيًا؟ اضغط على اسم المحادثة في الأعلى ← «الرسائل المؤقتة» ← 24 ساعة"
END_WORDS = {norm(w) for w in ["x", "ء", "إنهاء", "انهاء", "انهي", "إنهاء المحادثة", "end"]}

DELETE_WORDS = {norm(w) for w in ["d", "ي", "حذف بياناتي", "احذف بياناتي", "delete my data"]}
MENU_FOOTER = "s للبداية • d لحذف بياناتك"
CHANNEL_URL = "https://whatsapp.com/channel/0029VbDnWZT11ulJLdQN7D3L"


def _ask_delete(api, wa_id):
    """حذف البيانات نهائي — نأكد قبل (حرف d ممكن ينكتب بالغلط)."""
    api.buttons(
        wa_id,
        "🗑️ هل تريد حذف بياناتك من «فنّي» نهائيًا؟\n\n"
        "سيُحذف ما يلي:\n• سجل عمليات البحث (ما بحثت عنه وأين)\n• سجل الفنيين الذين تواصلت معهم\n• محادثتك الحالية مع البوت\n\n"
        "ملاحظة: إذا كنت مسجّلًا كفنّي، فلن يُحذف تسجيلك كفنّي بهذا الإجراء (اطلب ذلك من الإدارة).",
        [("del:yes", "🗑️ نعم، احذف"), ("del:no", "لا، رجوع")],
    )
    return "menu", {}


def _delete_my_data(api, wa_id):
    """حذف بيانات العميل نهائيًا (وعد سياسة الخصوصية): الجلسة + سجلات بحثه وتواصله."""
    cid = customer_id(wa_id)
    with db.get_conn() as conn:
        conn.execute("DELETE FROM wa_sessions WHERE wa_id = ?", (wa_id,))
        conn.execute("DELETE FROM search_log WHERE customer_telegram_id = ?", (cid,))
        conn.execute("DELETE FROM contact_clicks WHERE customer_telegram_id = ?", (cid,))
    api.text(wa_id, "✅ تم حذف جميع بياناتك من «فني» نهائيًا. يمكنك العودة إلى استخدام الخدمة في أي وقت.")
    return None, {}


def _page(items: list, page: int, per: int = LIST_PAGE):
    if len(items) <= 10 and page == 0:
        return items, False, False
    start = page * per
    return items[start:start + per], page > 0, start + per < len(items)


# ─────────────────────────── نقطة الدخول ───────────────────────────

def handle(api, wa_id: str, name: str, msg: dict):
    with _lock_for(wa_id):
        state, data = _load(wa_id)
        state, data = _dispatch(api, wa_id, name, msg, state, data)
        _save(wa_id, state, data)


def _dispatch(api, wa_id, name, msg, state, data):
    mtype = msg.get("type")
    # فني مسجّل من واتساب: أي رسالة منه = تفاعل مع الإشعارات، ونتحقق لو عنده دفع اشتراك معلّق
    pro = db.get_professional_for_wa(wa_id)
    if pro:
        db.mark_notifications_responded(pro["id"])
        from whatsapp_bot import subscribe
        if subscribe.check_pending(api, wa_id, pro):
            return "menu", {}
        if mtype == "text" and norm((msg.get("text") or {}).get("body", "")) in {norm(w) for w in subscribe.PAID_WORDS}:
            if db.get_latest_pending_payment(pro["id"], "tap"):
                subscribe.not_paid_yet(api, wa_id)
                return state, data
    if mtype == "button":
        # زر «رد سريع» من رسالة قالب (مثل «💳 اشترك الآن» بإشعار خلصت فرصك)
        payload = (msg.get("button") or {}).get("payload", "")
        if payload.startswith("R:"):
            from whatsapp_bot import register
            return register.on_choice(api, wa_id, payload, state, data)
        return _welcome(api, wa_id, name)
    if mtype == "interactive":
        inter = msg.get("interactive", {})
        kind = inter.get("type")
        rid = (inter.get(kind) or {}).get("id", "")
        if rid.startswith("R:"):
            from whatsapp_bot import register
            return register.on_choice(api, wa_id, rid, state, data)
        return _on_choice(api, wa_id, name, rid, state, data)
    if mtype == "location":
        loc = msg.get("location", {})
        if (state or "").startswith("r_"):
            from whatsapp_bot import register
            return register.on_location(api, wa_id, data, float(loc.get("latitude")), float(loc.get("longitude")))
        if data.get("pid"):
            return _on_location(api, wa_id, float(loc.get("latitude")), float(loc.get("longitude")), data)
        return _welcome(api, wa_id, name)
    if mtype == "text":
        body = (msg.get("text") or {}).get("body", "")
        if norm(body) in DELETE_WORDS:
            return _ask_delete(api, wa_id)
        if norm(body) in END_WORDS:
            # «إنهاء» ألغيناه كزر (رسالة بلا فائدة = تكلفة) — لو أحد كتبه نصفّر الجلسة بصمت بدون رد
            return None, {}
        if state is None or norm(body) in RESET_WORDS:
            return _welcome(api, wa_id, name)
        if (state or "").startswith("r_"):
            from whatsapp_bot import register
            return register.on_text(api, wa_id, state, data, body)
        if state == "prof":
            return _match_profession(api, wa_id, body, data)
        if state == "dist" and data.get("city_id"):
            return _on_district_text(api, wa_id, body, data)
        if state == "loc_reg" and data.get("pid"):
            return _on_region_text(api, wa_id, body, data)
        if state == "loc_city" and data.get("pid"):
            return _on_city_text(api, wa_id, body, data)
        if state == "loc" and data.get("pid"):
            api.buttons(wa_id, "📍 أرسل موقعك (📎 ← الموقع)، أو اختر مدينتك يدويًا:", [("loc:manual", "🏙️ اختيار يدوي")])
            return state, data
        return _welcome(api, wa_id, name)
    # صورة/صوت/ملصق… → القائمة
    return _welcome(api, wa_id, name)


def _on_choice(api, wa_id, name, rid, state, data):
    p = rid.split(":")
    head = p[0]
    if head == "del":
        if p[1] == "yes":
            return _delete_my_data(api, wa_id)
        return _welcome(api, wa_id, name)
    if head == "m":
        if p[1] == "channel":
            api.cta_url(wa_id, "📢 تابع قناة «فنّي» على واتساب: عروض، مهن جديدة، ونصائح صيانة.", "فتح القناة", CHANNEL_URL)
            return state, data
        if p[1] == "search":
            return _ask_top(api, wa_id)
        if p[1] == "pro":
            from whatsapp_bot import register
            return register.start(api, wa_id)
        return _welcome(api, wa_id, name)
    if head == "top":
        return _ask_more(api, wa_id)
    if head == "dpg":
        return _ask_domain(api, wa_id, int(p[1]), data)
    if head == "dom":
        return _ask_profession(api, wa_id, p[1], 0, data)
    if head == "ppg":
        return _ask_profession(api, wa_id, p[1], int(p[2]), data)
    if head == "prof":
        return _select_profession(api, wa_id, p[1], data)
    if not data.get("pid") and head not in ("c", "n"):
        return _welcome(api, wa_id, name)   # زر قديم بعد انتهاء الجلسة
    if head == "loc":
        return _manual_start(api, wa_id, data)
    if head == "cty":
        return _choose_country(api, wa_id, p[1], 0, data)
    if head == "rpg":
        return _choose_country(api, wa_id, p[1], int(p[2]), data)
    if head == "reg":
        return _choose_region(api, wa_id, int(p[1]), 0, data)
    if head == "cpg":
        return _choose_region(api, wa_id, int(p[1]), int(p[2]), data)
    if head == "city":
        return _choose_city(api, wa_id, int(p[1]), 0, data)
    if head == "dipg":
        return _choose_city(api, wa_id, int(p[1]), int(p[2]), data)
    if head == "dist":
        if p[1] == "all":
            data.update(neighborhood=None, district_id=None)
        else:
            d = db.get_sa_district_by_id(int(p[1]))
            if not d:
                return _welcome(api, wa_id, name)
            data.update(neighborhood=d["name"], district_id=d["id"])
        return _run_search(api, wa_id, data)
    if head == "more":
        return _show_page(api, wa_id, data)
    if head in ("c", "n"):
        if len(p) > 2 and p[2].isdigit() and _now_minute() - int(p[2]) > RESULTS_TTL_MIN:
            api.buttons(wa_id, "⏰ نتائج هذا البحث قديمة (مضى عليها أكثر من يوم). ابدأ بحثًا جديدًا لترى الفنيين المتاحين الآن 👇",
                        [("m:search", "🔄 بحث جديد")])
            return "menu", {}
        return _contact(api, wa_id, int(p[1]), head == "n", state, data)
    return _welcome(api, wa_id, name)


# ─────────────────────────── الشاشات ───────────────────────────

def _welcome(api, wa_id, name):
    hi = f"أهلًا {name} 👋" if name else "أهلًا بك 👋"
    api.buttons(
        wa_id,
        f"{hi}\nهنا «فنّي» 🛠️ نصلك بأقرب فنّي: سبّاك، كهربائي، تكييف، نجّار، وأكثر من 60 مهنة "
        "في السعودية ومصر ودول الخليج.\n\n"
        # واتساب ما يسمح بزر رابط مع أزرار الرد بنفس الرسالة — الرابط بالنص يفتح القناة مباشرة بدون رسالة زيادة
        f"📢 قناة فنّي: {CHANNEL_URL}\n\nماذا تريد أن تفعل؟",
        [("m:search", "🔍 ابحث عن فني"), ("m:pro", "🛠️ أنا فني")],
        footer=MENU_FOOTER,
    )
    return "menu", {}


def _pro_info(api, wa_id, data):
    api.cta_url(
        wa_id,
        "مرحبًا بك 🙌 يتم التسجيل كفنّي حاليًا عن طريق بوت «فنّي» على تلغرام — مجانًا ويستغرق دقيقتين، "
        "وبعدها تظهر للعملاء الذين يبحثون هنا في واتساب وفي تلغرام.",
        "سجّل مجانًا", TELEGRAM_REGISTER_URL,
    )
    return "menu", data


def _ask_top(api, wa_id, note: str = ""):
    """أول شاشة بالبحث: الـ9 الأكثر طلبًا + «المزيد» (رسالة وحدة). note: سطر فوقها (مثل «ما لقيت…»)."""
    api.list(wa_id, f"{note}ما المهنة التي تبحث عنها؟ اختر من القائمة 👇\nأو اكتب اسمها مباشرة (مثل: سباك)",
             "اختر المهنة", top.top_rows(), header="🔍 بحث عن فني", section_title="الأكثر طلبًا")
    return "prof", {}  # بحث جديد = جلسة جديدة


def _ask_more(api, wa_id):
    text, ids = top.more_message("📋 باقي المهن (الأكثر طلبًا أولًا):")
    api.text(wa_id, text)
    return "prof", {"more": ids}


def _ask_domain(api, wa_id, page, data):
    domains = professions.get_domains("ar")
    items, prev, nxt = _page(domains, page)
    rows = [(f"dom:{d['id']}", d["name"], d["name"] if len(d["name"]) > 24 else None) for d in items]
    if nxt:
        rows.append((f"dpg:{page + 1}", "المزيد ⬅️", "باقي المجالات"))
    if prev:
        rows.append((f"dpg:{page - 1}", "➡️ السابق", None))
    api.list(wa_id, "اختر مجال المهنة من القائمة 👇\nأو اكتب اسم المهنة مباشرة (مثل: سباك، كهربائي، تكييف)",
             "اختر المجال", rows, header="🔍 بحث عن فني", section_title="المجالات")
    return "prof", {}  # بحث جديد = جلسة جديدة


def _ask_profession(api, wa_id, domain_id, page, data):
    profs = professions.get_professions_by_domain(domain_id, "ar")
    if not profs:
        return _ask_top(api, wa_id)
    per = 7 if len(profs) > 9 else 9      # 7 + (التالي/السابق/رجوع) = 10 حد واتساب
    start = page * per
    items = profs[start:start + per]
    rows = [(f"prof:{x['id']}", x["name"], x["name"] if len(x["name"]) > 24 else None) for x in items]
    if start + per < len(profs):
        rows.append((f"ppg:{domain_id}:{page + 1}", "المزيد ⬅️", f"باقي {len(profs) - start - per} مهنة"))
    if page > 0:
        rows.append((f"ppg:{domain_id}:{page - 1}", "➡️ السابق", None))
    rows.append(("dpg:0", "↩️ العودة إلى المجالات", None))
    api.list(wa_id, "اختر المهنة 👇", "اختر المهنة", rows, section_title="المهن")
    return "prof", data


def _all_professions():
    out = []
    for d in professions.get_domains("ar"):
        out.extend(professions.get_professions_by_domain(d["id"], "ar"))
    return out


def _match_profession(api, wa_id, text, data):
    n = top.to_number(text)
    if n is not None:
        if n == 10 and not data.get("more"):
            return _ask_more(api, wa_id)
        pid = top.pick_by_number(n, data.get("more"))
        if pid:
            return _select_profession(api, wa_id, pid, data)
        api.text(wa_id, "هذا الرقم غير موجود في القائمة 🤔 اكتب رقمًا صحيحًا أو اسم المهنة.")
        return "prof", data
    syn = top.synonym_profession(text)
    if syn and professions.get_profession(syn, "ar")[1]:
        db.log_search_term(text, syn, professions.get_profession(syn, "ar")[1]["name"], "search")
        return _select_profession(api, wa_id, syn, data)
    q = norm(text)
    words = [w for w in q.split() if len(w) >= 3] or [q]
    scored = []
    _all = _all_professions()
    for x in _all:
        n = norm(x["name"])
        if q == n:
            s = 0
        elif n.startswith(q) or q.startswith(n):
            s = 1
        elif q in n or n in q:
            s = 2
        elif any(w in n or n in w for w in words):
            s = 3
        else:
            continue
        scored.append((s, len(n), x))
    scored.sort(key=lambda t: (t[0], t[1]))
    matches = [x for _, _, x in scored]
    if len(matches) == 1 or (matches and scored[0][0] == 0):
        db.log_search_term(text, matches[0]["id"], matches[0]["name"], "search")
        return _select_profession(api, wa_id, matches[0]["id"], data)
    db.log_search_term(text, None, "، ".join(x["name"] for x in matches[:3]) or None, "search")
    if matches:
        rows = [(f"prof:{x['id']}", x["name"], x["name"] if len(x["name"]) > 24 else None) for x in matches[:9]]
        rows.append(("top:more", "📋 كل المهن", None))
        api.list(wa_id, f"وجدت أكثر من مهنة قريبة من «{clip_text(text)}» — اختر المهنة المقصودة 👇", "اختر المهنة", rows,
                 section_title="نتائج البحث")
        return "prof", data
    return _ask_top(api, wa_id, f"لم أجد مهنة باسم «{clip_text(text)}» 🤔\n\n")


def clip_text(s, n=30):
    s = (s or "").strip()
    return s if len(s) <= n else s[: n - 1] + "…"


def _select_profession(api, wa_id, pid, data):
    _, prof = professions.get_profession(pid, "ar")
    if not prof:
        return _ask_top(api, wa_id)
    data = {"pid": prof["id"], "pname": prof["name"]}
    api.location_request(
        wa_id, f"حسنًا ✅ «{prof['name']}»\n📍 أرسل موقعك من الزر أدناه، وسنعرض لك أقرب الفنيين إليك."
    )
    api.buttons(wa_id, "أو اختر مدينتك وحيّك يدويًا:", [("loc:manual", "🏙️ اختيار يدوي")])
    return "loc", data


def _on_location(api, wa_id, lat, lon, data):
    res = db.find_nearest_sa_city_and_district_by_coords(lat, lon, countries.enabled_codes("wa"))
    if not res or not res[0]:
        api.text(wa_id, "لم نتمكن من تحديد مدينتك من الموقع 😅 اختر يدويًا:")
        return _manual_start(api, wa_id, data)
    city, district = res
    data.update(city_id=city["id"], city=city["name"], country=city.get("country") or "SA",
                neighborhood=district["name"] if district else None,
                district_id=district["id"] if district else None)
    return _run_search(api, wa_id, data)


def _manual_start(api, wa_id, data):
    enabled = countries.enabled_codes("wa")
    if len(enabled) == 1:
        return _choose_country(api, wa_id, enabled[0], 0, data)
    rows = [(f"cty:{c}", countries.label(c, "ar"), None) for c in enabled[:10]]
    api.list(wa_id, "اختر الدولة 👇", "اختر الدولة", rows, section_title="الدول")
    return "loc", data


def send_numbered(api, wa_id, head: str, names: list[str] | None, tail: str, first_line: str | None = None,
                  groups: list[tuple] | None = None):
    """قائمة مرقمة برسالة وحدة (تتقسم لو تعدت حد واتساب) — بدل قوائم بصفحات كل صفحة برد.
    groups=[(عنوان، [أسماء])]: نفس الترقيم المتسلسل لكن تحت عناوين مجموعات."""
    groups = groups or [(None, names or [])]
    cur = head + "\n"
    if first_line:
        cur += "\n" + first_line
    chunks = []
    i = 0

    def add(line):
        nonlocal cur
        if len(cur) + len(line) + 1 > 3900:
            chunks.append(cur)
            cur = ""
        cur += "\n" + line

    for title, gnames in groups:
        if title:
            add("")
            add(f"*{title}*")
        for n in gnames:
            i += 1
            add(f"{i}. {n}")
    chunks.append(cur + "\n\n" + tail)
    for c in chunks:
        api.text(wa_id, c.strip())


def _number_in(text: str, items: list):
    n = top.to_number(text)
    if n is not None and 1 <= n <= len(items):
        return items[n - 1]
    return None


def _name_in(text: str, items: list[dict]):
    q = norm(re.sub(r"^\s*(حي|منطقة|مدينة)\s+", "", (text or "").strip()))
    if not q:
        return None
    exact = [x for x in items if norm(x["name"]) == q or norm(re.sub(r"^(حي|منطقة)\s+", "", x["name"])) == q]
    if exact:
        return exact[0]
    part = [x for x in items if q in norm(x["name"])]
    return part[0] if len(part) == 1 else None


def _choose_country(api, wa_id, code, page, data):
    regions = db.list_sa_regions(code)
    data["country"] = code
    if len(regions) == 1:
        return _choose_region(api, wa_id, regions[0]["id"], 0, data)
    data["nreg"] = [r["id"] for r in regions]
    send_numbered(api, wa_id, f"📍 مناطق {countries.name(code, 'ar')} 👇", [r["name"] for r in regions],
                  "✍️ اكتب *رقم* المنطقة.")
    return "loc_reg", data


def _on_region_text(api, wa_id, text, data):
    ids = data.get("nreg") or []
    rid = _number_in(text, ids)
    if rid is None:
        regions = [r for r in db.list_sa_regions(data.get("country", "SA")) if r["id"] in ids]
        hit = _name_in(text, regions)
        rid = hit["id"] if hit else None
    if rid is None:
        api.text(wa_id, f"اكتب رقمًا من 1 إلى {len(ids)} 🙏")
        return "loc_reg", data
    return _choose_region(api, wa_id, rid, 0, data)


def _choose_region(api, wa_id, region_id, page, data):
    cities = db.list_sa_major_cities_by_region(region_id)
    if len(cities) == 1:
        return _choose_city(api, wa_id, cities[0]["id"], 0, data)
    if not cities:
        api.text(wa_id, "لا توجد مدن مسجلة في هذه المنطقة حاليًا.")
        return _choose_country(api, wa_id, data.get("country", "SA"), 0, data)
    data["ncity"] = [c["id"] for c in cities]
    data["nreg_id"] = region_id
    send_numbered(api, wa_id, "🏙️ اختر المدينة 👇", [c["name"] for c in cities], "✍️ اكتب *رقم* المدينة.")
    return "loc_city", data


def _on_city_text(api, wa_id, text, data):
    ids = data.get("ncity") or []
    cid = _number_in(text, ids)
    if cid is None:
        cities = db.list_sa_major_cities_by_region(data.get("nreg_id")) if data.get("nreg_id") else []
        hit = _name_in(text, cities)
        cid = hit["id"] if hit else None
    if cid is None:
        api.text(wa_id, f"اكتب رقمًا من 1 إلى {len(ids)} 🙏")
        return "loc_city", data
    return _choose_city(api, wa_id, cid, 0, data)


def _choose_city(api, wa_id, city_id, page, data):
    city = db.get_sa_city_by_id(city_id)
    if not city:
        return _manual_start(api, wa_id, data)
    data.update(city_id=city["id"], city=city["name"], country=city.get("country") or data.get("country") or "SA")
    districts = db.list_sa_districts_by_city(city_id) if city.get("has_districts") else []
    if not districts:
        data.update(neighborhood=None, district_id=None)
        return _run_search(api, wa_id, data)
    if len(districts) <= 9:
        # أحياء قليلة: قائمة اختيار عادية (أسهل من الأرقام)
        rows = [("dist:all", f"🌍 كل {city['name']}"[:24], "كل أحياء المدينة")]
        rows += [(f"dist:{d['id']}", d["name"], d["name"] if len(d["name"]) > 24 else None)
                 for d in sorted(districts, key=lambda d: norm(re.sub(r"^حي\s+", "", d["name"])))]
        data["ndist"] = [d["id"] for d in districts]
        api.list(wa_id, f"📍 اختر الحي في {city['name']} 👇", "اختر الحي", rows, section_title="الأحياء")
        return "dist", data
    from whatsapp_bot import geo_groups
    groups = geo_groups.ordered_groups(city["id"], city["name"])
    if len(groups) == 1 and groups[0][0] is None:
        # مدينة صغيرة: ترتيب أبجدي بدون كلمة «حي» عشان العميل يلقى حيّه بسهولة
        groups = [(None, sorted(groups[0][1], key=lambda d: norm(re.sub(r"^حي\s+", "", d["name"]))))]
        head = f"📍 أحياء {city['name']} 👇"
    else:
        head = f"📍 أحياء {city['name']} — مقسّمة حسب المنطقة 👇"
    data["ndist"] = [d["id"] for _, ds in groups for d in ds]
    send_numbered(api, wa_id, head, None, "✍️ اكتب *رقم* حيّك (أو اسمه).", first_line=f"#. 🌍 كل {city['name']}",
                  groups=[(t, [d["name"] for d in ds]) for t, ds in groups])
    return "dist", data


def _on_district_text(api, wa_id, text, data):
    t = (text or "").strip()
    if t in ("#", "＃"):
        data.update(neighborhood=None, district_id=None)
        return _run_search(api, wa_id, data)
    did = _number_in(t, data.get("ndist") or [])
    if did is not None:
        d = db.get_sa_district_by_id(did)
        if d:
            data.update(neighborhood=d["name"], district_id=d["id"])
            return _run_search(api, wa_id, data)
    if top.to_number(t) is not None or not data.get("ndist"):
        if not data.get("ndist"):
            return _match_district(api, wa_id, t, data)
        api.text(wa_id, f"اكتب رقمًا من 1 إلى {len(data.get('ndist') or [])}، أو # لكل المدينة 🙏")
        return "dist", data
    # كتب اسم: لو حي واحد يطابق نبحث فيه مباشرة، وإلا نعرض أرقام المتشابهة (بدون إعادة القائمة)
    q = norm(re.sub(r"^\s*حي\s+", "", t))
    names = {d["id"]: d["name"] for d in db.list_sa_districts_by_city(data["city_id"])}
    exact = [did for did in data["ndist"] if norm(re.sub(r"^حي\s+", "", names.get(did, ""))) == q]
    hits = [(i, did) for i, did in enumerate(data["ndist"], 1) if len(q) >= 2 and q in norm(names.get(did, ""))]
    pick = exact[0] if exact else (hits[0][1] if len(hits) == 1 else None)
    if pick:
        data.update(neighborhood=names[pick], district_id=pick)
        return _run_search(api, wa_id, data)
    if hits:
        api.text(wa_id, f"🔎 الأحياء التي تحتوي على «{clip_text(t)}»:\n" + "\n".join(f"{i}. {names[d]}" for i, d in hits[:15])
                 + "\n\n✍️ اكتب *رقم* حيّك.")
    else:
        api.text(wa_id, f"✍️ اكتب *رقم* حيّك من القائمة أعلاه 👆 أو # لكل المدينة."
                 + (f"\nلم أجد حيًّا يحتوي على «{clip_text(t)}»." if len(q) >= 2 else ""))
    return "dist", data


def _match_district(api, wa_id, text, data):
    city_id = data.get("city_id")
    q = re.sub(r"^\s*حي\s+", "", (text or "").strip())
    matches = db.search_sa_districts(city_id, q, 9) if q else []
    if not matches and q:
        nq = norm(q)
        matches = [d for d in db.list_sa_districts_by_city(city_id) if nq in norm(d["name"])][:9]
    if len(matches) == 1:
        data.update(neighborhood=matches[0]["name"], district_id=matches[0]["id"])
        return _run_search(api, wa_id, data)
    if matches:
        rows = [(f"dist:{d['id']}", d["name"], d["name"] if len(d["name"]) > 24 else None) for d in matches]
        rows.append(("dist:all", f"🌍 كل {data.get('city', 'المدينة')}", None))
        api.list(wa_id, f"اختر حيّك من النتائج 👇", "اختر الحي", rows, section_title="الأحياء")
        return "dist", data
    api.text(wa_id, f"لم أجد حيًّا باسم «{clip_text(text)}» في {data.get('city', '')} 🤔 اكتب رقم الحي من القائمة، أو # لكل المدينة.")
    return "dist", data


# ─────────────────────────── البحث والنتائج ───────────────────────────

def _run_search(api, wa_id, data):
    pid, pname, city = data["pid"], data["pname"], data["city"]
    ids = db.search_active_professional_ids(pid, city, data.get("neighborhood"), data.get("district_id"),
                                            None, data.get("city_id"))
    db.log_search(customer_id(wa_id), pid, pname, city, data.get("neighborhood"), len(ids), data.get("country") or "SA")
    _notify_missed_async(dict(data))

    note = ""
    if not ids and data.get("district_id"):
        # ما فيه بالحي — نوسّع للمدينة كاملة بدل ما نرجّعه فاضي
        ids = db.search_active_professional_ids(pid, city, None, None, None, data.get("city_id"))
        if ids:
            nb = data["neighborhood"] if str(data["neighborhood"]).startswith("حي") else f"حي {data['neighborhood']}"
            note = f"لم نجد نتائج في {nb}، وهذه نتائج {city} كاملة 👇\n"
            data.update(neighborhood=None, district_id=None)
    if not ids:
        return _offer_nearby_cities(api, wa_id, data)
    data.update(ids=ids, shown=0, note=note)
    return _show_page(api, wa_id, data)


def _offer_nearby_cities(api, wa_id, data):
    """ما فيه فنيين بالمدينة: نعرض مباشرة أقرب المدن اللي فيها فنيين لنفس المهنة (قائمة وحدة)."""
    pname, city = data["pname"], data["city"]
    near = db.nearby_cities_with_professionals(data.get("city_id"), data["pid"], 8)
    if not near:
        api.buttons(
            wa_id,
            f"عذرًا، لا يوجد حاليًا فنيون في مهنة «{pname}» في {city} ولا في المدن القريبة منها 😔\n"
            "سجّلنا طلبك، ونعمل على إضافة فنيين في منطقتك قريبًا.",
            [("loc:manual", "🏙️ مدينة أخرى"), ("m:search", "🔄 بحث جديد")],
        )
        return "results", data
    rows = [(f"city:{c['id']}", c["name"], f"{c['count']} {'فني' if c['count'] == 1 else 'فنيين'} • {c['km']} كم")
            for c in near]
    rows.append(("loc:manual", "🏙️ مدينة أخرى", "اختيار يدوي"))
    rows.append(("m:search", "🔄 بحث جديد", None))
    api.list(wa_id, f"لا يوجد حاليًا فنيون في مهنة «{pname}» في {city} 😔\nهذه أقرب المدن التي يتوفر فيها فنيون 👇",
             "اختر المدينة", rows, section_title="مدن قريبة")
    return "loc", data


def _row_desc(p: dict) -> str:
    loc = "المدينة كاملة 🌍" if p.get("covers_whole_city") else (p.get("neighborhood") or p.get("city") or "")
    services = []
    try:
        services = json.loads(p.get("services_json") or "[]")
    except Exception:
        pass
    desc = f"📍 {loc}"
    if services:
        desc += " • " + "، ".join(services)
    return desc


def _show_page(api, wa_id, data):
    ids = data.get("ids") or []
    shown = data.get("shown", 0)
    page_ids = ids[shown:shown + RESULTS_PER_PAGE]
    if not page_ids:
        api.buttons(wa_id, "هؤلاء جميع الفنيين المتاحين 👌", [("m:search", "🔄 بحث جديد")])
        return "results", data
    people = db.get_professionals_by_ids(page_ids)
    db.mark_shown([p["id"] for p in people])
    remaining_after = len(ids) - shown - len(people)
    stamp = _now_minute()   # النتائج صالحة 24 ساعة (الرقم داخل معرّف الصف)
    rows = [((f"c:{p['id']}:{stamp}" if p.get("has_whatsapp", 1) else f"n:{p['id']}:{stamp}"), p["full_name"], _row_desc(p))
            for p in people]
    if remaining_after > 0:
        rows.append(("more", "⬇️ عرض المزيد", f"بقي {remaining_after} من الفنيين"))
    if shown == 0:
        body = (data.pop("note", "") or "") + (
            f"وجدنا {len(ids)} من فنيي «{data['pname']}» 👍\nاضغط «عرض الفنيين» واختر أحدهم، وسنفتح لك محادثته على واتساب مباشرة."
        )
    else:
        body = f"بقي {len(ids) - shown} من فنيي «{data['pname']}» 👇"
    api.list(wa_id, body, "عرض الفنيين", rows, header=f"🛠️ {data['pname']} — {data['city']}",
             footer="الترتيب بالتناوب العادل بين الفنيين", section_title="الفنيين")
    data["shown"] = shown + len(people)
    return "results", data


def _contact(api, wa_id, pid, call_only, state, data):
    from handlers.search import _professional_card_text  # نفس نص البطاقة اللي في تلغرام

    p = db.get_professional_by_id(pid)
    if not db.professional_can_receive_contacts(p):
        api.text(wa_id, "عذرًا، هذا الفني غير متاح حاليًا 🙏 اختر فنيًا آخر من القائمة، أو اكتب s لبدء بحث جديد.")
        return state or "results", data
    db.register_contact(pid, customer_id(wa_id))   # تُخصم فرصة (مرة وحدة لكل عميل/فني خلال 24 ساعة)
    card = _professional_card_text(p)
    if call_only or not p.get("has_whatsapp", 1):
        api.text(wa_id, f"{card}\n\n📞 هذا الرقم للاتصال فقط (بدون واتساب): {p['whatsapp_number']}")
        return state or "results", data
    searched = data.get("pid")
    prof_name = (p.get("profession2_name") if searched and searched == p.get("profession2_id") else None) \
        or data.get("pname") or p.get("profession_name")
    prefill = i18n.t("srch_wa_prefill_text", "ar", profession=prof_name)
    url = contact_links.wa_link(p["whatsapp_number"], prefill, p.get("country"))
    api.cta_url(wa_id, f"{card}\n\nاضغط الزر لفتح المحادثة معه 👇\n\n{DISAPPEAR_TIP}", "💬 فتح المحادثة", url,
                footer="يمكنك العودة إلى القائمة واختيار فنّي آخر")
    return state or "results", data


# ─────────────────────────── تنبيه «فيه عميل يدوّر عليك» للفنيين المخفيين ───────────────────────────

def _notify_missed_async(data: dict):
    """المنطق كله بـ nudges.py (تلغرام مجاني بدون حد، واتساب قوالب بحدود الدورة)."""
    import nudges

    nudges.notify_missed_async(data["pid"], data["pname"], data["city"], data.get("neighborhood"),
                               data.get("district_id"), data.get("city_id"))
