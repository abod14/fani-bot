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
    if state in ("prof", "loc", "dist"):
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


RESET_WORDS = {norm(w) for w in [
    "0", "٠", "ابدأ", "ابدا", "القائمة", "قائمة", "منيو", "menu", "start", "مرحبا", "هلا", "اهلا",
    "السلام عليكم", "السلام", "هاي", "hi", "hello", "الغاء", "إلغاء",
]}


DELETE_WORDS = {norm(w) for w in ["حذف بياناتي", "احذف بياناتي", "delete my data"]}


def _delete_my_data(api, wa_id):
    """حذف بيانات العميل نهائيًا (وعد سياسة الخصوصية): الجلسة + سجلات بحثه وتواصله."""
    cid = customer_id(wa_id)
    with db.get_conn() as conn:
        conn.execute("DELETE FROM wa_sessions WHERE wa_id = ?", (wa_id,))
        conn.execute("DELETE FROM search_log WHERE customer_telegram_id = ?", (cid,))
        conn.execute("DELETE FROM contact_clicks WHERE customer_telegram_id = ?", (cid,))
    api.text(wa_id, "✅ تم حذف كل بياناتك من «فني» نهائيًا. تقدر ترجع تستخدم الخدمة بأي وقت.")
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
            return _delete_my_data(api, wa_id)
        if state is None or norm(body) in RESET_WORDS:
            return _welcome(api, wa_id, name)
        if (state or "").startswith("r_"):
            from whatsapp_bot import register
            return register.on_text(api, wa_id, state, data, body)
        if state == "prof":
            return _match_profession(api, wa_id, body, data)
        if state == "dist" and data.get("city_id"):
            return _match_district(api, wa_id, body, data)
        if state == "loc" and data.get("pid"):
            api.buttons(wa_id, "📍 أرسل موقعك (📎 ← الموقع)، أو اختر مدينتك يدويًا:", [("loc:manual", "🏙️ اختيار يدوي")])
            return state, data
        return _welcome(api, wa_id, name)
    # صورة/صوت/ملصق… → القائمة
    return _welcome(api, wa_id, name)


def _on_choice(api, wa_id, name, rid, state, data):
    p = rid.split(":")
    head = p[0]
    if head == "m":
        if p[1] == "search":
            return _ask_domain(api, wa_id, 0, {})
        if p[1] == "pro":
            from whatsapp_bot import register
            return register.start(api, wa_id)
        return _welcome(api, wa_id, name)
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
            api.buttons(wa_id, "⏰ نتائج هذا البحث قديمة (أكثر من يوم). سوّ بحث جديد عشان تشوف الفنيين المتاحين الحين 👇",
                        [("m:search", "🔄 بحث جديد")])
            return "menu", {}
        return _contact(api, wa_id, int(p[1]), head == "n", state, data)
    return _welcome(api, wa_id, name)


# ─────────────────────────── الشاشات ───────────────────────────

def _welcome(api, wa_id, name):
    hi = f"أهلًا {name} 👋" if name else "أهلًا بك 👋"
    api.buttons(
        wa_id,
        f"{hi}\nمعك «فنّي» 🛠️ نوصلك بأقرب فني: سبّاك، كهربائي، تكييف، نجّار، وأكثر من 60 مهنة "
        "في السعودية ومصر ودول الخليج.\n\nوش تبي تسوي؟",
        [("m:search", "🔍 ابحث عن فني"), ("m:pro", "🛠️ أنا فني")],
        footer="اكتب 0 بأي وقت للرجوع للقائمة",
    )
    return "menu", {}


def _pro_info(api, wa_id, data):
    api.cta_url(
        wa_id,
        "حيّاك 🙌 التسجيل كفني حاليًا عن طريق بوت «فنّي» على تلغرام — مجاني وياخذ دقيقتين، "
        "وبعدها تظهر للعملاء اللي يبحثون هنا في واتساب وفي تلغرام.",
        "سجّل مجانًا", TELEGRAM_REGISTER_URL,
    )
    return "menu", data


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
        return _ask_domain(api, wa_id, 0, data)
    per = 7 if len(profs) > 9 else 9      # 7 + (التالي/السابق/رجوع) = 10 حد واتساب
    start = page * per
    items = profs[start:start + per]
    rows = [(f"prof:{x['id']}", x["name"], x["name"] if len(x["name"]) > 24 else None) for x in items]
    if start + per < len(profs):
        rows.append((f"ppg:{domain_id}:{page + 1}", "المزيد ⬅️", f"باقي {len(profs) - start - per} مهنة"))
    if page > 0:
        rows.append((f"ppg:{domain_id}:{page - 1}", "➡️ السابق", None))
    rows.append(("dpg:0", "↩️ رجوع للمجالات", None))
    api.list(wa_id, "اختر المهنة 👇", "اختر المهنة", rows, section_title="المهن")
    return "prof", data


def _all_professions():
    out = []
    for d in professions.get_domains("ar"):
        out.extend(professions.get_professions_by_domain(d["id"], "ar"))
    return out


def _match_profession(api, wa_id, text, data):
    q = norm(text)
    words = [w for w in q.split() if len(w) >= 3] or [q]
    scored = []
    for x in _all_professions():
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
        return _select_profession(api, wa_id, matches[0]["id"], data)
    if matches:
        rows = [(f"prof:{x['id']}", x["name"], x["name"] if len(x["name"]) > 24 else None) for x in matches[:9]]
        rows.append(("dpg:0", "📋 كل المجالات", None))
        api.list(wa_id, f"لقيت أكثر من مهنة قريبة من «{clip_text(text)}» — اختر المقصودة 👇", "اختر المهنة", rows,
                 section_title="نتائج البحث")
        return "prof", data
    api.text(wa_id, f"ما لقيت مهنة باسم «{clip_text(text)}» 🤔 اختر من المجالات:")
    return _ask_domain(api, wa_id, 0, data)


def clip_text(s, n=30):
    s = (s or "").strip()
    return s if len(s) <= n else s[: n - 1] + "…"


def _select_profession(api, wa_id, pid, data):
    _, prof = professions.get_profession(pid, "ar")
    if not prof:
        return _ask_domain(api, wa_id, 0, data)
    data = {"pid": prof["id"], "pname": prof["name"]}
    api.location_request(
        wa_id, f"تمام ✅ «{prof['name']}»\n📍 أرسل موقعك من الزر تحت، ونجيب لك أقرب الفنيين لك."
    )
    api.buttons(wa_id, "أو اختر مدينتك وحيّك يدويًا:", [("loc:manual", "🏙️ اختيار يدوي")])
    return "loc", data


def _on_location(api, wa_id, lat, lon, data):
    res = db.find_nearest_sa_city_and_district_by_coords(lat, lon, countries.enabled_codes())
    if not res or not res[0]:
        api.text(wa_id, "ما قدرنا نحدد مدينتك من الموقع 😅 اختر يدويًا:")
        return _manual_start(api, wa_id, data)
    city, district = res
    data.update(city_id=city["id"], city=city["name"], country=city.get("country") or "SA",
                neighborhood=district["name"] if district else None,
                district_id=district["id"] if district else None)
    return _run_search(api, wa_id, data)


def _manual_start(api, wa_id, data):
    enabled = countries.enabled_codes()
    if len(enabled) == 1:
        return _choose_country(api, wa_id, enabled[0], 0, data)
    rows = [(f"cty:{c}", countries.label(c, "ar"), None) for c in enabled[:10]]
    api.list(wa_id, "اختر الدولة 👇", "اختر الدولة", rows, section_title="الدول")
    return "loc", data


def _choose_country(api, wa_id, code, page, data):
    regions = db.list_sa_regions(code)
    data["country"] = code
    if len(regions) == 1:
        return _choose_region(api, wa_id, regions[0]["id"], 0, data)
    items, prev, nxt = _page(regions, page)
    rows = [(f"reg:{r['id']}", r["name"], r["name"] if len(r["name"]) > 24 else None) for r in items]
    if nxt:
        rows.append((f"rpg:{code}:{page + 1}", "المزيد ⬅️", None))
    if prev:
        rows.append((f"rpg:{code}:{page - 1}", "➡️ السابق", None))
    api.list(wa_id, f"اختر المنطقة في {countries.name(code, 'ar')} 👇", "اختر المنطقة", rows, section_title="المناطق")
    return "loc", data


def _choose_region(api, wa_id, region_id, page, data):
    cities = db.list_sa_major_cities_by_region(region_id)
    if len(cities) == 1:
        return _choose_city(api, wa_id, cities[0]["id"], 0, data)
    if not cities:
        api.text(wa_id, "ما فيه مدن مسجلة بهذي المنطقة حاليًا.")
        return _choose_country(api, wa_id, data.get("country", "SA"), 0, data)
    items, prev, nxt = _page(cities, page)
    rows = [(f"city:{c['id']}", c["name"], c["name"] if len(c["name"]) > 24 else None) for c in items]
    if nxt:
        rows.append((f"cpg:{region_id}:{page + 1}", "المزيد ⬅️", None))
    if prev:
        rows.append((f"cpg:{region_id}:{page - 1}", "➡️ السابق", None))
    api.list(wa_id, "اختر المدينة 👇", "اختر المدينة", rows, section_title="المدن")
    return "loc", data


def _choose_city(api, wa_id, city_id, page, data):
    city = db.get_sa_city_by_id(city_id)
    if not city:
        return _manual_start(api, wa_id, data)
    data.update(city_id=city["id"], city=city["name"], country=city.get("country") or data.get("country") or "SA")
    districts = db.list_sa_districts_by_city(city_id) if city.get("has_districts") else []
    if not districts:
        data.update(neighborhood=None, district_id=None)
        return _run_search(api, wa_id, data)
    per = 7
    start = page * per
    items = districts[start:start + per]
    rows = [("dist:all", f"🌍 كل {city['name']}", "كل أحياء المدينة")]
    rows += [(f"dist:{d['id']}", d["name"], d["name"] if len(d["name"]) > 24 else None) for d in items]
    if start + per < len(districts):
        rows.append((f"dipg:{city_id}:{page + 1}", "المزيد ⬅️", f"باقي {len(districts) - start - per} حي"))
    if page > 0:
        rows.append((f"dipg:{city_id}:{page - 1}", "➡️ السابق", None))
    api.list(wa_id, f"اختر الحي في {city['name']} 👇\nأو اكتب اسم حيّك مباشرة (مثل: النرجس)", "اختر الحي", rows,
             section_title="الأحياء")
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
    api.text(wa_id, f"ما لقيت حي باسم «{clip_text(text)}» في {data.get('city', '')} 🤔")
    return _choose_city(api, wa_id, city_id, 0, data)


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
            note = f"ما لقينا في {nb}، وهذي نتائج كل {city} 👇\n"
            data.update(neighborhood=None, district_id=None)
    if not ids:
        api.buttons(
            wa_id,
            f"ما فيه حاليًا فنيين «{pname}» في {city} 😔\nجرّب مدينة قريبة أو مهنة ثانية.",
            [("m:search", "🔄 بحث جديد"), ("loc:manual", "🏙️ مدينة ثانية")],
        )
        return "results", data
    data.update(ids=ids, shown=0, note=note)
    return _show_page(api, wa_id, data)


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
        api.buttons(wa_id, "هذولا كل الفنيين المتاحين 👌", [("m:search", "🔄 بحث جديد")])
        return "results", data
    people = db.get_professionals_by_ids(page_ids)
    db.mark_shown([p["id"] for p in people])
    remaining_after = len(ids) - shown - len(people)
    stamp = _now_minute()   # النتائج صالحة 24 ساعة (الرقم داخل معرّف الصف)
    rows = [((f"c:{p['id']}:{stamp}" if p.get("has_whatsapp", 1) else f"n:{p['id']}:{stamp}"), p["full_name"], _row_desc(p))
            for p in people]
    if remaining_after > 0:
        rows.append(("more", "⬇️ عرض المزيد", f"باقي {remaining_after} فني"))
    if shown == 0:
        body = (data.pop("note", "") or "") + (
            f"وجدنا {len(ids)} فني «{data['pname']}» 👍\nاضغط «عرض الفنيين» واختر واحد، ونفتح لك محادثته على واتساب مباشرة."
        )
    else:
        body = f"باقي {len(ids) - shown} فني «{data['pname']}» 👇"
    api.list(wa_id, body, "عرض الفنيين", rows, header=f"🛠️ {data['pname']} — {data['city']}",
             footer="الترتيب بالتناوب العادل بين الفنيين", section_title="الفنيين")
    data["shown"] = shown + len(people)
    return "results", data


def _contact(api, wa_id, pid, call_only, state, data):
    from handlers.search import _professional_card_text  # نفس نص البطاقة اللي في تلغرام

    p = db.get_professional_by_id(pid)
    if not db.professional_can_receive_contacts(p):
        api.text(wa_id, "عذرًا، هذا الفني غير متاح حاليًا 🙏 اختر فني ثاني من القائمة، أو اكتب 0 لبحث جديد.")
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
    api.cta_url(wa_id, f"{card}\n\nاضغط الزر لفتح المحادثة معه 👇", "💬 فتح المحادثة", url,
                footer="تقدر ترجع للقائمة وتختار فني ثاني")
    return state or "results", data


# ─────────────────────────── تنبيه «فوّتّ عميل» للفنيين (على تلغرام، مجاني) ───────────────────────────

def _notify_missed_async(data: dict):
    threading.Thread(target=_notify_missed, args=(data,), daemon=True).start()


def _notify_missed(data: dict):
    try:
        missed = db.find_subscription_missed_professionals(
            data["pid"], data["city"], data.get("neighborhood"), data.get("district_id"), data.get("city_id")
        )
        if not missed:
            return
        import asyncio

        from telegram import Bot, InlineKeyboardButton, InlineKeyboardMarkup

        import config
        from handlers.subscription import CB_SUBSCRIBE_MENU

        suffix = f" — {data['neighborhood']}" if data.get("neighborhood") else ""

        async def _send():
            sent = []
            async with Bot(config.BOT_TOKEN) as bot:
                for p in missed:
                    lang = db.get_user_language(p["telegram_user_id"])
                    try:
                        await bot.send_message(
                            chat_id=p["telegram_user_id"],
                            text=i18n.t("srch_missed_nudge", lang, profession=data["pname"], city=data["city"],
                                        district_suffix=suffix),
                            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton(
                                i18n.t("srch_missed_nudge_subscribe_btn", lang), callback_data=CB_SUBSCRIBE_MENU)]]),
                        )
                        sent.append(p["id"])
                    except Exception:
                        pass
            return sent

        sent = asyncio.run(_send())
        db.mark_search_nudge_sent(sent)
    except Exception:
        import logging
        logging.getLogger("fani.wa").exception("missed nudge failed")
