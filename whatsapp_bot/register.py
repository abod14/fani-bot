# تسجيل الفني من بوت واتساب (بدون تلغرام).
#
# الخطوات (مختصرة لأن واتساب ما يتحمل قوائم طويلة):
#   الاسم ← المهنة (قائمة مجالات أو كتابة) ← الخدمات (اختياري) ← مشاركة الموقع فقط
#   ← تأكيد «السعودية / جدة» ← أقرب الأحياء (وإذا ما فيها حيّه: «المزيد» يجيب اللي بعدها)
#   ← مراجعة وتأكيد ← حفظ بنفس قاعدة بيانات تلغرام ← عرض ربط الحساب بتلغرام.
#
# الفني يُحفظ بـ telegram_user_id = -رقم واتساب (لين يربط بتلغرام) و wa_id = رقمه.

import json
import re
import threading

import contact_links
import countries
import db
import professions_repo as professions
from whatsapp_bot import top

TELEGRAM_BOT = "FanniServiceBot"


def _flow():
    from whatsapp_bot import flow  # تجنّب الاستيراد الدائري
    return flow


def _digits(wa_id: str) -> str:
    return re.sub(r"\D", "", wa_id or "")


# ─────────────────────────── البداية ───────────────────────────

def start(api, wa_id):
    """زر «أنا فني»: لو مسجّل يشوف حالته، وإلا نبدأ التسجيل."""
    me = _digits(wa_id)
    p = db.get_professional_by_wa_id(me)
    # المالك/المسوّق يسجّل فنيين آخرين — ما نوقفه عند حالته هو
    if p and p.get("status") != db.STATUS_REJECTED and not db.is_wa_registrar(me):
        return _status(api, wa_id, p)
    api.text(wa_id, "مرحبًا بك 🙌 سنسجّلك في «فنّي» مجانًا خلال دقيقة، لتظهر للعملاء في واتساب وتلغرام.\n\n"
                    "✍️ اكتب اسمك (الاسم الذي سيظهر للعملاء):")
    return "r_name", {"r": {}}


def _status(api, wa_id, p, extra=""):
    from handlers.search import _professional_card_text

    limit = int(db.get_setting("free_contacts_limit", str(db.FREE_CONTACTS_LIMIT))) + (p.get("bonus_contacts") or 0)
    line = "✅ مشترك — تظهر لجميع العملاء دون حد" if p.get("is_subscribed") else \
        f"📊 فرص التواصل المجانية: استخدمت {p.get('free_contacts_used', 0)} من {limit}"
    if not p.get("is_subscribed") and (p.get("free_contacts_used") or 0) >= limit:
        line += "\n\n⚠️ انتهت فرصك المجانية — رقمك لا يظهر للعملاء حاليًا. اضغط «💳 اشترك» أدناه لتعود إلى الظهور."
    buttons = [("m:search", "🔍 ابحث عن فني")]
    if not p.get("is_subscribed"):
        buttons.insert(0, ("R:sub", "💳 اشترك"))
    if not (p.get("telegram_user_id") or 0) > 0:
        buttons.insert(0, ("R:tg:yes", "🔗 اربط بتلغرام"))
    api.buttons(wa_id, f"أنت مسجّل في «فنّي» 👌\n\n{_professional_card_text(p)}\n\n{line}{extra}", buttons)
    return "menu", {}


# ─────────────────────────── النصوص ───────────────────────────

def on_text(api, wa_id, state, data, body):
    r = data.setdefault("r", {})
    if state == "r_name":
        name = re.sub(r"\s+", " ", (body or "").strip())
        if not (2 <= len(name) <= 40):
            return _flow().hint_once(api, wa_id, state, data,
                                     lambda: api.text(wa_id, "اكتب اسمًا يتراوح طوله بين حرفين و40 حرفًا 🙏"))
        r["name"] = name
        return _ask_number(api, wa_id, data)
    if state == "r_num":
        return _flow().hint_once(api, wa_id, state, data, lambda: _ask_number(api, wa_id, data))
    if state == "r_phone":
        return _on_phone_text(api, wa_id, data, body)
    if state == "r_otp":
        return _on_otp_text(api, wa_id, data, body)
    if state == "r_prof":
        return _match_profession(api, wa_id, body, data)
    if state == "r_dist":
        b = (body or "").strip()
        if b in WHOLE_CITY_WORDS or _flow().norm(b) in {_flow().norm(w) for w in WHOLE_CITY_WORDS}:
            if r.get("wide"):
                r["whole"] = True
                return _confirm(api, wa_id, data)
            api.text(wa_id, f"🌍 خيار «المدينة كاملة» متاح للمهن النادرة فقط. اكتب أرقام أحيائك (حتى {MAX_DISTRICTS}) من القائمة 👆")
            return "r_dist", data
        if not r.get("dlist"):
            # قائمة أقرب الأحياء (مو المرقمة): اسم حي واضح ← نضيفه، غير كذا تنبيه مرة وحدة
            return _district_text_in_list(api, wa_id, data, b)
        picked = _pick_district_numbers(api, wa_id, data, body)
        if picked:
            return picked
        return _hint_district_numbers(api, wa_id, data, body)
    if state in ("r_loc", "r_locok"):
        return _flow().hint_once(api, wa_id, "r_loc", data, lambda: api.location_request(
            wa_id, "📍 شارك موقعك من الزر أدناه (أو 📎 ← الموقع) لنحدد مدينتك وأحياءك."))
    if state == "r_svc":
        return _flow().hint_once(api, wa_id, state, data, lambda: api.text(
            wa_id, "👆 اضغط زر «اختر الخدمات» في الرسالة أعلاه."))
    if state == "r_confirm":
        return _flow().hint_once(api, wa_id, state, data, lambda: api.text(
            wa_id, "👆 اضغط «✅ تأكيد التسجيل» في الرسالة أعلاه، أو «✏️ البدء من جديد»."))
    # بعد انتهاء التسجيل (أو أي خطوة ما تنتظر كتابة): أي كتابة = القائمة الرئيسية بدل السكوت
    p = db.get_professional_by_wa_id(_digits(wa_id))
    return _flow()._welcome(api, wa_id, (p or {}).get("full_name") or r.get("name") or "")


# ─────────────────────────── رقم الفني (هذا الجوال أو رقم آخر) ───────────────────────────

OTP_TTL = 600          # صلاحية الرمز بالثواني
OTP_TRIES = 3          # محاولات إدخال الرمز
OTP_DAILY = 3          # رموز في اليوم لكل مرسل (كل رمز رسالة مدفوعة)
_CC = ("966", "971", "965", "974", "973", "968", "20")


def tech_phone(r: dict, wa_id: str) -> str:
    """رقم الفني اللي ينحفظ ويظهر للعملاء: الرقم الآخر لو اختاره، وإلا رقم المرسل."""
    return r.get("phone") or _digits(wa_id)


def norm_phone(text: str, sender: str) -> str | None:
    """يحوّل الرقم المكتوب لصيغة دولية (أرقام فقط): 0501234567 ← 966501234567 حسب دولة المرسل."""
    t = (text or "").translate(str.maketrans("٠١٢٣٤٥٦٧٨٩۰۱۲۳۴۵۶۷۸۹", "01234567890123456789"))
    t = re.sub(r"\D", "", t)
    if t.startswith("00"):
        t = t[2:]
    if t.startswith("0"):
        cc = next((c for c in _CC if sender.startswith(c)), "966")
        t = cc + t[1:]
    elif len(t) == 9 and t.startswith("5"):
        t = "966" + t
    return t if 10 <= len(t) <= 15 else None


def otp_enabled() -> bool:
    """رمز التحقق للجمهور يشتغل بس بعد ما يتفعّل قالب المصادقة (يحتاج توثيق النشاط التجاري بميتا) —
    المالك يفعّله من صفحة «المسوّقون» باللوحة."""
    return db.get_setting("wa_otp_enabled", "0") == "1"


def _ask_number(api, wa_id, data):
    me = _digits(wa_id)
    if not db.is_wa_registrar(me) and not otp_enabled():
        # الجمهور قبل تفعيل رمز التحقق: التسجيل على رقمه فقط (بدون سؤال = رسالة أقل)
        data["r"].pop("phone", None)
        return _on_number_choice(api, wa_id, data, "me")
    api.buttons(
        wa_id,
        f"📱 هل تريد التسجيل على هذا الرقم؟\n+{me}\n\n(هو الرقم الذي سيتواصل عليه العملاء عبر واتساب)",
        [("R:num:me", "✅ نعم، هذا الرقم"), ("R:num:other", "📱 رقم آخر")],
    )
    return "r_num", data


def _registered(phone: str):
    p = db.get_professional_for_wa(phone)
    return p if p and p.get("status") != db.STATUS_REJECTED else None


def _on_number_choice(api, wa_id, data, which):
    r = data["r"]
    me = _digits(wa_id)
    if which == "me":
        p = _registered(me)
        if p:
            api.text(wa_id, f"هذا الرقم مسجّل مسبقًا في «فنّي» باسم «{p['full_name']}».")
            if not db.is_wa_registrar(me) and not otp_enabled():
                return "menu", {}
            return _ask_number(api, wa_id, data)
        r.pop("phone", None)
        return _ask_top(api, wa_id, data)
    api.text(wa_id, "✍️ اكتب رقم واتساب الفني (مثل: 0501234567 أو 966501234567):")
    return "r_phone", data


def _on_phone_text(api, wa_id, data, body):
    r = data["r"]
    me = _digits(wa_id)
    t = norm_phone(body, me)
    if not t:
        api.text(wa_id, "الرقم غير صحيح 🙏 اكتبه مثل: 0501234567 أو 966501234567")
        return "r_phone", data
    if t == me:
        return _on_number_choice(api, wa_id, data, "me")
    p = _registered(t)
    if p:
        api.text(wa_id, f"الرقم +{t} مسجّل مسبقًا في «فنّي» باسم «{p['full_name']}». اكتب رقمًا آخر:")
        return "r_phone", data
    if db.is_wa_registrar(me):
        # المالك والمسوّقون: بدون رمز تحقق
        r["phone"] = t
        return _ask_top(api, wa_id, data, note=f"✅ سيُسجَّل الفني على الرقم +{t}\n\n")
    return _send_otp(api, wa_id, data, t)


def _send_otp(api, wa_id, data, t):
    import secrets
    import time

    import config
    import nudges

    r = data["r"]
    me = _digits(wa_id)
    if db.count_otp_since(me) >= OTP_DAILY:
        api.text(wa_id, "⚠️ تجاوزت الحد المسموح لإرسال رموز التحقق اليوم. حاول غدًا، أو سجّل من جوال الفني نفسه.")
        return "r_phone", data
    code = f"{secrets.randbelow(900000) + 100000}"
    ok = False
    if nudges._in_free_window(t):
        # صاحب الرقم راسل البوت خلال 24 ساعة — رسالة عادية بدل القالب المدفوع
        res = api.text(t, f"🔐 رمز التحقق لتسجيلك في «فنّي»: {code}\nلا تشاركه إلا مع الشخص الذي يسجّلك.")
        ok = res is not None and getattr(res, "status_code", 500) < 400
    if not ok:
        for name in config.WA_TPL_VERIFY:
            res = api.auth_code(t, name.strip(), code)
            if res is not None and getattr(res, "status_code", 500) < 400:
                ok = True
                break
    if not ok:
        api.text(wa_id, f"⚠️ تعذّر إرسال الرمز إلى +{t}. تأكد أن الرقم صحيح وعليه واتساب، أو سجّل من جوال الفني نفسه.\n\n"
                        "✍️ اكتب الرقم مرة أخرى:")
        return "r_phone", data
    db.log_otp(me, t)
    r.update(otp=code, otp_phone=t, otp_at=time.time(), otp_tries=0)
    api.text(wa_id, f"📩 أرسلنا رمز تحقق إلى واتساب الرقم +{t}.\nاطلب الرمز من صاحب الرقم، واكتبه هنا (صالح 10 دقائق):")
    return "r_otp", data


def _on_otp_text(api, wa_id, data, body):
    import time

    r = data["r"]
    t = r.get("otp_phone")
    if not r.get("otp") or not t:
        return _ask_number(api, wa_id, data)
    if time.time() - (r.get("otp_at") or 0) > OTP_TTL:
        for k in ("otp", "otp_phone", "otp_at", "otp_tries"):
            r.pop(k, None)
        api.text(wa_id, "⌛ انتهت صلاحية الرمز. اكتب الرقم مرة أخرى لإرسال رمز جديد:")
        return "r_phone", data
    typed = re.sub(r"\D", "", (body or "").translate(str.maketrans("٠١٢٣٤٥٦٧٨٩", "0123456789")))
    if typed == r["otp"]:
        for k in ("otp", "otp_phone", "otp_at", "otp_tries"):
            r.pop(k, None)
        r["phone"] = t
        return _ask_top(api, wa_id, data, note=f"✅ تم التحقق من الرقم +{t}\n\n")
    r["otp_tries"] = (r.get("otp_tries") or 0) + 1
    left = OTP_TRIES - r["otp_tries"]
    if left <= 0:
        for k in ("otp", "otp_phone", "otp_at", "otp_tries"):
            r.pop(k, None)
        api.text(wa_id, "❌ تجاوزت عدد المحاولات. اكتب الرقم مرة أخرى لإرسال رمز جديد:")
        return "r_phone", data
    api.text(wa_id, f"❌ الرمز غير صحيح. حاول مرة أخرى (المتبقي: {left}):")
    return "r_otp", data


# ─────────────────────────── المهنة ───────────────────────────

def _ask_top(api, wa_id, data, intro=None, note=""):
    """الـ9 الأكثر طلبًا + «المزيد» — نفس قائمة البحث."""
    from whatsapp_bot import top
    data.setdefault("r", {}).pop("more", None)
    more_n = max(len(top.all_professions()) - 9, 0)
    body = note + (intro or (f"أهلًا بك {data['r'].get('name', '')} 👋\n"
                     f"ما هي مهنتك؟ اختر من القائمة التالية، أو اضغط «المزيد» للقائمة الموسّعة (+{more_n} مهنة)، "
                     "أو اكتب اسمها (مثل: سباك)"))
    api.list(wa_id, body, "اختر مهنتك", top.top_rows("R:"), section_title="الأكثر طلبًا")
    return "r_prof", data


def _ask_more(api, wa_id, data):
    from whatsapp_bot import top
    text, ids = top.more_message("📋 باقي المهن:")
    api.text(wa_id, text)
    data.setdefault("r", {})["more"] = ids
    return "r_prof", data


def _ask_domain(api, wa_id, page, data):
    f = _flow()
    items, prev, nxt = f._page(professions.get_domains("ar"), page)
    rows = [(f"R:dom:{d['id']}", d["name"], d["name"] if len(d["name"]) > 24 else None) for d in items]
    if nxt:
        rows.append((f"R:dpg:{page + 1}", "المزيد ⬅️", "باقي المجالات"))
    if prev:
        rows.append((f"R:dpg:{page - 1}", "➡️ السابق", None))
    api.list(wa_id, f"تشرّفنا بك يا {data['r'].get('name', '')} 🌟\nاختر مجال مهنتك 👇 أو اكتب اسم مهنتك (مثل: سباك)",
             "اختر المجال", rows, section_title="المجالات")
    return "r_prof", data


def _ask_profession(api, wa_id, domain_id, page, data):
    profs = professions.get_professions_by_domain(domain_id, "ar")
    if not profs:
        return _ask_top(api, wa_id, data)
    per = 7 if len(profs) > 9 else 9
    start_ = page * per
    rows = [(f"R:prof:{x['id']}", x["name"], x["name"] if len(x["name"]) > 24 else None) for x in profs[start_:start_ + per]]
    if start_ + per < len(profs):
        rows.append((f"R:ppg:{domain_id}:{page + 1}", "المزيد ⬅️", None))
    if page > 0:
        rows.append((f"R:ppg:{domain_id}:{page - 1}", "➡️ السابق", None))
    rows.append(("R:dpg:0", "↩️ العودة إلى المجالات", None))
    api.list(wa_id, "اختر مهنتك 👇", "اختر المهنة", rows, section_title="المهن")
    return "r_prof", data


def _match_profession(api, wa_id, text, data):
    from whatsapp_bot import top
    n = top.to_number(text)
    if n is not None:
        more = data.get("r", {}).get("more")
        if n == 10 and not more:
            return _ask_more(api, wa_id, data)
        pid = top.pick_by_number(n, more)
        if pid:
            return _select_profession(api, wa_id, pid, data)
        api.text(wa_id, "هذا الرقم غير موجود في القائمة 🤔 اكتب رقمًا صحيحًا أو اسم المهنة.")
        return "r_prof", data
    syn = top.synonym_profession(text)
    if syn and professions.get_profession(syn, "ar")[1]:
        db.log_search_term(text, syn, professions.get_profession(syn, "ar")[1]["name"], "register")
        return _select_profession(api, wa_id, syn, data)
    f = _flow()
    q = f.norm(text)
    words = [w for w in q.split() if len(w) >= 3] or [q]
    scored = []
    for x in f._all_professions():
        n = f.norm(x["name"])
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
    if scored and (len(scored) == 1 or scored[0][0] == 0):
        db.log_search_term(text, scored[0][2]["id"], scored[0][2]["name"], "register")
        return _select_profession(api, wa_id, scored[0][2]["id"], data)
    db.log_search_term(text, None, "، ".join(x["name"] for _, _, x in scored[:3]) or None, "register")
    if scored:
        rows = [(f"R:prof:{x['id']}", x["name"], x["name"] if len(x["name"]) > 24 else None) for _, _, x in scored[:9]]
        rows.append(("R:top:more", "📋 كل المهن", None))
        api.list(wa_id, "اختر مهنتك من النتائج 👇", "اختر المهنة", rows, section_title="المهن")
        return "r_prof", data
    return _ask_top(api, wa_id, data, f"لم أجد مهنة باسم «{_flow().clip_text(text)}» 🤔\n\nاختر مهنتك من القائمة 👇 أو اكتب رقمها أو اسمها بصيغة أخرى")


def _select_profession(api, wa_id, pid, data):
    domain, prof = professions.get_profession(pid, "ar")
    if not prof:
        return _ask_top(api, wa_id, data)
    r = data.setdefault("r", {})
    r.update(pid=prof["id"], pname=prof["name"], domain=(domain or {}).get("name", ""),
             wide=bool(prof.get("allow_city_wide")), all_services=prof.get("services") or [], services=[])
    if r["all_services"]:
        return _ask_services(api, wa_id, data, 0)
    return _ask_location(api, wa_id, data)


# ─────────────────────────── الخدمات (اختياري) ───────────────────────────

def _ask_services(api, wa_id, data, page=0):
    """قائمة الخدمات: يختار أكثر من خدمة (ضغطة لكل خدمة)، والمختارة تختفي من القائمة.
    أول مرة: حتى 9 خدمات + «كل الخدمات». بعد أول اختيار: «✅ تم التحديد» + الباقي + «كل الخدمات»."""
    r = data["r"]
    allsv, chosen = r["all_services"], r.get("services", [])
    if not chosen:
        # نموذج بمربعات اختيار ☑️ (يحدد أكثر من خدمة ويرسل مرة وحدة) — وإلا القائمة العادية
        from whatsapp_bot import wa_flows
        items = [{"id": "all", "title": "📋 كل الخدمات"}] + [
            {"id": str(i), "title": wa_flows.clip_title(sv), "description": sv if len(sv) > wa_flows.TITLE_MAX else None}
            for i, sv in enumerate(allsv)]
        if wa_flows.send(api, wa_id, "services",
                         f"ما الخدمات التي تقدمها في مهنة «{r['pname']}»؟ 👇\n"
                         "اضغط الزر، وحدّد كل خدماتك ☑️ ثم «تم التحديد».",
                         "اختر الخدمات", "حدّد كل الخدمات التي تقدمها:", items, f"svc:{_digits(wa_id)}"):
            return "r_svc", data
    left = [(i, sv) for i, sv in enumerate(allsv) if sv not in chosen]
    if not left:
        return _ask_location(api, wa_id, data)
    rows = []
    if chosen:
        rows.append(("R:svcdone", f"✅ تم التحديد ({len(chosen)})", "الانتقال إلى الخطوة التالية"))
    room = 10 - len(rows) - 1
    for i, sv in left[:room]:
        rows.append((f"R:svc:{i}", sv, sv if len(sv) > 24 else None))
    rows.append(("R:svcall", "📋 كل الخدمات", "أقدّم جميع خدمات المهنة"))
    if chosen:
        head = ("✅ اخترت: " + "، ".join(chosen) + "\n\nاختر خدمة أخرى، أو اضغط «تم التحديد» 👇")
    else:
        head = (f"ما الخدمات التي تقدمها في مهنة «{r['pname']}»؟ 👇\n"
                "يمكنك اختيار أكثر من خدمة (واحدة بعد الأخرى)، أو «كل الخدمات».")
    api.list(wa_id, head, "اختر الخدمات", rows, section_title="الخدمات")
    return "r_svc", data


# ─────────────────────────── الموقع ───────────────────────────

def _ask_location(api, wa_id, data):
    api.location_request(wa_id, "📍 شارك موقعك (مكان عملك أو منزلك) من الزر أدناه، لنحدد مدينتك وأقرب الأحياء إليك.")
    return "r_loc", data


def on_location(api, wa_id, data, lat, lon):
    r = data.setdefault("r", {})
    if not r.get("pid"):
        return start(api, wa_id)
    res = db.find_nearest_sa_city_and_district_by_coords(lat, lon, countries.enabled_codes("wa"))
    if not res or not res[0]:
        api.text(wa_id, "لم نتمكن من تحديد مدينتك من هذا الموقع 😅 جرّب إرسال موقع آخر.")
        return _ask_location(api, wa_id, data)
    city, district = res
    r.update(city_id=city["id"], city=city["name"], country=city.get("country") or "SA",
             origin=district["id"] if district else None, has_d=bool(city.get("has_districts") and district),
             chosen=[], shown=[], lat=lat, lon=lon)
    # بدون خطوة «هل موقعك صحيح؟» — مباشرة أقرب الأحياء (والمدينة مكتوبة تحت كل حي)
    if not r["has_d"]:
        return _confirm(api, wa_id, data)
    r["whole"] = False
    return _ask_near_districts(api, wa_id, data)


# ─────────────────────────── الأحياء ───────────────────────────

def _district_rows(r):
    shown = r.get("page_ids", [])
    chosen = set(r.get("chosen", []))
    rows = []
    for did in shown:
        if did in chosen:
            continue
        d = db.get_sa_district_by_id(did)
        if d:
            rows.append((f"R:d:{did}", d["name"], d["name"] if len(d["name"]) > 24 else None))
    rows = rows[:7]
    rows.append(("R:dmore", "🔎 أحيائي ليست هنا", "اعرض أحياء أخرى"))
    if chosen:
        rows.append(("R:ddone", f"✔️ انتهيت ({len(chosen)})", None))
    if r.get("wide"):
        rows.append(("R:dwhole", f"🌍 كل {r['city']}", "أخدم المدينة كاملة"))
    return rows[:10]


def _next_page(r):
    exclude = list(set(r.get("shown", [])) | set(r.get("chosen", [])))
    origin = r.get("origin")
    ids = []
    if origin and origin not in exclude:
        ids.append(origin)
    if origin:
        ids += [d["id"] for d in db.nearest_sa_districts(origin, exclude + ids, limit=7 - len(ids))]
    r["page_ids"] = ids
    r["shown"] = list(set(r.get("shown", [])) | set(ids))
    return ids


def _ask_districts(api, wa_id, data, new_page=False):
    r = data["r"]
    if new_page or not r.get("page_ids"):
        if not _next_page(r):
            # خلصت الأحياء القريبة — نعيد من الأقرب
            r["shown"] = []
            _next_page(r)
    chosen_names = [db.get_sa_district_by_id(d)["name"] for d in r.get("chosen", []) if db.get_sa_district_by_id(d)]
    head = ("✅ اخترت: " + "، ".join(chosen_names) + "\nهل تريد إضافة حي آخر؟ 👇") if chosen_names else \
        f"ما الأحياء التي تخدمها في {r['city']}؟ 👇 (يمكنك اختيار أكثر من حي)\nأو اكتب اسم الحي"
    api.list(wa_id, head, "اختر الحي", _district_rows(r), section_title="أقرب الأحياء إليك")
    return "r_dist", data


MAX_DISTRICTS = 5   # نفس حد تلغرام


def _ask_near_districts(api, wa_id, data):
    """قائمة أقرب الأحياء لموقعه (حتى 9) — تحت كل حي اسم المدينة، والصف الأخير «قائمة الأحياء كاملة».
    يضغط حي حي (حتى 5)، وبعد أول اختيار يظهر «✅ تم التحديد»."""
    r = data["r"]
    chosen = r.setdefault("chosen", [])
    if len(chosen) >= MAX_DISTRICTS:
        return _confirm(api, wa_id, data, f"ℹ️ وصلت إلى الحد الأقصى ({MAX_DISTRICTS} أحياء).\n")
    if not r.get("near_ids"):
        origin = r.get("origin")
        ids = [origin] if origin else []
        if origin:
            ids += [d["id"] for d in db.nearest_sa_districts(origin, ids, limit=17)]
        r["near_ids"] = ids
    if not chosen:
        # نموذج بمربعات اختيار ☑️: أقرب الأحياء (حتى 18) + «كل المدينة» للمهن النادرة + «حيّي ليس هنا»
        from whatsapp_bot import wa_flows
        items = []
        for did in r["near_ids"][:18]:
            d = db.get_sa_district_by_id(did)
            if d:
                items.append({"id": str(did), "title": wa_flows.clip_title(d["name"]), "description": r["city"]})
        if r.get("wide"):
            items.append({"id": "whole", "title": f"🌍 كل {r['city']}", "description": "أخدم المدينة كاملة"})
        items.append({"id": "full", "title": "📋 حيّي ليس هنا", "description": f"اعرض كل أحياء {r['city']} مرقّمة"})
        if wa_flows.send(api, wa_id, "districts",
                         f"📍 {r['city']} — ما الأحياء التي تعمل فيها؟ 👇\n"
                         f"اضغط الزر، وحدّد أحياءك ☑️ (حتى {MAX_DISTRICTS}) ثم «تم التحديد».",
                         "اختر أحياءك", f"أقرب الأحياء إلى موقعك — حدّد حتى {MAX_DISTRICTS}:", items,
                         f"dist:{_digits(wa_id)}"):
            return "r_dist", data
    rows = []
    if chosen:
        rows.append(("R:ddone", f"✅ تم التحديد ({len(chosen)})", "الانتقال إلى المراجعة"))
    extra = [("R:dwhole", f"🌍 كل {r['city']}"[:24], "أخدم المدينة كاملة")] if r.get("wide") else []
    room = 10 - len(rows) - 1 - len(extra)
    for did in [d for d in r["near_ids"] if d not in chosen][:min(room, 9)]:
        d = db.get_sa_district_by_id(did)
        if d:
            rows.append((f"R:d:{did}", clip_name(d["name"]), r["city"]))
    rows += extra
    rows.append(("R:dall", "📋 قائمة الأحياء كاملة", f"كل أحياء {r['city']} مرقّمة"))
    if chosen:
        names = [db.get_sa_district_by_id(d)["name"] for d in chosen if db.get_sa_district_by_id(d)]
        head = ("✅ اخترت: " + "، ".join(names)
                + f"\n\nاختر حيًّا آخر (حتى {MAX_DISTRICTS})، أو اضغط «تم التحديد» 👇")
    else:
        head = (f"📍 {r['city']} — ما الأحياء التي تعمل فيها؟ 👇\n"
                f"هذه أقرب الأحياء إلى موقعك. يمكنك اختيار حتى {MAX_DISTRICTS} أحياء (واحدًا بعد الآخر).")
    api.list(wa_id, head, "اختر الحي", rows, section_title="أقرب الأحياء إليك")
    return "r_dist", data


def _district_text_in_list(api, wa_id, data, text):
    r = data["r"]
    f = _flow()
    q = f.norm(re.sub(r"^\s*حي\s+", "", text or ""))
    if len(q) >= 2:
        hits = [d for d in db.list_sa_districts_by_city(r["city_id"])
                if f.norm(re.sub(r"^حي\s+", "", d["name"])) == q]
        if len(hits) == 1:
            if hits[0]["id"] not in r.setdefault("chosen", []):
                r["chosen"].append(hits[0]["id"])
            r["whole"] = False
            data.pop("_hinted", None)
            return _ask_near_districts(api, wa_id, data)
    return f.hint_once(api, wa_id, "r_dist", data, lambda: api.text(
        wa_id, "👆 اختر أحياءك من الرسالة أعلاه (زر «اختر الحي» أو «اختر أحياءك»)."))


def clip_name(name: str) -> str:
    return name if len(name) <= 24 else name[:23] + "…"
WHOLE_CITY_WORDS = ("#", "＃", "كل المدينة", "المدينة كاملة", "كامل المدينة", "كل المدينه")


def _ask_districts_numbered(api, wa_id, data):
    """رسالة وحدة فيها أحياء المدينة مرقمة (المدن الكبيرة: مقسمة مجموعات متقاربة، ومجموعة
    الفني أول)، والفني يرد بأرقام أحيائه (حتى 5) برسالة وحدة — أوفر من الضغط حي حي."""
    from whatsapp_bot import geo_groups
    r = data["r"]
    lat, lon = r.get("lat"), r.get("lon")
    groups = geo_groups.ordered_groups(r["city_id"], r["city"], near=(lat, lon) if lat is not None else None)
    if len(groups) == 1 and groups[0][0] is None and lat is not None:
        ds = groups[0][1]
        with_c = sorted((d for d in ds if d.get("lat") is not None),
                        key=lambda d: db._approx_dist_sq(d["lat"], d["lon"], lat, lon))
        groups = [(None, with_c + [d for d in ds if d.get("lat") is None])]
    r["dlist"] = [d["id"] for _, ds in groups for d in ds]
    whole = f"#. 🌍 كل {r['city']} (المدينة كاملة)" if r.get("wide") else None
    head = (f"📍 أحياء {r['city']} (الأقرب إلى موقعك أولًا) 👇\n"
            f"اكتب *أرقام* الأحياء التي تعمل فيها — حتى {MAX_DISTRICTS} أحياء، كل رقم في سطر، مثل:\n1\n4\n9")
    _flow().send_numbered(api, wa_id, head, None, f"✍️ اكتب أرقام أحيائك (حتى {MAX_DISTRICTS}).",
                          first_line=whole, groups=[(t, [d["name"] for d in ds]) for t, ds in groups])
    return "r_dist", data


def _pick_district_numbers(api, wa_id, data, text) -> tuple | None:
    """يرجع (state, data) لو الرسالة فيها أرقام، وإلا None."""
    from whatsapp_bot import top
    r = data["r"]
    t = (text or "").translate(top._AR_DIGITS)
    nums = [int(x) for x in re.findall(r"\d+", t)]
    if not nums or not r.get("dlist"):
        return None
    ids, bad = [], []
    for n in nums:
        if 1 <= n <= len(r["dlist"]):
            did = r["dlist"][n - 1]
            if did not in ids:
                ids.append(did)
        else:
            bad.append(n)
    if not ids:
        api.text(wa_id, f"هذه الأرقام غير موجودة في القائمة 🤔 اكتب أرقامًا من 1 إلى {len(r['dlist'])}.")
        return "r_dist", data
    note = ""
    if len(ids) > MAX_DISTRICTS:
        ids = ids[:MAX_DISTRICTS]
        note += f"ℹ️ الحد الأقصى {MAX_DISTRICTS} أحياء — اعتمدنا أول {MAX_DISTRICTS}.\n"
    if bad:
        note += "ℹ️ تجاهلنا أرقامًا غير موجودة: " + "، ".join(map(str, bad)) + "\n"
    r["chosen"] = ids
    r["whole"] = False
    return _confirm(api, wa_id, data, note)


def _hint_district_numbers(api, wa_id, data, text):
    """كتب كلام بدل أرقام: نطلع له أرقام الأحياء اللي تشبه كلامه (من نفس القائمة)،
    وإلا نذكّره يكتب أرقام — بدون ما نعيد القائمة الطويلة أو نرجع للقوائم القديمة."""
    r = data["r"]
    if not r.get("dlist"):
        return _ask_districts_numbered(api, wa_id, data)
    f = _flow()
    q = f.norm(re.sub(r"^\s*حي\s+", "", (text or "").strip()))
    hits = []
    if len(q) >= 2:
        names = {d["id"]: d["name"] for d in db.list_sa_districts_by_city(r["city_id"])}
        for i, did in enumerate(r["dlist"], 1):
            if q in f.norm(names.get(did, "")):
                hits.append(f"{i}. {names[did]}")
    if hits:
        api.text(wa_id, f"🔎 الأحياء التي تحتوي على «{f.clip_text(text)}»:\n" + "\n".join(hits[:15])
                 + f"\n\n✍️ اكتب *أرقام* أحيائك (حتى {MAX_DISTRICTS})، كل رقم في سطر.")
    else:
        api.text(wa_id, f"✍️ اكتب *أرقام* الأحياء من القائمة أعلاه 👆 (حتى {MAX_DISTRICTS})، كل رقم في سطر، مثل:\n12\n40\n7"
                 + ("\nأو اكتب اسم الحي لأعرض لك رقمه." if len(q) < 2 else f"\nلم أجد حيًّا يحتوي على «{f.clip_text(text)}».")
                 + ("\n🌍 أو # لكل المدينة." if r.get("wide") else ""))
    return "r_dist", data


def _match_district(api, wa_id, text, data):
    r = data["r"]
    q = re.sub(r"^\s*حي\s+", "", (text or "").strip())
    f = _flow()
    matches = db.search_sa_districts(r["city_id"], q, 9) if q else []
    if not matches and q:
        nq = f.norm(q)
        matches = [d for d in db.list_sa_districts_by_city(r["city_id"]) if nq in f.norm(d["name"])][:9]
    if len(matches) == 1:
        return _add_district(api, wa_id, data, matches[0]["id"])
    if matches:
        r["page_ids"] = [d["id"] for d in matches[:7]]
        return _ask_districts(api, wa_id, data)
    api.text(wa_id, f"لم أجد حيًّا بهذا الاسم في {r['city']} 🤔")
    return _ask_districts(api, wa_id, data)


def _add_district(api, wa_id, data, did):
    r = data["r"]
    if did not in r.setdefault("chosen", []):
        r["chosen"].append(did)
    return _ask_districts(api, wa_id, data)


# ─────────────────────────── المراجعة والحفظ ───────────────────────────

def _confirm(api, wa_id, data, note=""):
    r = data["r"]
    if r.get("whole") or not r.get("has_d"):
        where = f"{r['city']} — المدينة كاملة 🌍"
    else:
        names = [db.get_sa_district_by_id(d)["name"] for d in r.get("chosen", [])]
        where = f"{r['city']} — " + "، ".join(names)
    services = "، ".join(r.get("services") or []) or "—"
    api.buttons(
        wa_id,
        f"{note}راجع بياناتك قبل التسجيل 👇\n\n"
        f"👷 {r['name']}\n🛠️ {r['pname']}\n📋 {services}\n📍 {countries.name(r['country'], 'ar')} / {where}\n"
        f"📱 رقم التواصل للعملاء: +{tech_phone(r, wa_id)}",
        [("R:ok", "✅ تأكيد التسجيل")]
        + ([("R:dedit", "📍 تعديل الأحياء")] if r.get("has_d") else [])
        + [("R:redo", "✏️ البدء من جديد")],
    )
    return "r_confirm", data


def _save(api, wa_id, data):
    from handlers.search import _professional_card_text

    r = data["r"]
    digits = tech_phone(r, wa_id)
    other = digits != _digits(wa_id)
    if _registered(digits):
        api.text(wa_id, f"الرقم +{digits} مسجّل مسبقًا في «فنّي».")
        return "menu", {}
    whole = bool(r.get("whole") or not r.get("has_d"))
    chosen = [] if whole else list(r.get("chosen", []))
    names = [db.get_sa_district_by_id(d)["name"] for d in chosen]
    row_id = db.create_registration({
        "telegram_user_id": -int(digits),
        "wa_id": digits,
        "full_name": r["name"],
        "city": r["city"],
        "city_id": r["city_id"],
        "country": r["country"],
        "neighborhood": "، ".join(names) if names else None,
        "district_ids": chosen,
        "whatsapp_number": "+" + digits,
        "has_whatsapp": True,
        "domain_name": r.get("domain") or "",
        "profession_id": r["pid"],
        "profession_name": r["pname"],
        "services": r.get("services") or [],
        "covers_whole_city": whole,
        "source": "whatsapp",
        "registered_by": _digits(wa_id) if other else None,
    })
    _notify_admin_async(row_id)
    p = db.get_professional_by_id(row_id)
    if other:
        _notify_registered(api, digits, r["name"], r["pname"])
        # سجّل فنيًا آخر: رسالة وحدة (بطاقة + أزرار) — بدون سؤال ربط تلغرام (يخص صاحب الرقم)
        api.buttons(wa_id, f"🎉 تم تسجيل الفني «{r['name']}» على الرقم +{digits}، وأصبح يظهر للعملاء.\n\n"
                           + _professional_card_text(p),
                    [("R:again", "➕ تسجيل فني آخر"), ("m:search", "🔍 ابحث عن فني")])
        return "menu", {}
    api.text(wa_id, "🎉 تم تسجيلك! وأصبحت تظهر للعملاء الذين يبحثون في واتساب وتلغرام.\n\nهذه بطاقتك كما يراها العميل:\n\n"
             + _professional_card_text(p))
    api.buttons(
        wa_id,
        "هل تريد إضافة بياناتك في تطبيق تلغرام أيضًا؟ 🔗\nستصلك هناك تنبيهات العملاء مجانًا، ويمكنك إدارة حسابك واشتراكك.",
        [("R:tg:yes", "✅ نعم، أضفها"), ("R:tg:no", "لا، شكرًا")],
    )
    return "r_done", {"r": {"saved_id": row_id}}


def _notify_registered(api, phone, name, pname):
    """يبلّغ الفني بتسجيله (قالب خدمي مدفوع ~4 هللات) — يشتغل بالخلفية عشان ما يأخر رد المسجِّل."""
    def run():
        import config
        for tpl in config.WA_TPL_REGISTERED:
            r = api.template(phone, tpl.strip(), [name, pname], button_payloads=["R:mine"])
            if r is not None and getattr(r, "status_code", 500) < 400:
                break

    threading.Thread(target=run, daemon=True).start()


def _telegram_link(api, wa_id, data):
    p = db.get_professional_by_wa_id(_digits(wa_id))
    if not p:
        return start(api, wa_id)
    if (p.get("telegram_user_id") or 0) > 0:
        api.text(wa_id, "حسابك مربوط بتلغرام بالفعل ✅")
        return "menu", {}
    url = f"https://t.me/{TELEGRAM_BOT}?start={contact_links.link_token(p['id'])}"
    api.cta_url(wa_id, "اضغط الزر، ثم اضغط «ابدأ» (Start) في تلغرام — وسيُربط حسابك تلقائيًا ✅",
                "فتح تلغرام", url)
    return "menu", {}


def on_flow(api, wa_id, kind, picked, state, data):
    """رد نموذج مربعات الاختيار (الخدمات أو الأحياء)."""
    r = data.setdefault("r", {})
    if kind == "svc":
        if not r.get("pid"):
            return start(api, wa_id)
        allsv = r.get("all_services") or []
        if "all" in picked or not picked:
            r["services"] = list(allsv)
        else:
            r["services"] = [allsv[int(i)] for i in picked if i.isdigit() and int(i) < len(allsv)]
        return _ask_location(api, wa_id, data)
    if kind == "dist":
        if not r.get("city_id"):
            return start(api, wa_id)
        if "full" in picked:
            return _ask_districts_numbered(api, wa_id, data)
        if "whole" in picked and r.get("wide"):
            r["whole"], r["chosen"] = True, []
            return _confirm(api, wa_id, data)
        ids = [int(i) for i in picked if i.isdigit()][:MAX_DISTRICTS]
        if not ids:
            return _ask_near_districts(api, wa_id, data)
        r["chosen"], r["whole"] = ids, False
        return _confirm(api, wa_id, data)
    return state, data


# ─────────────────────────── الأزرار ───────────────────────────

def on_choice(api, wa_id, rid, state, data):
    p = rid.split(":")[1:]
    act = p[0] if p else ""
    r = data.setdefault("r", {})
    if act == "details":
        p = db.get_professional_for_wa(wa_id)
        if not p:
            return start(api, wa_id)
        from whatsapp_bot import subscribe
        return subscribe.details(api, wa_id, p)
    if act == "mine":
        # زر «حسابي» من قالب «تم تسجيلك»: بطاقته وحالته + رابط القناة (الرسالة مجانية بعد ضغطه)
        p = db.get_professional_for_wa(wa_id)
        if not p:
            return start(api, wa_id)
        return _status(api, wa_id, p, extra=f"\n\n📢 تابع قناة «فنّي» على واتساب: {_flow().CHANNEL_URL}")
    if act == "mute":
        p = db.get_professional_for_wa(wa_id)
        if p:
            db.set_notify_off(p["id"], "whatsapp", True)
            db.mark_notifications_responded(p["id"])
        api.text(wa_id, "🔕 تم إيقاف الإشعارات. إذا أردت إعادة تفعيلها فتواصل مع إدارة «فنّي».")
        return "menu", {}
    if act == "sub":
        p = db.get_professional_for_wa(wa_id)
        if not p:
            return start(api, wa_id)
        from whatsapp_bot import subscribe
        return subscribe.start(api, wa_id, p)
    if act == "tg":
        if p[1] == "yes":
            return _telegram_link(api, wa_id, data)
        api.text(wa_id, "حسنًا 👍 يمكنك ربطه في أي وقت من «🛠️ أنا فني». اكتب s للعودة إلى القائمة.")
        return "menu", {}
    if act == "again":
        return start(api, wa_id)
    if not r.get("name"):            # زر قديم من جلسة منتهية (مرت المهلة) ← القائمة الرئيسية
        p_ = db.get_professional_by_wa_id(_digits(wa_id))
        return _flow()._welcome(api, wa_id, (p_ or {}).get("full_name") or "")
    if act == "num":
        return _on_number_choice(api, wa_id, data, p[1] if len(p) > 1 else "me")
    if act == "top":
        return _ask_more(api, wa_id, data)
    if act == "dpg":
        return _ask_domain(api, wa_id, int(p[1]), data)
    if act == "dom":
        return _ask_profession(api, wa_id, p[1], 0, data)
    if act == "ppg":
        return _ask_profession(api, wa_id, p[1], int(p[2]), data)
    if act == "prof":
        return _select_profession(api, wa_id, p[1], data)
    if not r.get("pid"):
        return _ask_top(api, wa_id, data)
    if act == "svc":
        i = int(p[1])
        if 0 <= i < len(r.get("all_services", [])):
            sv = r["all_services"][i]
            r.setdefault("services", [])
            if sv not in r["services"]:
                r["services"].append(sv)
        if r.get("services") and len(r["services"]) >= len(r.get("all_services", [])):
            return _ask_location(api, wa_id, data)
        return _ask_services(api, wa_id, data)
    if act == "svcpg":
        return _ask_services(api, wa_id, data, int(p[1]))
    if act == "svcall":
        r["services"] = list(r.get("all_services", []))
        return _ask_location(api, wa_id, data)
    if act == "svcdone":
        return _ask_location(api, wa_id, data)
    if act == "locno":
        return _ask_location(api, wa_id, data)
    if not r.get("city_id"):
        return _ask_location(api, wa_id, data)
    if act in ("locok", "dedit"):
        if r.get("has_d"):
            r["chosen"], r["whole"] = [], False
            return _ask_near_districts(api, wa_id, data)
        return _confirm(api, wa_id, data)
    if act == "d":
        did = int(p[1])
        if did not in r.setdefault("chosen", []):
            r["chosen"].append(did)
        r["whole"] = False
        return _ask_near_districts(api, wa_id, data)
    if act == "dall":
        return _ask_districts_numbered(api, wa_id, data)
    if act == "dmore":
        return _ask_districts(api, wa_id, data, new_page=True)
    if act == "ddone":
        if not r.get("chosen") and not r.get("whole"):
            return _ask_near_districts(api, wa_id, data)
        return _confirm(api, wa_id, data)
    if act == "dwhole":
        r["whole"] = True
        return _confirm(api, wa_id, data)
    if act == "redo":
        return start(api, wa_id)
    if act == "ok":
        if state != "r_confirm":
            return _confirm(api, wa_id, data)
        return _save(api, wa_id, data)
    return state, data


# ─────────────────────────── تنبيه الأدمن (تلغرام) ───────────────────────────

def _notify_admin_async(row_id: int):
    def run():
        try:
            import asyncio

            from telegram import Bot

            import config
            from handlers.admin import notify_admin_new_registration

            class _Ctx:
                pass

            async def go():
                async with Bot(config.BOT_TOKEN) as bot:
                    c = _Ctx()
                    c.bot = bot
                    await notify_admin_new_registration(c, row_id)

            asyncio.run(go())
        except Exception:
            import logging
            logging.getLogger("fani.wa").exception("admin notify failed")

    threading.Thread(target=run, daemon=True).start()
