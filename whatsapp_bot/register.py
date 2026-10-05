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
    p = db.get_professional_by_wa_id(_digits(wa_id))
    if p and p.get("status") != db.STATUS_REJECTED:
        return _status(api, wa_id, p)
    api.text(wa_id, "مرحبًا بك 🙌 سنسجّلك في «فنّي» مجانًا خلال دقيقة، لتظهر للعملاء في واتساب وتلغرام.\n\n"
                    "✍️ اكتب اسمك (الاسم الذي سيظهر للعملاء):")
    return "r_name", {"r": {}}


def _status(api, wa_id, p):
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
    api.buttons(wa_id, f"أنت مسجّل في «فنّي» 👌\n\n{_professional_card_text(p)}\n\n{line}", buttons)
    return "menu", {}


# ─────────────────────────── النصوص ───────────────────────────

def on_text(api, wa_id, state, data, body):
    r = data.setdefault("r", {})
    if state == "r_name":
        name = re.sub(r"\s+", " ", (body or "").strip())
        if not (2 <= len(name) <= 40):
            api.text(wa_id, "اكتب اسمًا يتراوح طوله بين حرفين و40 حرفًا 🙏")
            return state, data
        r["name"] = name
        return _ask_top(api, wa_id, data)
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
        picked = _pick_district_numbers(api, wa_id, data, body)
        if picked:
            return picked
        return _hint_district_numbers(api, wa_id, data, body)
    if state in ("r_loc", "r_locok"):
        api.location_request(wa_id, "📍 شارك موقعك من الزر أدناه (أو 📎 ← الموقع) لنحدد مدينتك وأحياءك.")
        return "r_loc", data
    if state == "r_svc":
        return _ask_services(api, wa_id, data, r.get("svc_page", 0))
    if state == "r_confirm":
        return _confirm(api, wa_id, data)
    return state, data


# ─────────────────────────── المهنة ───────────────────────────

def _ask_top(api, wa_id, data, intro=None):
    """الـ9 الأكثر طلبًا + «المزيد» — نفس قائمة البحث."""
    from whatsapp_bot import top
    data.setdefault("r", {}).pop("more", None)
    more_n = max(len(top.all_professions()) - 9, 0)
    body = intro or (f"أهلًا بك {data['r'].get('name', '')} 👋\n"
                     f"ما هي مهنتك؟ اختر من القائمة التالية، أو اضغط «المزيد» للقائمة الموسّعة (+{more_n} مهنة)، "
                     "أو اكتب اسمها (مثل: سباك)")
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

def _ask_services(api, wa_id, data, page):
    r = data["r"]
    allsv, chosen = r["all_services"], r.get("services", [])
    per = 7
    if page * per >= len(allsv):
        page = 0
    r["svc_page"] = page
    rows = []
    for i in range(page * per, min(len(allsv), page * per + per)):
        mark = "✅ " if allsv[i] in chosen else ""
        rows.append((f"R:svc:{i}", mark + allsv[i], allsv[i] if len(mark + allsv[i]) > 24 else None))
    if len(allsv) > per:
        rows.append((f"R:svcpg:{page + 1}", "المزيد ⬅️", "باقي الخدمات"))
    rows.append(("R:svcdone", f"✔️ انتهيت ({len(chosen)})" if chosen else "✔️ تخطي", None))
    rows.append(("R:svcall", "📋 كل الخدمات", "أقدّم جميع خدمات المهنة"))
    picked = ("\n✅ اخترت: " + "، ".join(chosen)) if chosen else ""
    api.list(wa_id, f"ما الخدمات التي تقدمها في مهنة «{r['pname']}»؟ اخترها واحدة تلو الأخرى، ثم اضغط «انتهيت» 👇{picked}",
             "اختر الخدمات", rows, section_title="الخدمات")
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
    api.buttons(wa_id, f"📍 موقعك: {countries.name(r['country'], 'ar')} / {city['name']}\nهل هذا صحيح؟",
                [("R:locok", "✅ نعم، صحيح"), ("R:locno", "❌ لا، أعد التحديد")])
    return "r_locok", data


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
        f"📱 رقم التواصل للعملاء: +{_digits(wa_id)}",
        [("R:ok", "✅ تأكيد التسجيل")]
        + ([("R:dedit", "📍 تعديل الأحياء")] if r.get("has_d") else [])
        + [("R:redo", "✏️ البدء من جديد")],
    )
    return "r_confirm", data


def _save(api, wa_id, data):
    from handlers.search import _professional_card_text

    r = data["r"]
    digits = _digits(wa_id)
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
    })
    _notify_admin_async(row_id)
    p = db.get_professional_by_id(row_id)
    api.text(wa_id, "🎉 تم تسجيلك! وأصبحت تظهر للعملاء الذين يبحثون في واتساب وتلغرام.\n\nهذه بطاقتك كما يراها العميل:\n\n"
             + _professional_card_text(p))
    api.buttons(
        wa_id,
        "هل تريد إضافة بياناتك في تطبيق تلغرام أيضًا؟ 🔗\nستصلك هناك تنبيهات العملاء مجانًا، ويمكنك إدارة حسابك واشتراكك.",
        [("R:tg:yes", "✅ نعم، أضفها"), ("R:tg:no", "لا، شكرًا")],
    )
    return "r_done", {"r": {"saved_id": row_id}}


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
    if not r.get("name"):            # زر قديم من جلسة منتهية
        return start(api, wa_id)
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
            s = r["all_services"][i]
            r.setdefault("services", [])
            r["services"].remove(s) if s in r["services"] else r["services"].append(s)
        return _ask_services(api, wa_id, data, r.get("svc_page", 0))
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
    if act == "locok":
        if r.get("has_d"):
            r["chosen"], r["whole"] = [], False
            return _ask_districts_numbered(api, wa_id, data)
        return _confirm(api, wa_id, data)
    if act == "dedit":
        if r.get("has_d"):
            r["chosen"], r["whole"] = [], False
            return _ask_districts_numbered(api, wa_id, data)
        return _confirm(api, wa_id, data)
    if act == "d":
        return _add_district(api, wa_id, data, int(p[1]))
    if act == "dmore":
        return _ask_districts(api, wa_id, data, new_page=True)
    if act == "ddone":
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
