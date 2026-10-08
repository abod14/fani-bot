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
from whatsapp_bot import lang, top
from whatsapp_bot.lang import get_lang, tr, tr_service

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
REG_STEP_TTL = timedelta(minutes=3)       # تسجيل فني ما خلص وتأخر 3 دقايق → يبدأ من جديد (نفس البحث، طلب المالك)
OTP_STEP_TTL = timedelta(minutes=10)      # ينتظر رمز التحقق من صاحب الرقم الآخر (صلاحية الرمز)


LONG_LIST_TTL = timedelta(minutes=5)      # قائمة الأحياء الكاملة المرقمة (طويلة وتحتاج قراءة) — طلب المالك


def _ttl_for(state: str | None, data: dict | None = None) -> timedelta:
    data = data or {}
    if (state == "dist" and len(data.get("ndist") or []) > 9) or (state == "r_dist" and (data.get("r") or {}).get("dlist")):
        return LONG_LIST_TTL
    if state == "results":
        return RESULTS_TTL
    if state == "r_otp":
        return OTP_STEP_TTL
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
    lang.ensure_table()


def _load(wa_id: str) -> tuple[str | None, dict]:
    with db.get_conn() as conn:
        row = conn.execute("SELECT state, data, updated_at FROM wa_sessions WHERE wa_id = ?", (wa_id,)).fetchone()
    if not row:
        return None, {}
    try:
        data = json.loads(row["data"] or "{}")
        if datetime.now(timezone.utc) - datetime.fromisoformat(row["updated_at"]) > _ttl_for(row["state"], data):
            return None, {}
    except Exception:
        return None, {}
    return row["state"], data


def _save(wa_id: str, state: str | None, data: dict):
    with db.get_conn() as conn:
        conn.execute(
            "INSERT INTO wa_sessions (wa_id, state, data, updated_at) VALUES (?, ?, ?, ?) "
            "ON CONFLICT(wa_id) DO UPDATE SET state=excluded.state, data=excluded.data, updated_at=excluded.updated_at",
            (wa_id, state, json.dumps(data, ensure_ascii=False), datetime.now(timezone.utc).isoformat()),
        )


def hint_once(api, wa_id, state, data, send):
    """كلام غير مفهوم بخطوة تنتظر ضغطة/اختيار: نرد عليه مرة وحدة بس بهالخطوة، وبعدها سكوت
    (كل رد رسالة محسوبة). أي ضغطة زر/قائمة أو موقع يرجّع التنبيه."""
    if data.get("_hinted") == state:
        return state, data
    data["_hinted"] = state
    send()
    return state, data


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

# كتابة اسم اللغة بأي وقت تبدّل لغة البوت
LANG_WORDS = {
    **{norm(w): "en" for w in ("english", "انجليزي", "إنجليزي", "انقليزي")},
    **{norm(w): "ur" for w in ("urdu", "اردو", "اُردو")},
    **{norm(w): "ar" for w in ("عربي", "arabic", "العربية")},
}


# ─────────────────────────── عرض بلغة المستخدم ───────────────────────────

def join_list(items) -> str:
    """فاصل القوائم بالنص: «، » للعربي والأردو، «, » للإنجليزي."""
    return (", " if get_lang() == "en" else "، ").join(items)


def prof_name(pid, ar_name: str | None = "") -> str:
    """اسم المهنة للعرض بلغة المستخدم (المحفوظ بالجلسة/القاعدة يبقى عربي)."""
    if get_lang() == "ar" or not pid:
        return ar_name or ""
    _, p = professions.get_profession(pid, get_lang())
    return (p or {}).get("name") or ar_name or ""


def card_text(p: dict) -> str:
    """بطاقة الفني كما يراها العميل — العربي نفس بطاقة تلغرام بالضبط، وباقي اللغات مترجمة."""
    from handlers.search import _professional_card_text
    if get_lang() == "ar":
        return _professional_card_text(p)
    if p.get("covers_whole_city"):
        location = tr("{city} — المدينة كاملة 🌍", city=p["city"])
    else:
        location = p["city"] + (f" — {p['neighborhood']}" if p.get("neighborhood") else "")
    pname = prof_name(p.get("profession_id"), p.get("profession_name"))
    if p.get("profession2_name"):
        pname += " • " + prof_name(p.get("profession2_id"), p.get("profession2_name"))
    lines = [f"👷 {p['full_name']}", f"🛠️ {pname}"]
    services = p.get("services")
    if services is None and p.get("services_json"):
        try:
            services = json.loads(p["services_json"])
        except Exception:
            services = []
    if services:
        lines.append("📋 " + join_list(tr_service(s) for s in services))
    lines.append(f"📍 {location}")
    return "\n".join(lines)


def _ask_delete(api, wa_id):
    """حذف البيانات نهائي (يشمل تسجيل الفني) — نأكد قبل برسالة تنبيه (حرف d ممكن ينكتب بالغلط)."""
    pro = db.get_professional_by_wa_id(wa_id)
    items = []
    if pro:
        items.append(tr("• تسجيلك كفنّي ({name})، ولن تظهر للعملاء بعد الآن",
                        name=prof_name(pro.get("profession_id"), pro.get("profession_name") or "")))
        if pro.get("is_subscribed"):
            items.append(tr("• اشتراكك المدفوع الحالي، دون استرجاع المبلغ"))
    items += [tr("• سجل عمليات البحث (ما بحثت عنه وأين)"), tr("• سجل الفنيين الذين تواصلت معهم"),
              tr("• محادثتك الحالية مع البوت")]
    api.buttons(
        wa_id,
        tr("🗑️ هل تريد حذف بياناتك من «فنّي» نهائيًا؟\n\nسيُحذف ما يلي:\n{items}\n\n⚠️ لا يمكن التراجع عن هذا الإجراء.",
           items="\n".join(items)),
        [("del:yes", tr("🗑️ نعم، احذف")), ("del:no", tr("لا، رجوع"))],
    )
    return "menu", {}


def _delete_my_data(api, wa_id):
    """حذف نهائي (وعد سياسة الخصوصية): الجلسة + سجلات بحثه وتواصله + تسجيله كفني لو مسجّل من واتساب."""
    cid = customer_id(wa_id)
    db.delete_wa_professional(wa_id)
    with db.get_conn() as conn:
        conn.execute("DELETE FROM wa_sessions WHERE wa_id = ?", (wa_id,))
        conn.execute("DELETE FROM search_log WHERE customer_telegram_id = ?", (cid,))
        conn.execute("DELETE FROM contact_clicks WHERE customer_telegram_id = ?", (cid,))
    api.text(wa_id, tr("✅ تم حذف جميع بياناتك من «فنّي» نهائيًا. يمكنك العودة إلى استخدام الخدمة في أي وقت."))
    lang.forget(wa_id)
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
        lg = lang.load(wa_id)
        d = None
        if not lg and msg.get("type") == "text":
            d = lang.detect((msg.get("text") or {}).get("body", ""))
            if d:
                lang.save(wa_id, d)
        lang.set_lang(lg or d or "ar")
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
        data.pop("_hinted", None)
        # زر «رد سريع» من رسالة قالب (مثل «💳 اشترك الآن» بإشعار خلصت فرصك)
        payload = (msg.get("button") or {}).get("payload", "")
        if payload.startswith("R:"):
            from whatsapp_bot import register
            return register.on_choice(api, wa_id, payload, state, data)
        return _welcome(api, wa_id, name)
    if mtype == "interactive":
        data.pop("_hinted", None)
        inter = msg.get("interactive", {})
        kind = inter.get("type")
        if kind == "nfm_reply":
            # رد نموذج مربعات الاختيار (تسجيل الفني: الخدمات/الأحياء)
            from whatsapp_bot import register, wa_flows
            parsed = wa_flows.parse_reply(inter)
            if parsed:
                return register.on_flow(api, wa_id, parsed[0], parsed[1], state, data)
            return _welcome(api, wa_id, name)
        rid = (inter.get(kind) or {}).get("id", "")
        if rid.startswith("R:"):
            from whatsapp_bot import register
            return register.on_choice(api, wa_id, rid, state, data)
        return _on_choice(api, wa_id, name, rid, state, data)
    if mtype == "location":
        data.pop("_hinted", None)
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
        if norm(body) in LANG_WORDS:
            code = LANG_WORDS[norm(body)]
            lang.save(wa_id, code)
            lang.set_lang(code)
            return _welcome(api, wa_id, name)
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
            return hint_once(api, wa_id, state, data, lambda: api.buttons(
                wa_id, tr("📍 أرسل موقعك (📎 ← الموقع)، أو اختر مدينتك يدويًا:"), [("loc:manual", tr("🏙️ اختيار يدوي"))]))
        return _welcome(api, wa_id, name)
    # صورة/صوت/ملصق… → القائمة
    return _welcome(api, wa_id, name)


# أزرار خطوات البحث — لو ضغطها بعد انتهاء المهلة (الجلسة صفرت) نرجعه للقائمة الرئيسية بدل ما نكمّل
STEP_HEADS = {"prof", "top", "ppg", "dpg", "dom", "loc", "cty", "rpg", "reg", "cpg", "city", "dipg", "ncity", "dist"}


def _on_choice(api, wa_id, name, rid, state, data):
    p = rid.split(":")
    head = p[0]
    if state is None and head in STEP_HEADS:
        return _welcome(api, wa_id, name)
    if head == "del":
        if p[1] == "yes":
            return _delete_my_data(api, wa_id)
        return _welcome(api, wa_id, name)
    if head == "lang":
        code = p[1] if len(p) > 1 and p[1] in lang.LANGS else "ar"
        lang.save(wa_id, code)
        lang.set_lang(code)
        return _welcome(api, wa_id, name)
    if head == "m":
        if p[1] == "lang":
            return _ask_lang(api, wa_id)
        if p[1] == "channel":
            api.cta_url(wa_id, tr("📢 تابع قناة «فنّي» على واتساب: عروض، مهن جديدة، ونصائح صيانة."), tr("فتح القناة"),
                        CHANNEL_URL)
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
    if head == "ncity":
        c = db.get_sa_city_by_id(int(p[1]))
        if not c:
            return _welcome(api, wa_id, name)
        data.update(city_id=c["id"], city=c["name"], country=c.get("country") or data.get("country") or "SA",
                    neighborhood=None, district_id=None)
        data["from_near"] = 1
        return _run_search(api, wa_id, data)
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
            api.buttons(wa_id, tr("⏰ نتائج هذا البحث قديمة (مضى عليها أكثر من يوم). ابدأ بحثًا جديدًا لترى الفنيين المتاحين الآن 👇"),
                        [("m:search", tr("🔄 بحث جديد"))])
            return "menu", {}
        return _contact(api, wa_id, int(p[1]), head == "n", state, data)
    return _welcome(api, wa_id, name)


# ─────────────────────────── الشاشات ───────────────────────────

def _welcome(api, wa_id, name):
    hi = tr("أهلًا {name} 👋", name=name) if name else tr("أهلًا بك 👋")
    lang_btn = ("m:lang", "🌐 English / اردو") if get_lang() == "ar" else ("m:lang", "🌐 Language / اللغة")
    api.buttons(
        wa_id,
        # واتساب ما يسمح بزر رابط مع أزرار الرد بنفس الرسالة — الرابط بالنص يفتح القناة مباشرة بدون رسالة زيادة
        tr("{hi}\nهنا «فنّي» 🛠️ نصلك بأقرب فنّي: سبّاك، كهربائي، تكييف، نجّار، وأكثر من 60 مهنة "
           "في السعودية ومصر ودول الخليج.\n\n📢 قناة فنّي: {url}\n\nماذا تريد أن تفعل؟", hi=hi, url=CHANNEL_URL),
        [("m:search", tr("🔍 ابحث عن فني")), ("m:pro", tr("🛠️ أنا فني")), lang_btn],
        footer=tr(MENU_FOOTER),
    )
    return "menu", {}


def _ask_lang(api, wa_id):
    api.list(wa_id, "🌐 Choose your language / اختر لغتك / اپنی زبان منتخب کریں", "🌐 Language / اللغة",
             [("lang:ar", "العربية", None), ("lang:en", "English", None), ("lang:ur", "اردو", None)],
             section_title="Language / اللغة")
    return "menu", {}


def _pro_info(api, wa_id, data):
    api.cta_url(
        wa_id,
        tr("مرحبًا بك 🙌 يتم التسجيل كفنّي حاليًا عن طريق بوت «فنّي» على تلغرام — مجانًا ويستغرق دقيقتين، "
           "وبعدها تظهر للعملاء الذين يبحثون هنا في واتساب وفي تلغرام."),
        tr("سجّل مجانًا"), TELEGRAM_REGISTER_URL,
    )
    return "menu", data


def _ask_top(api, wa_id, note: str = ""):
    """أول شاشة بالبحث: الـ9 الأكثر طلبًا + «المزيد» (رسالة وحدة). note: سطر فوقها (مثل «ما لقيت…»)."""
    api.list(wa_id, tr("{note}ما المهنة التي تبحث عنها؟ اختر من القائمة 👇\nأو اكتب اسمها مباشرة (مثل: سباك)", note=note),
             tr("اختر المهنة"), top.top_rows(), header=tr("🔍 بحث عن فني"), section_title=tr("الأكثر طلبًا"))
    return "prof", {}  # بحث جديد = جلسة جديدة


def _ask_more(api, wa_id):
    text, ids = top.more_message(tr("📋 باقي المهن:"))
    api.text(wa_id, text)
    return "prof", {"more": ids}


def _ask_domain(api, wa_id, page, data):
    domains = professions.get_domains(get_lang())
    items, prev, nxt = _page(domains, page)
    rows = [(f"dom:{d['id']}", d["name"], d["name"] if len(d["name"]) > 24 else None) for d in items]
    if nxt:
        rows.append((f"dpg:{page + 1}", tr("المزيد ⬅️"), tr("باقي المجالات")))
    if prev:
        rows.append((f"dpg:{page - 1}", tr("➡️ السابق"), None))
    api.list(wa_id, tr("اختر مجال المهنة من القائمة 👇\nأو اكتب اسم المهنة مباشرة (مثل: سباك، كهربائي، تكييف)"),
             tr("اختر المجال"), rows, header=tr("🔍 بحث عن فني"), section_title=tr("المجالات"))
    return "prof", {}  # بحث جديد = جلسة جديدة


def _ask_profession(api, wa_id, domain_id, page, data):
    profs = professions.get_professions_by_domain(domain_id, get_lang())
    if not profs:
        return _ask_top(api, wa_id)
    per = 7 if len(profs) > 9 else 9      # 7 + (التالي/السابق/رجوع) = 10 حد واتساب
    start = page * per
    items = profs[start:start + per]
    rows = [(f"prof:{x['id']}", x["name"], x["name"] if len(x["name"]) > 24 else None) for x in items]
    if start + per < len(profs):
        rows.append((f"ppg:{domain_id}:{page + 1}", tr("المزيد ⬅️"), tr("باقي {n} مهنة", n=len(profs) - start - per)))
    if page > 0:
        rows.append((f"ppg:{domain_id}:{page - 1}", tr("➡️ السابق"), None))
    rows.append(("dpg:0", tr("↩️ العودة إلى المجالات"), None))
    api.list(wa_id, tr("اختر المهنة 👇"), tr("اختر المهنة"), rows, section_title=tr("المهن"))
    return "prof", data


def _all_professions(lg: str = "ar"):
    out = []
    for d in professions.get_domains(lg):
        out.extend(professions.get_professions_by_domain(d["id"], lg))
    return out


def match_scored(text: str) -> list[tuple]:
    """مطابقة اسم مهنة مكتوب: [(درجة، طول، المهنة بالعربي)] مرتبة — بالأسماء العربية، وكمان
    بأسماء لغة المستخدم (لو كتب Plumber أو پلمبر). المهنة الراجعة دائمًا بالاسم العربي (للحفظ والسجلات)."""
    q = norm(text)
    words = [w for w in q.split() if len(w) >= 3] or [q]
    lg = get_lang()
    local = {x["id"]: x["name"] for x in _all_professions(lg)} if lg != "ar" else {}
    scored = []
    for x in _all_professions():
        best = None
        for name in ([x["name"]] + ([local[x["id"]]] if local.get(x["id"]) else [])):
            n = norm(name)
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
            if best is None or (s, len(n)) < best:
                best = (s, len(n))
        if best is not None:
            scored.append((best[0], best[1], x))
    scored.sort(key=lambda t: (t[0], t[1]))
    return scored


def _match_profession(api, wa_id, text, data):
    n = top.to_number(text)
    if n is not None:
        if n == 10 and not data.get("more"):
            return _ask_more(api, wa_id)
        pid = top.pick_by_number(n, data.get("more"))
        if pid:
            return _select_profession(api, wa_id, pid, data)
        api.text(wa_id, tr("هذا الرقم غير موجود في القائمة 🤔 اكتب رقمًا صحيحًا أو اسم المهنة."))
        return "prof", data
    syn = top.synonym_profession(text)
    if syn and professions.get_profession(syn, "ar")[1]:
        db.log_search_term(text, syn, professions.get_profession(syn, "ar")[1]["name"], "search")
        return _select_profession(api, wa_id, syn, data)
    scored = match_scored(text)
    matches = [x for _, _, x in scored]
    if len(matches) == 1 or (matches and scored[0][0] == 0):
        db.log_search_term(text, matches[0]["id"], matches[0]["name"], "search")
        return _select_profession(api, wa_id, matches[0]["id"], data)
    db.log_search_term(text, None, "، ".join(x["name"] for x in matches[:3]) or None, "search")
    if matches:
        rows = []
        for x in matches[:9]:
            nm = prof_name(x["id"], x["name"])
            rows.append((f"prof:{x['id']}", nm, nm if len(nm) > 24 else None))
        rows.append(("top:more", tr("📋 كل المهن"), None))
        api.list(wa_id, tr("وجدت أكثر من مهنة قريبة من «{q}» — اختر المهنة المقصودة 👇", q=clip_text(text)),
                 tr("اختر المهنة"), rows, section_title=tr("نتائج البحث"))
        return "prof", data
    return _ask_top(api, wa_id, tr("لم أجد مهنة باسم «{q}» 🤔\n\n", q=clip_text(text)))


def clip_text(s, n=30):
    s = (s or "").strip()
    return s if len(s) <= n else s[: n - 1] + "…"


def _select_profession(api, wa_id, pid, data):
    _, prof = professions.get_profession(pid, "ar")
    if not prof:
        return _ask_top(api, wa_id)
    data = {"pid": prof["id"], "pname": prof["name"]}
    api.location_request(
        wa_id, tr("حسنًا ✅ «{name}»\n📍 أرسل موقعك من الزر أدناه، وسنعرض لك أقرب الفنيين إليك.",
                  name=prof_name(prof["id"], prof["name"]))
    )
    api.buttons(wa_id, tr("أو اختر مدينتك وحيّك يدويًا:"), [("loc:manual", tr("🏙️ اختيار يدوي"))])
    return "loc", data


def _on_location(api, wa_id, lat, lon, data):
    data.pop("from_near", None)
    res = db.find_nearest_sa_city_and_district_by_coords(lat, lon, countries.enabled_codes("wa"))
    if not res or not res[0]:
        api.text(wa_id, tr("لم نتمكن من تحديد مدينتك من الموقع 😅 اختر يدويًا:"))
        return _manual_start(api, wa_id, data)
    city, district = res
    data.update(city_id=city["id"], city=city["name"], country=city.get("country") or "SA",
                neighborhood=district["name"] if district else None,
                district_id=district["id"] if district else None)
    return _run_search(api, wa_id, data)


def _manual_start(api, wa_id, data):
    data.pop("from_near", None)
    enabled = countries.enabled_codes("wa")
    if len(enabled) == 1:
        return _choose_country(api, wa_id, enabled[0], 0, data)
    rows = [(f"cty:{c}", countries.label(c, get_lang()), None) for c in enabled[:10]]
    api.list(wa_id, tr("اختر الدولة 👇"), tr("اختر الدولة"), rows, section_title=tr("الدول"))
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
    send_numbered(api, wa_id, tr("📍 مناطق {country} 👇", country=countries.name(code, get_lang())),
                  [r["name"] for r in regions], tr("✍️ اكتب *رقم* المنطقة."))
    return "loc_reg", data


def _on_region_text(api, wa_id, text, data):
    ids = data.get("nreg") or []
    rid = _number_in(text, ids)
    if rid is None:
        regions = [r for r in db.list_sa_regions(data.get("country", "SA")) if r["id"] in ids]
        hit = _name_in(text, regions)
        rid = hit["id"] if hit else None
    if rid is None:
        return hint_once(api, wa_id, "loc_reg", data, lambda: api.text(wa_id, tr("اكتب رقمًا من 1 إلى {n} 🙏", n=len(ids))))
    return _choose_region(api, wa_id, rid, 0, data)


def _choose_region(api, wa_id, region_id, page, data):
    cities = db.list_sa_major_cities_by_region(region_id)
    if len(cities) == 1:
        return _choose_city(api, wa_id, cities[0]["id"], 0, data)
    if not cities:
        api.text(wa_id, tr("لا توجد مدن مسجلة في هذه المنطقة حاليًا."))
        return _choose_country(api, wa_id, data.get("country", "SA"), 0, data)
    data["ncity"] = [c["id"] for c in cities]
    data["nreg_id"] = region_id
    send_numbered(api, wa_id, tr("🏙️ اختر المدينة 👇"), [c["name"] for c in cities], tr("✍️ اكتب *رقم* المدينة."))
    return "loc_city", data


def _on_city_text(api, wa_id, text, data):
    ids = data.get("ncity") or []
    cid = _number_in(text, ids)
    if cid is None:
        cities = db.list_sa_major_cities_by_region(data.get("nreg_id")) if data.get("nreg_id") else []
        hit = _name_in(text, cities)
        cid = hit["id"] if hit else None
    if cid is None:
        return hint_once(api, wa_id, "loc_city", data, lambda: api.text(wa_id, tr("اكتب رقمًا من 1 إلى {n} 🙏", n=len(ids))))
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
        rows = [("dist:all", tr("🌍 كل {city}", city=city["name"])[:24], tr("كل أحياء المدينة"))]
        rows += [(f"dist:{d['id']}", d["name"], d["name"] if len(d["name"]) > 24 else None)
                 for d in sorted(districts, key=lambda d: norm(re.sub(r"^حي\s+", "", d["name"])))]
        data["ndist"] = [d["id"] for d in districts]
        api.list(wa_id, tr("📍 اختر الحي في {city} 👇", city=city["name"]), tr("اختر الحي"), rows,
                 section_title=tr("الأحياء"))
        return "dist", data
    from whatsapp_bot import geo_groups
    groups = geo_groups.ordered_groups(city["id"], city["name"])
    if len(groups) == 1 and groups[0][0] is None:
        # مدينة صغيرة: ترتيب أبجدي بدون كلمة «حي» عشان العميل يلقى حيّه بسهولة
        groups = [(None, sorted(groups[0][1], key=lambda d: norm(re.sub(r"^حي\s+", "", d["name"]))))]
        head = tr("📍 أحياء {city} 👇", city=city["name"])
    else:
        head = tr("📍 أحياء {city} — مقسّمة حسب المنطقة 👇", city=city["name"])
    data["ndist"] = [d["id"] for _, ds in groups for d in ds]
    send_numbered(api, wa_id, head, None, tr("✍️ اكتب *رقم* حيّك (أو اسمه)."),
                  first_line="#. " + tr("🌍 كل {city}", city=city["name"]),
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
        return hint_once(api, wa_id, "dist", data, lambda: api.text(
            wa_id, tr("اكتب رقمًا من 1 إلى {n}، أو # لكل المدينة 🙏", n=len(data.get("ndist") or []))))
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
        api.text(wa_id, tr("🔎 الأحياء التي تحتوي على «{q}»:\n{lines}\n\n✍️ اكتب *رقم* حيّك.", q=clip_text(t),
                           lines="\n".join(f"{i}. {names[d]}" for i, d in hits[:15])))
    else:
        api.text(wa_id, tr("✍️ اكتب *رقم* حيّك من القائمة أعلاه 👆 أو # لكل المدينة.")
                 + ("\n" + tr("لم أجد حيًّا يحتوي على «{q}».", q=clip_text(t)) if len(q) >= 2 else ""))
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
        rows.append(("dist:all", tr("🌍 كل {city}", city=data.get("city", tr("المدينة"))), None))
        api.list(wa_id, tr("اختر حيّك من النتائج 👇"), tr("اختر الحي"), rows, section_title=tr("الأحياء"))
        return "dist", data
    api.text(wa_id, tr("لم أجد حيًّا باسم «{q}» في {city} 🤔 اكتب رقم الحي من القائمة، أو # لكل المدينة.",
                       q=clip_text(text), city=data.get("city", "")))
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
            note = tr("لم نجد نتائج في {nb}، وهذه نتائج {city} كاملة 👇\n", nb=nb, city=city)
            data.update(neighborhood=None, district_id=None)
    if not ids:
        return _offer_nearby_cities(api, wa_id, data)
    data.update(ids=ids, shown=0, note=note)
    return _show_page(api, wa_id, data)


def _offer_nearby_cities(api, wa_id, data):
    """ما فيه فنيين بالمدينة: نشيّك أقرب 3 مدن حولها فقط (مو الدولة كلها) ونعرض منها اللي فيها
    فنيين كأزرار مع المسافة. ما فيه ولا وحدة — أو جاي أصلًا من وحدة منها — ننهي البحث نهائيًا."""
    pname, city = prof_name(data["pid"], data["pname"]), data["city"]
    near = [] if data.get("from_near") else db.nearest3_with_professionals(data.get("city_id"), data["pid"], 3)
    if not near:
        api.text(wa_id, tr("عذرًا، لا يوجد حاليًا فنيون في مهنة «{pname}» في {city} ولا في المدن القريبة منها 😔\n"
                           "سجّلنا طلبك، ونعمل على إضافة فنيين في منطقتك قريبًا.\n\n"
                           "للبحث من جديد اكتب s", pname=pname, city=city))
        return None, {}
    lines = "\n".join(tr("• {name} — تبعد {km} كم", name=c["name"], km=c["km"]) for c in near)
    api.buttons(wa_id, tr("لا يوجد حاليًا فنيون في مهنة «{pname}» في {city} 😔\n"
                          "يتوفر فنيون في هذه المدن القريبة 👇\n{lines}", pname=pname, city=city, lines=lines),
                [(f"ncity:{c['id']}", clip_text(c["name"], 20)) for c in near])
    return "loc", data


def _row_desc(p: dict) -> str:
    loc = tr("المدينة كاملة 🌍") if p.get("covers_whole_city") else (p.get("neighborhood") or p.get("city") or "")
    services = []
    try:
        services = json.loads(p.get("services_json") or "[]")
    except Exception:
        pass
    desc = f"📍 {loc}"
    if services:
        desc += " • " + join_list(tr_service(s) for s in services)
    return desc


def _show_page(api, wa_id, data):
    ids = data.get("ids") or []
    shown = data.get("shown", 0)
    page_ids = ids[shown:shown + RESULTS_PER_PAGE]
    if not page_ids:
        api.buttons(wa_id, tr("هؤلاء جميع الفنيين المتاحين 👌"), [("m:search", tr("🔄 بحث جديد"))])
        return "results", data
    people = db.get_professionals_by_ids(page_ids)
    db.mark_shown([p["id"] for p in people])
    remaining_after = len(ids) - shown - len(people)
    stamp = _now_minute()   # النتائج صالحة 24 ساعة (الرقم داخل معرّف الصف)
    rows = [((f"c:{p['id']}:{stamp}" if p.get("has_whatsapp", 1) else f"n:{p['id']}:{stamp}"), p["full_name"], _row_desc(p))
            for p in people]
    if remaining_after > 0:
        rows.append(("more", tr("⬇️ عرض المزيد"), tr("بقي {n} من الفنيين", n=remaining_after)))
    pname = prof_name(data["pid"], data["pname"])
    if shown == 0:
        body = (data.pop("note", "") or "") + tr(
            "وجدنا {n} من فنيي «{pname}» 👍\nاضغط «عرض الفنيين» واختر أحدهم، وسنفتح لك محادثته على واتساب مباشرة.",
            n=len(ids), pname=pname)
    else:
        body = tr("بقي {n} من فنيي «{pname}» 👇", n=len(ids) - shown, pname=pname)
    api.list(wa_id, body, tr("عرض الفنيين"), rows, header=f"🛠️ {pname} — {data['city']}",
             footer=tr("الترتيب بالتناوب العادل بين الفنيين"), section_title=tr("الفنيين"))
    data["shown"] = shown + len(people)
    return "results", data


def _contact(api, wa_id, pid, call_only, state, data):
    p = db.get_professional_by_id(pid)
    if not db.professional_can_receive_contacts(p):
        api.text(wa_id, tr("عذرًا، هذا الفني غير متاح حاليًا 🙏 اختر فنيًا آخر من القائمة، أو اكتب s لبدء بحث جديد."))
        return state or "results", data
    db.register_contact(pid, customer_id(wa_id))   # تُخصم فرصة (مرة وحدة لكل عميل/فني خلال 24 ساعة)
    card = card_text(p)   # العربي = نفس نص البطاقة اللي في تلغرام
    if call_only or not p.get("has_whatsapp", 1):
        api.text(wa_id, tr("{card}\n\n📞 هذا الرقم للاتصال فقط (بدون واتساب): {number}", card=card,
                           number=p["whatsapp_number"]))
        return state or "results", data
    searched = data.get("pid")
    if searched and searched == p.get("profession2_id") and p.get("profession2_name"):
        pr_name = prof_name(searched, p.get("profession2_name"))
    elif data.get("pname"):
        pr_name = prof_name(searched, data.get("pname"))
    else:
        pr_name = prof_name(p.get("profession_id"), p.get("profession_name"))
    # الرسالة الجاهزة للفني بلغة العميل (نفس ترجمات تلغرام)
    prefill = i18n.t("srch_wa_prefill_text", get_lang(), profession=pr_name)
    url = contact_links.wa_link(p["whatsapp_number"], prefill, p.get("country"))
    api.cta_url(wa_id, tr("{card}\n\nاضغط الزر لفتح المحادثة معه 👇\n\n{tip}", card=card, tip=tr(DISAPPEAR_TIP)),
                tr("💬 فتح المحادثة"), url, footer=tr("يمكنك العودة إلى القائمة واختيار فنّي آخر"))
    return state or "results", data


# ─────────────────────────── تنبيه «فيه عميل يدوّر عليك» للفنيين المخفيين ───────────────────────────

def _notify_missed_async(data: dict):
    """المنطق كله بـ nudges.py (تلغرام مجاني بدون حد، واتساب قوالب بحدود الدورة)."""
    import nudges

    nudges.notify_missed_async(data["pid"], data["pname"], data["city"], data.get("neighborhood"),
                               data.get("district_id"), data.get("city_id"))
