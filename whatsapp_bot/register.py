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
from whatsapp_bot import lang, top
from whatsapp_bot.lang import get_lang, tr, tr_service

TELEGRAM_BOT = "FanniServiceBot"


def _flow():
    from whatsapp_bot import flow  # تجنّب الاستيراد الدائري
    return flow


def _digits(wa_id: str) -> str:
    return re.sub(r"\D", "", wa_id or "")


def _pname(r: dict) -> str:
    """اسم المهنة للعرض بلغة المستخدم — r["pname"] يبقى عربي لأنه ينحفظ بالقاعدة."""
    if (r.get("edit") == "p2" or r.get("adding2")) and r.get("p2id"):
        return _flow().prof_name(r["p2id"], r.get("p2name"))
    return _flow().prof_name(r.get("pid"), r.get("pname"))


# ─────────────────────────── البداية ───────────────────────────

def start(api, wa_id):
    """زر «أنا فني»: لو مسجّل يشوف حالته، وإلا نبدأ التسجيل."""
    me = _digits(wa_id)
    p = db.get_professional_by_wa_id(me)
    # المالك/المسوّق يسجّل فنيين آخرين — ما نوقفه عند حالته هو
    if p and p.get("status") != db.STATUS_REJECTED and not db.is_wa_registrar(me):
        return _status(api, wa_id, p)
    api.text(wa_id, tr("مرحبًا بك 🙌 سنسجّلك في «فنّي» مجانًا خلال دقيقة، لتظهر للعملاء في واتساب وتلغرام.\n\n"
                       "✍️ اكتب اسمك (الاسم الذي سيظهر للعملاء):"))
    return "r_name", {"r": {}}


def _status(api, wa_id, p, extra=""):
    limit = int(db.get_setting("free_contacts_limit", str(db.FREE_CONTACTS_LIMIT))) + (p.get("bonus_contacts") or 0)
    line = tr("✅ مشترك — تظهر لجميع العملاء دون حد") if p.get("is_subscribed") else \
        tr("📊 فرص التواصل المجانية: استخدمت {used} من {limit}", used=p.get("free_contacts_used", 0), limit=limit)
    if not p.get("is_subscribed") and (p.get("free_contacts_used") or 0) >= limit:
        line += "\n\n" + tr("⚠️ انتهت فرصك المجانية — رقمك لا يظهر للعملاء حاليًا. اضغط «💳 اشترك» أدناه لتعود إلى الظهور.")
    buttons = [("R:edit", tr("✏️ تعديل بياناتي"))]
    if not p.get("is_subscribed"):
        buttons.insert(0, ("R:sub", tr("💳 اشترك")))
    if not (p.get("telegram_user_id") or 0) > 0:
        buttons.insert(0, ("R:tg:yes", tr("🔗 اربط بتلغرام")))
    api.buttons(wa_id, tr("أنت مسجّل في «فنّي» 👌\n\n{card}\n\n{line}", card=_flow().card_text(p), line=line) + extra,
                buttons)
    return "menu", {}


# ─────────────────────────── النصوص ───────────────────────────

def on_text(api, wa_id, state, data, body):
    r = data.setdefault("r", {})
    if state == "r_name":
        name = re.sub(r"\s+", " ", (body or "").strip())
        if not (2 <= len(name) <= 40):
            return _flow().hint_once(api, wa_id, state, data,
                                     lambda: api.text(wa_id, tr("اكتب اسمًا يتراوح طوله بين حرفين و40 حرفًا 🙏")))
        r["name"] = name
        return _ask_number(api, wa_id, data)
    if state == "r_ename":
        name = re.sub(r"\s+", " ", (body or "").strip())
        if not (2 <= len(name) <= 40) or not r.get("edit_id"):
            return _flow().hint_once(api, wa_id, state, data,
                                     lambda: api.text(wa_id, tr("اكتب اسمًا يتراوح طوله بين حرفين و40 حرفًا 🙏")))
        db.update_professional_name(r["edit_id"], name)
        return _status(api, wa_id, db.get_professional_by_id(r["edit_id"]), extra="\n\n" + tr("✅ تم تحديث بياناتك."))
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
            api.text(wa_id, tr("🌍 خيار «المدينة كاملة» متاح للمهن النادرة فقط. اكتب أرقام أحيائك (حتى {max}) من القائمة 👆",
                               max=MAX_DISTRICTS))
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
            wa_id, tr("📍 شارك موقعك من الزر أدناه (أو 📎 ← الموقع) لنحدد مدينتك وأحياءك.")))
    if state == "r_svc":
        return _flow().hint_once(api, wa_id, state, data, lambda: api.text(
            wa_id, tr("👆 اضغط زر «اختر الخدمات» في الرسالة أعلاه.")))
    if state == "r_confirm":
        return _flow().hint_once(api, wa_id, state, data, lambda: api.text(
            wa_id, tr("👆 اضغط «✅ تأكيد التسجيل» في الرسالة أعلاه، أو «✏️ البدء من جديد».")))
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
        tr("📱 هل تريد التسجيل على هذا الرقم؟\n+{me}\n\n(هو الرقم الذي سيتواصل عليه العملاء عبر واتساب)", me=me),
        [("R:num:me", tr("✅ نعم، هذا الرقم")), ("R:num:other", tr("📱 رقم آخر"))],
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
            api.text(wa_id, tr("هذا الرقم مسجّل مسبقًا في «فنّي» باسم «{name}».", name=p["full_name"]))
            if not db.is_wa_registrar(me) and not otp_enabled():
                return "menu", {}
            return _ask_number(api, wa_id, data)
        r.pop("phone", None)
        return _ask_top(api, wa_id, data)
    api.text(wa_id, tr("✍️ اكتب رقم واتساب الفني (مثل: 0501234567 أو 966501234567):"))
    return "r_phone", data


def _on_phone_text(api, wa_id, data, body):
    r = data["r"]
    me = _digits(wa_id)
    t = norm_phone(body, me)
    if not t:
        api.text(wa_id, tr("الرقم غير صحيح 🙏 اكتبه مثل: 0501234567 أو 966501234567"))
        return "r_phone", data
    if t == me:
        return _on_number_choice(api, wa_id, data, "me")
    p = _registered(t)
    if p:
        api.text(wa_id, tr("الرقم +{phone} مسجّل مسبقًا في «فنّي» باسم «{name}». اكتب رقمًا آخر:", phone=t, name=p["full_name"]))
        return "r_phone", data
    if db.is_wa_registrar(me):
        # المالك والمسوّقون: بدون رمز تحقق
        r["phone"] = t
        return _ask_top(api, wa_id, data, note=tr("✅ سيُسجَّل الفني على الرقم +{phone}\n\n", phone=t))
    return _send_otp(api, wa_id, data, t)


def _send_otp(api, wa_id, data, t):
    import secrets
    import time

    import config
    import nudges

    r = data["r"]
    me = _digits(wa_id)
    if db.count_otp_since(me) >= OTP_DAILY:
        api.text(wa_id, tr("⚠️ تجاوزت الحد المسموح لإرسال رموز التحقق اليوم. حاول غدًا، أو سجّل من جوال الفني نفسه."))
        return "r_phone", data
    code = f"{secrets.randbelow(900000) + 100000}"
    ok = False
    if nudges._in_free_window(t):
        # صاحب الرقم راسل البوت خلال 24 ساعة — رسالة عادية بدل القالب المدفوع
        # الرسالة لصاحب الرقم الآخر: بلغته المحفوظة لو راسلنا قبل، وإلا بلغة المسجِّل
        cur = get_lang()
        lang.set_lang(lang.load(t) or cur)
        otp_msg = tr("🔐 رمز التحقق لتسجيلك في «فنّي»: {code}\nلا تشاركه إلا مع الشخص الذي يسجّلك.", code=code)
        lang.set_lang(cur)
        res = api.text(t, otp_msg)
        ok = res is not None and getattr(res, "status_code", 500) < 400
    if not ok:
        for name in config.WA_TPL_VERIFY:
            res = api.auth_code(t, name.strip(), code)
            if res is not None and getattr(res, "status_code", 500) < 400:
                ok = True
                break
    if not ok:
        api.text(wa_id, tr("⚠️ تعذّر إرسال الرمز إلى +{phone}. تأكد أن الرقم صحيح وعليه واتساب، أو سجّل من جوال الفني نفسه.\n\n"
                           "✍️ اكتب الرقم مرة أخرى:", phone=t))
        return "r_phone", data
    db.log_otp(me, t)
    r.update(otp=code, otp_phone=t, otp_at=time.time(), otp_tries=0)
    api.text(wa_id, tr("📩 أرسلنا رمز تحقق إلى واتساب الرقم +{phone}.\nاطلب الرمز من صاحب الرقم، واكتبه هنا (صالح 10 دقائق):",
                       phone=t))
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
        api.text(wa_id, tr("⌛ انتهت صلاحية الرمز. اكتب الرقم مرة أخرى لإرسال رمز جديد:"))
        return "r_phone", data
    typed = re.sub(r"\D", "", (body or "").translate(str.maketrans("٠١٢٣٤٥٦٧٨٩", "0123456789")))
    if typed == r["otp"]:
        for k in ("otp", "otp_phone", "otp_at", "otp_tries"):
            r.pop(k, None)
        r["phone"] = t
        return _ask_top(api, wa_id, data, note=tr("✅ تم التحقق من الرقم +{phone}\n\n", phone=t))
    r["otp_tries"] = (r.get("otp_tries") or 0) + 1
    left = OTP_TRIES - r["otp_tries"]
    if left <= 0:
        for k in ("otp", "otp_phone", "otp_at", "otp_tries"):
            r.pop(k, None)
        api.text(wa_id, tr("❌ تجاوزت عدد المحاولات. اكتب الرقم مرة أخرى لإرسال رمز جديد:"))
        return "r_phone", data
    api.text(wa_id, tr("❌ الرمز غير صحيح. حاول مرة أخرى (المتبقي: {left}):", left=left))
    return "r_otp", data


# ─────────────────────────── المهنة ───────────────────────────

def _ask_top(api, wa_id, data, intro=None, note=""):
    """الـ9 الأكثر طلبًا + «المزيد» — نفس قائمة البحث."""
    from whatsapp_bot import top
    data.setdefault("r", {}).pop("more", None)
    more_n = max(len(top.all_professions()) - 9, 0)
    body = note + (intro or tr("أهلًا بك {name} 👋\n"
                               "ما هي مهنتك؟ اختر من القائمة التالية، أو اضغط «المزيد» للقائمة الموسّعة (+{n} مهنة)، "
                               "أو اكتب اسمها (مثل: سباك)", name=data["r"].get("name", ""), n=more_n)
                   + "\n\n" + tr("💡 يمكنك إضافة مهنة ثانية بعد إكمال التسجيل."))
    api.list(wa_id, body, tr("اختر مهنتك"), top.top_rows("R:"), section_title=tr("الأكثر طلبًا"))
    return "r_prof", data


def _ask_more(api, wa_id, data):
    from whatsapp_bot import top
    text, ids = top.more_message(tr("📋 باقي المهن:"))
    api.text(wa_id, text)
    data.setdefault("r", {})["more"] = ids
    return "r_prof", data


def _ask_domain(api, wa_id, page, data):
    f = _flow()
    items, prev, nxt = f._page(professions.get_domains(get_lang()), page)
    rows = [(f"R:dom:{d['id']}", d["name"], d["name"] if len(d["name"]) > 24 else None) for d in items]
    if nxt:
        rows.append((f"R:dpg:{page + 1}", tr("المزيد ⬅️"), tr("باقي المجالات")))
    if prev:
        rows.append((f"R:dpg:{page - 1}", tr("➡️ السابق"), None))
    api.list(wa_id, tr("تشرّفنا بك يا {name} 🌟\nاختر مجال مهنتك 👇 أو اكتب اسم مهنتك (مثل: سباك)",
                       name=data["r"].get("name", "")),
             tr("اختر المجال"), rows, section_title=tr("المجالات"))
    return "r_prof", data


def _ask_profession(api, wa_id, domain_id, page, data):
    profs = professions.get_professions_by_domain(domain_id, get_lang())
    if not profs:
        return _ask_top(api, wa_id, data)
    per = 7 if len(profs) > 9 else 9
    start_ = page * per
    rows = [(f"R:prof:{x['id']}", x["name"], x["name"] if len(x["name"]) > 24 else None) for x in profs[start_:start_ + per]]
    if start_ + per < len(profs):
        rows.append((f"R:ppg:{domain_id}:{page + 1}", tr("المزيد ⬅️"), None))
    if page > 0:
        rows.append((f"R:ppg:{domain_id}:{page - 1}", tr("➡️ السابق"), None))
    rows.append(("R:dpg:0", tr("↩️ العودة إلى المجالات"), None))
    api.list(wa_id, tr("اختر مهنتك 👇"), tr("اختر المهنة"), rows, section_title=tr("المهن"))
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
        api.text(wa_id, tr("هذا الرقم غير موجود في القائمة 🤔 اكتب رقمًا صحيحًا أو اسم المهنة."))
        return "r_prof", data
    syn = top.synonym_profession(text)
    if syn and professions.get_profession(syn, "ar")[1]:
        db.log_search_term(text, syn, professions.get_profession(syn, "ar")[1]["name"], "register")
        return _select_profession(api, wa_id, syn, data)
    f = _flow()
    scored = f.match_scored(text)   # بالعربي وبلغة المستخدم — والمهنة الراجعة بالعربي (للحفظ)
    if scored and (len(scored) == 1 or scored[0][0] == 0):
        db.log_search_term(text, scored[0][2]["id"], scored[0][2]["name"], "register")
        return _select_profession(api, wa_id, scored[0][2]["id"], data)
    db.log_search_term(text, None, "، ".join(x["name"] for _, _, x in scored[:3]) or None, "register")
    if scored:
        rows = []
        for _, _, x in scored[:9]:
            nm = f.prof_name(x["id"], x["name"])
            rows.append((f"R:prof:{x['id']}", nm, nm if len(nm) > 24 else None))
        rows.append(("R:top:more", tr("📋 كل المهن"), None))
        api.list(wa_id, tr("اختر مهنتك من النتائج 👇"), tr("اختر المهنة"), rows, section_title=tr("المهن"))
        return "r_prof", data
    return _ask_top(api, wa_id, data, tr("لم أجد مهنة باسم «{q}» 🤔\n\nاختر مهنتك من القائمة 👇 أو اكتب رقمها أو اسمها بصيغة أخرى",
                                         q=_flow().clip_text(text)))


def _select_profession(api, wa_id, pid, data):
    domain, prof = professions.get_profession(pid, "ar")
    if not prof:
        return _ask_top(api, wa_id, data)
    r = data.setdefault("r", {})
    if r.get("adding2"):
        # مهنة ثانية أثناء التسجيل (من شاشة المراجعة): نفس الأحياء — المهنة وخدماتها ثم نرجع للمراجعة
        if prof["id"] == r.get("pid"):
            api.text(wa_id, tr("هذه مهنتك الأولى نفسها 🙂 اختر مهنة أخرى."))
            return _ask_p2(api, wa_id, data)
        r.update(p2id=prof["id"], p2name=prof["name"], services1=list(r.get("services") or []),
                 all_services1=list(r.get("all_services") or []),
                 all_services=prof.get("services") or [], services=[])
        if r["all_services"]:
            return _ask_services(api, wa_id, data, 0)
        return _finish_add2(api, wa_id, data)
    if r.get("edit") == "p2":
        # المهنة الثانية: نفس المدينة والأحياء — بس المهنة وخدماتها
        if prof["id"] == r.get("pid"):
            api.text(wa_id, tr("هذه مهنتك الأولى نفسها 🙂 اختر مهنة أخرى."))
            return _ask_p2(api, wa_id, data)
        r.update(p2id=prof["id"], p2name=prof["name"], all_services=prof.get("services") or [], services=[])
        if r["all_services"]:
            return _ask_services(api, wa_id, data, 0)
        return _save_edit(api, wa_id, data)
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
        shown = [tr_service(sv) for sv in allsv]
        items = [{"id": "all", "title": tr("📋 كل الخدمات")}] + [
            {"id": str(i), "title": wa_flows.clip_title(sv), "description": sv if len(sv) > wa_flows.TITLE_MAX else None}
            for i, sv in enumerate(shown)]
        if wa_flows.send(api, wa_id, "services",
                         tr("ما الخدمات التي تقدمها في مهنة «{pname}»؟ 👇\n"
                            "اضغط الزر، وحدّد كل خدماتك ☑️ ثم «تم التحديد».", pname=_pname(r)),
                         tr("اختر الخدمات"), tr("حدّد كل الخدمات التي تقدمها:"), items, f"svc:{_digits(wa_id)}"):
            return "r_svc", data
    left = [(i, sv) for i, sv in enumerate(allsv) if sv not in chosen]
    if not left:
        return _ask_location(api, wa_id, data)
    rows = []
    if chosen:
        rows.append(("R:svcdone", tr("✅ تم التحديد ({n})", n=len(chosen)), tr("الانتقال إلى الخطوة التالية")))
    room = 10 - len(rows) - 1
    for i, sv in left[:room]:
        sv = tr_service(sv)
        rows.append((f"R:svc:{i}", sv, sv if len(sv) > 24 else None))
    rows.append(("R:svcall", tr("📋 كل الخدمات"), tr("أقدّم جميع خدمات المهنة")))
    if chosen:
        head = tr("✅ اخترت: {items}\n\nاختر خدمة أخرى، أو اضغط «تم التحديد» 👇",
                  items=_flow().join_list(tr_service(c) for c in chosen))
    else:
        head = tr("ما الخدمات التي تقدمها في مهنة «{pname}»؟ 👇\n"
                  "يمكنك اختيار أكثر من خدمة (واحدة بعد الأخرى)، أو «كل الخدمات».", pname=_pname(r))
    api.list(wa_id, head, tr("اختر الخدمات"), rows, section_title=tr("الخدمات"))
    return "r_svc", data


# ─────────────────────────── الموقع ───────────────────────────

def _ask_location(api, wa_id, data):
    if data.get("r", {}).get("edit") in ("svc", "p2"):
        return _save_edit(api, wa_id, data)
    if data.get("r", {}).get("adding2"):
        return _finish_add2(api, wa_id, data)
    api.location_request(wa_id, tr("📍 شارك موقعك (مكان عملك أو منزلك) من الزر أدناه، لنحدد مدينتك وأقرب الأحياء إليك."))
    return "r_loc", data


def on_location(api, wa_id, data, lat, lon):
    r = data.setdefault("r", {})
    if not r.get("pid"):
        return start(api, wa_id)
    res = db.find_nearest_sa_city_and_district_by_coords(lat, lon, countries.enabled_codes("wa"))
    if not res or not res[0]:
        api.text(wa_id, tr("لم نتمكن من تحديد مدينتك من هذا الموقع 😅 جرّب إرسال موقع آخر."))
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
    rows.append(("R:dmore", tr("🔎 أحيائي ليست هنا"), tr("اعرض أحياء أخرى")))
    if chosen:
        rows.append(("R:ddone", tr("✔️ انتهيت ({n})", n=len(chosen)), None))
    if r.get("wide"):
        rows.append(("R:dwhole", tr("🌍 كل {city}", city=r["city"]), tr("أخدم المدينة كاملة")))
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
    head = tr("✅ اخترت: {items}\nهل تريد إضافة حي آخر؟ 👇", items=_flow().join_list(chosen_names)) if chosen_names else \
        tr("ما الأحياء التي تخدمها في {city}؟ 👇 (يمكنك اختيار أكثر من حي)\nأو اكتب اسم الحي", city=r["city"])
    api.list(wa_id, head, tr("اختر الحي"), _district_rows(r), section_title=tr("أقرب الأحياء إليك"))
    return "r_dist", data


MAX_DISTRICTS = 5   # نفس حد تلغرام


def _ask_near_districts(api, wa_id, data):
    """قائمة أقرب الأحياء لموقعه (حتى 9) — تحت كل حي اسم المدينة، والصف الأخير «قائمة الأحياء كاملة».
    يضغط حي حي (حتى 5)، وبعد أول اختيار يظهر «✅ تم التحديد»."""
    r = data["r"]
    chosen = r.setdefault("chosen", [])
    if len(chosen) >= MAX_DISTRICTS:
        return _confirm(api, wa_id, data, tr("ℹ️ وصلت إلى الحد الأقصى ({max} أحياء).\n", max=MAX_DISTRICTS))
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
            items.append({"id": "whole", "title": tr("🌍 كل {city}", city=r["city"]), "description": tr("أخدم المدينة كاملة")})
        items.append({"id": "full", "title": tr("📋 حيّي ليس هنا"),
                      "description": tr("اعرض كل أحياء {city} مرقّمة", city=r["city"])})
        if wa_flows.send(api, wa_id, "districts",
                         tr("📍 {city} — ما الأحياء التي تعمل فيها؟ 👇\n"
                            "اضغط الزر، وحدّد أحياءك ☑️ (حتى {max}) ثم «تم التحديد».", city=r["city"], max=MAX_DISTRICTS),
                         tr("اختر أحياءك"), tr("أقرب الأحياء إلى موقعك — حدّد حتى {max}:", max=MAX_DISTRICTS), items,
                         f"dist:{_digits(wa_id)}"):
            return "r_dist", data
    rows = []
    if chosen:
        rows.append(("R:ddone", tr("✅ تم التحديد ({n})", n=len(chosen)), tr("الانتقال إلى المراجعة")))
    extra = [("R:dwhole", tr("🌍 كل {city}", city=r["city"])[:24], tr("أخدم المدينة كاملة"))] if r.get("wide") else []
    room = 10 - len(rows) - 1 - len(extra)
    for did in [d for d in r["near_ids"] if d not in chosen][:min(room, 9)]:
        d = db.get_sa_district_by_id(did)
        if d:
            rows.append((f"R:d:{did}", clip_name(d["name"]), r["city"]))
    rows += extra
    rows.append(("R:dall", tr("📋 قائمة الأحياء كاملة"), tr("كل أحياء {city} مرقّمة", city=r["city"])))
    if chosen:
        names = [db.get_sa_district_by_id(d)["name"] for d in chosen if db.get_sa_district_by_id(d)]
        head = tr("✅ اخترت: {items}\n\nاختر حيًّا آخر (حتى {max})، أو اضغط «تم التحديد» 👇",
                  items=_flow().join_list(names), max=MAX_DISTRICTS)
    else:
        head = tr("📍 {city} — ما الأحياء التي تعمل فيها؟ 👇\n"
                  "هذه أقرب الأحياء إلى موقعك. يمكنك اختيار حتى {max} أحياء (واحدًا بعد الآخر).",
                  city=r["city"], max=MAX_DISTRICTS)
    api.list(wa_id, head, tr("اختر الحي"), rows, section_title=tr("أقرب الأحياء إليك"))
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
        wa_id, tr("👆 اختر أحياءك من الرسالة أعلاه (زر «اختر الحي» أو «اختر أحياءك»).")))


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
    whole = "#. " + tr("🌍 كل {city} (المدينة كاملة)", city=r["city"]) if r.get("wide") else None
    head = tr("📍 أحياء {city} (الأقرب إلى موقعك أولًا) 👇\n"
              "اكتب *أرقام* الأحياء التي تعمل فيها — حتى {max} أحياء، كل رقم في سطر، مثل:\n1\n4\n9",
              city=r["city"], max=MAX_DISTRICTS)
    _flow().send_numbered(api, wa_id, head, None, tr("✍️ اكتب أرقام أحيائك (حتى {max}).", max=MAX_DISTRICTS),
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
        api.text(wa_id, tr("هذه الأرقام غير موجودة في القائمة 🤔 اكتب أرقامًا من 1 إلى {n}.", n=len(r["dlist"])))
        return "r_dist", data
    note = ""
    if len(ids) > MAX_DISTRICTS:
        ids = ids[:MAX_DISTRICTS]
        note += tr("ℹ️ الحد الأقصى {max} أحياء — اعتمدنا أول {max}.\n", max=MAX_DISTRICTS)
    if bad:
        note += tr("ℹ️ تجاهلنا أرقامًا غير موجودة: {nums}\n", nums=_flow().join_list(map(str, bad)))
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
        api.text(wa_id, tr("🔎 الأحياء التي تحتوي على «{q}»:\n{lines}\n\n✍️ اكتب *أرقام* أحيائك (حتى {max})، كل رقم في سطر.",
                           q=f.clip_text(text), lines="\n".join(hits[:15]), max=MAX_DISTRICTS))
    else:
        api.text(wa_id, tr("✍️ اكتب *أرقام* الأحياء من القائمة أعلاه 👆 (حتى {max})، كل رقم في سطر، مثل:\n12\n40\n7",
                           max=MAX_DISTRICTS)
                 + "\n" + (tr("أو اكتب اسم الحي لأعرض لك رقمه.") if len(q) < 2
                           else tr("لم أجد حيًّا يحتوي على «{q}».", q=f.clip_text(text)))
                 + ("\n" + tr("🌍 أو # لكل المدينة.") if r.get("wide") else ""))
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
    api.text(wa_id, tr("لم أجد حيًّا بهذا الاسم في {city} 🤔", city=r["city"]))
    return _ask_districts(api, wa_id, data)


def _add_district(api, wa_id, data, did):
    r = data["r"]
    if did not in r.setdefault("chosen", []):
        r["chosen"].append(did)
    return _ask_districts(api, wa_id, data)


# ─────────────────────────── المراجعة والحفظ ───────────────────────────

def _finish_add2(api, wa_id, data):
    """خلصت خدمات المهنة الثانية أثناء التسجيل ← ندمجها مع خدمات الأولى ونرجع للمراجعة."""
    r = data["r"]
    first = r.pop("services1", []) or []
    r["services"] = first + [sv for sv in (r.get("services") or []) if sv not in first]
    r["all_services"] = r.pop("all_services1", r.get("all_services"))
    r.pop("adding2", None)
    return _confirm(api, wa_id, data)


def _confirm(api, wa_id, data, note=""):
    r = data["r"]
    if r.get("edit") == "dist":
        return _save_edit(api, wa_id, data)
    if r.get("whole") or not r.get("has_d"):
        where = tr("{city} — المدينة كاملة 🌍", city=r["city"])
    else:
        names = [db.get_sa_district_by_id(d)["name"] for d in r.get("chosen", [])]
        where = f"{r['city']} — " + _flow().join_list(names)
    services = _flow().join_list(tr_service(s) for s in (r.get("services") or [])) or "—"
    api.buttons(
        wa_id,
        tr("{note}راجع بياناتك قبل التسجيل 👇\n\n"
           "👷 {name}\n🛠️ {pname}\n📋 {services}\n📍 {country} / {where}\n"
           "📱 رقم التواصل للعملاء: +{phone}", note=note, name=r["name"],
           pname=_pname({"pid": r.get("pid"), "pname": r.get("pname")})
           + (" • " + _flow().prof_name(r["p2id"], r.get("p2name")) if r.get("p2id") else ""), services=services,
           country=countries.name(r["country"], get_lang()), where=where, phone=tech_phone(r, wa_id)),
        [("R:ok", tr("✅ تأكيد التسجيل"))]
        + ([("R:dedit", tr("📍 تعديل الأحياء"))] if r.get("has_d") else [])
        + ([("R:redo", tr("✏️ البدء من جديد"))] if r.get("p2id") else [("R:add2", tr("➕ إضافة مهنة أخرى"))]),
    )
    return "r_confirm", data


def _save(api, wa_id, data):
    _professional_card_text = _flow().card_text   # بطاقة بلغة المستخدم (العربي = بطاقة تلغرام)
    r = data["r"]
    digits = tech_phone(r, wa_id)
    other = digits != _digits(wa_id)
    if _registered(digits):
        api.text(wa_id, tr("الرقم +{phone} مسجّل مسبقًا في «فنّي».", phone=digits))
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
        "profession2_id": r.get("p2id"),
        "profession2_name": r.get("p2name"),
        "covers_whole_city": whole,
        "source": "whatsapp",
        "registered_by": _digits(wa_id) if other else None,
    })
    _notify_admin_async(row_id)
    p = db.get_professional_by_id(row_id)
    if other:
        _notify_registered(api, digits, r["name"], r["pname"])
        # سجّل فنيًا آخر: رسالة وحدة (بطاقة + أزرار) — بدون سؤال ربط تلغرام (يخص صاحب الرقم)
        api.buttons(wa_id, tr("🎉 تم تسجيل الفني «{name}» على الرقم +{phone}، وأصبح يظهر للعملاء.\n\n", name=r["name"], phone=digits)
                    + _professional_card_text(p),
                    [("R:again", tr("➕ تسجيل فني آخر")), ("m:search", tr("🔍 ابحث عن فني"))])
        return "menu", {}
    api.text(wa_id, tr("🎉 تم تسجيلك! وأصبحت تظهر للعملاء الذين يبحثون في واتساب وتلغرام.\n\nهذه بطاقتك كما يراها العميل:\n\n")
             + _professional_card_text(p))
    api.buttons(
        wa_id,
        tr("هل تريد إضافة بياناتك في تطبيق تلغرام أيضًا؟ 🔗\nستصلك هناك تنبيهات العملاء مجانًا، ويمكنك إدارة حسابك واشتراكك."),
        [("R:tg:yes", tr("✅ نعم، أضفها")), ("R:tg:no", tr("لا، شكرًا"))],
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
        api.text(wa_id, tr("حسابك مربوط بتلغرام بالفعل ✅"))
        return "menu", {}
    url = f"https://t.me/{TELEGRAM_BOT}?start={contact_links.link_token(p['id'])}"
    api.cta_url(wa_id, tr("اضغط الزر، ثم اضغط «ابدأ» (Start) في تلغرام — وسيُربط حسابك تلقائيًا ✅"),
                tr("فتح تلغرام"), url)
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


# ─────────────────────────── تعديل بيانات الفني المسجّل ───────────────────────────
# (بدون تعديل المهنة — من يريد مهنة أخرى يحذف حسابه ويسجّل من جديد، طلب المالك)

def _edit_menu(api, wa_id):
    p = db.get_professional_for_wa(wa_id)
    if not p:
        return start(api, wa_id)
    rows = []
    if _services_for(p):
        rows.append(("R:ed:svc", tr("🛠️ الخدمات"), None))
    rows += [("R:ed:dist", tr("📍 الأحياء"), None), ("R:ed:name", tr("👷 الاسم"), None)]
    if p.get("profession2_id"):
        rows += [("R:ed:p2", tr("🔄 تغيير المهنة الثانية"), _pname_of(p["profession2_id"], p["profession2_name"])),
                 ("R:ed:p2del", tr("🗑️ حذف المهنة الثانية"), _pname_of(p["profession2_id"], p["profession2_name"]))]
    else:
        rows.append(("R:ed:p2", tr("➕ إضافة مهنة ثانية"), tr("بنفس مدينتك وأحيائك")))
    api.list(wa_id, tr("✏️ ماذا تريد أن تعدّل؟ 👇\n(لتغيير المهنة: احذف حسابك بكتابة d ثم سجّل من جديد)"),
             tr("اختر"), rows, section_title=tr("تعديل بياناتي"))
    return "menu", {}


def _pname_of(pid, ar_name):
    _, pr = professions.get_profession(pid, _lang()) if pid else (None, None)
    return (pr or {}).get("name") or ar_name


def _lang():
    from whatsapp_bot.lang import get_lang
    return get_lang()


def _services_for(p) -> list[str]:
    """كل خدمات مهنتي الفني (الأولى + الثانية) بدون تكرار."""
    out = []
    for pid in (p.get("profession_id"), p.get("profession2_id")):
        if pid:
            _, pr = professions.get_profession(pid, "ar")
            for sv in (pr or {}).get("services") or []:
                if sv not in out:
                    out.append(sv)
    return out


def _ask_p2(api, wa_id, data):
    from whatsapp_bot import top
    data["r"].pop("more", None)
    api.list(wa_id, tr("➕ اختر مهنتك الثانية 👇 (ستظهر بها للعملاء في نفس مدينتك وأحيائك)\n"
                       "أو اضغط «المزيد»، أو اكتب اسمها."),
             tr("اختر مهنتك"), top.top_rows("R:"), section_title=tr("الأكثر طلبًا"))
    return "r_prof", data


def _start_edit(api, wa_id, what):
    p = db.get_professional_for_wa(wa_id)
    if not p:
        return start(api, wa_id)
    _, prof = professions.get_profession(p["profession_id"], "ar")
    r = {"edit": what, "edit_id": p["id"], "name": p["full_name"], "pid": p["profession_id"],
         "pname": p["profession_name"], "wide": bool(prof and prof.get("allow_city_wide")),
         "all_services": (prof or {}).get("services") or [], "services": []}
    r["all_services"] = _services_for(p) or r["all_services"]
    data = {"r": r}
    if what == "p2":
        return _ask_p2(api, wa_id, data)
    if what == "p2del":
        keep1 = (prof or {}).get("services") or []
        cur = []
        try:
            cur = json.loads(p.get("services_json") or "[]")
        except ValueError:
            pass
        db.set_profession2(p["id"], None, None, [sv for sv in cur if sv in keep1])
        return _status(api, wa_id, db.get_professional_by_id(p["id"]), extra="\n\n" + tr("✅ تم تحديث بياناتك."))
    if what == "svc" and r["all_services"]:
        return _ask_services(api, wa_id, data)
    if what == "name":
        api.text(wa_id, tr("✍️ اكتب الاسم الجديد (الاسم الذي سيظهر للعملاء):"))
        return "r_ename", data
    return _ask_location(api, wa_id, data)


def _save_edit(api, wa_id, data):
    r = data["r"]
    pid = r.get("edit_id")
    if not pid:
        return start(api, wa_id)
    if r["edit"] == "svc":
        db.update_professional_services(pid, r.get("services") or [])
    elif r["edit"] == "p2":
        p = db.get_professional_by_id(pid)
        _, pr1 = professions.get_profession(p["profession_id"], "ar")
        keep1 = (pr1 or {}).get("services") or []
        try:
            cur = json.loads(p.get("services_json") or "[]")
        except ValueError:
            cur = []
        merged = [sv for sv in cur if sv in keep1] + [sv for sv in (r.get("services") or []) if sv not in keep1]
        db.set_profession2(pid, r["p2id"], r["p2name"], merged)
    elif r["edit"] == "dist":
        whole = bool(r.get("whole") or not r.get("has_d"))
        db.update_professional_area(pid, r["country"], r["city"], r["city_id"],
                                    [] if whole else list(r.get("chosen") or []), whole)
    p = db.get_professional_by_id(pid)
    return _status(api, wa_id, p, extra="\n\n" + tr("✅ تم تحديث بياناتك."))


# ─────────────────────────── الأزرار ───────────────────────────

def on_choice(api, wa_id, rid, state, data):
    p = rid.split(":")[1:]
    act = p[0] if p else ""
    r = data.setdefault("r", {})
    if act == "edit":
        return _edit_menu(api, wa_id)
    if act == "ed":
        return _start_edit(api, wa_id, p[1] if len(p) > 1 else "")
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
        return _status(api, wa_id, p, extra="\n\n" + tr("📢 تابع قناة «فنّي» على واتساب: {url}", url=_flow().CHANNEL_URL))
    if act == "mute":
        p = db.get_professional_for_wa(wa_id)
        if p:
            db.set_notify_off(p["id"], "whatsapp", True)
            db.mark_notifications_responded(p["id"])
        api.text(wa_id, tr("🔕 تم إيقاف الإشعارات. إذا أردت إعادة تفعيلها فتواصل مع إدارة «فنّي»."))
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
        api.text(wa_id, tr("حسنًا 👍 يمكنك ربطه في أي وقت من «🛠️ أنا فني». اكتب s للعودة إلى القائمة."))
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
    if act == "add2":
        if r.get("pid") and r.get("city_id") and not r.get("p2id"):
            r["adding2"] = True
            return _ask_p2(api, wa_id, data)
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
