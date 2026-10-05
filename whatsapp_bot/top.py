# قائمة المهن بواتساب: 9 مهن ثابتة (الأكثر طلبًا) + «➕ المزيد».
#
# - الـ9 ما تتغير تلقائيًا — المالك يختارها من لوحة التحكم (صفحة «المهن الأكثر طلبًا»)
#   وتنحفظ بجدول settings بالمفتاح wa_top9.
# - «المزيد» = رسالة وحدة فيها باقي المهن مرقّمة، مرتبة حسب الأكثر بحثًا (تتغير تلقائيًا)،
#   والعميل يرد برقم المهنة أو اسمها. نفس الشي بتسجيل الفني.
# - رسالة وحدة بدل قوائم مجالات متعددة = ردود أقل = تكلفة أقل على واتساب.

import db
import professions_repo as professions

SETTING_KEY = "wa_top9"

# مبنية على بحث (تطبيقات الصيانة بالسعودية) + تصحيح المالك: فني التكييف يصلح الثلاجات
# والغسالات (فما نكرر «أجهزة منزلية»)، وما فيه عاملات نظافة مستقلات بالسعودية والخليج.
# تُستخدم لين المالك يغيّرها من اللوحة (صفحة «الأكثر طلبًا»).
DEFAULT_TOP = ["p13", "p12", "p17", "p63", "p64", "p26", "p14", db.SATELLITE_PROFESSION_ID, "p59"]

DESCS = {
    "p13": "مكيفات، ثلاجات، غسالات ملابس",
    "p12": "تسريب، انسداد، خلاطات، سخانات",
    "p17": "التماس، تركيب إنارة، لوحات كهرباء",
    "p63": "صراصير، نمل أبيض، بق الفراش",
    "p64": "فك وتركيب ونقل أثاث، دينا",
    "p26": "فك وتركيب غرف نوم، خزائن، أثاث",
    "p14": "دهان شقق، ترميم، ورق جدران",
    db.SATELLITE_PROFESSION_ID: "تركيب دش، برمجة، كاميرات مراقبة",
    "p59": "شبابيك، أبواب، مطابخ ألمنيوم",
    "p5": "أبواب خشب، خزائن، ديكور",
    "p70": "عدم تصريف، تسريب، لا تسخّن",
    "p71": "أفران غاز وكهرباء وبلت إن",
}

_AR_DIGITS = str.maketrans("٠١٢٣٤٥٦٧٨٩۰۱۲۳۴۵۶۷۸۹", "01234567890123456789")


def to_number(text: str) -> int | None:
    t = (text or "").strip().translate(_AR_DIGITS).rstrip(".-) ")
    return int(t) if t.isdigit() and len(t) <= 3 else None


def all_professions() -> list[dict]:
    out = []
    for d in professions.get_domains("ar"):
        out.extend(professions.get_professions_by_domain(d["id"], "ar"))
    return out


def top_ids_setting() -> list[str]:
    raw = db.get_setting(SETTING_KEY, "")
    ids = [x.strip() for x in raw.split(",") if x.strip()] if raw else []
    return ids or list(DEFAULT_TOP)


def top_professions(all_profs: list[dict] | None = None) -> list[dict]:
    by_id = {p["id"]: p for p in (all_profs or all_professions())}
    out, seen = [], set()
    for pid in top_ids_setting():
        if pid in by_id and pid not in seen:
            out.append(by_id[pid])
            seen.add(pid)
    return out[:9]


def rest_by_demand(all_profs: list[dict] | None = None) -> list[dict]:
    """باقي المهن (غير الـ9) مرتبة حسب عدد مرات البحث — المتساوية تبقى بترتيبها الأصلي."""
    all_profs = all_profs or all_professions()
    top = {p["id"] for p in top_professions(all_profs)}
    pop = db.get_profession_popularity()
    rest = [p for p in all_profs if p["id"] not in top]
    rest.sort(key=lambda p: pop.get(p["id"], 0), reverse=True)
    return rest


def desc_for(p: dict) -> str | None:
    if p["id"] in DESCS:
        return DESCS[p["id"]]
    services = p.get("services") or []
    return "، ".join(services[:3]) or None


def top_rows(prefix: str = "") -> list[tuple]:
    """صفوف قائمة واتساب: 9 مهن + المزيد (10 = حد واتساب)."""
    all_profs = all_professions()
    top = top_professions(all_profs)
    rows = [(f"{prefix}prof:{p['id']}", p["name"], desc_for(p)) for p in top]
    rows.append((f"{prefix}top:more", "➕ المزيد", f"باقي المهن ({len(all_profs) - len(top)} مهنة)"))
    return rows


def more_message(intro: str) -> tuple[str, list[str]]:
    """نص رسالة «المزيد» المرقّمة + ترتيب المعرّفات (عشان نعرف وش يقصد بالرقم)."""
    rest = rest_by_demand()
    lines = [f"{i}. {p['name']}" for i, p in enumerate(rest, 1)]
    text = f"{intro}\n\n" + "\n".join(lines) + "\n\n✍️ اكتب *رقم* المهنة (مثل: 3) أو اسمها."
    return text, [p["id"] for p in rest]


def pick_by_number(n: int, data_more: list | None) -> str | None:
    """الرقم بعد «المزيد» = من القائمة المرقمة. بدونها: 1-9 = الـ9 الأساسية."""
    if data_more:
        return data_more[n - 1] if 1 <= n <= len(data_more) else None
    top = top_professions()
    return top[n - 1]["id"] if 1 <= n <= len(top) else None


# كلمات الناس اليومية ← المهنة (العميل يكتب «مكيف» مو «فني تكييف وتبريد»)
SYNONYMS = [
    (("غساله صحون", "غسالة صحون", "جلايه", "جلاية"), "p70"),
    (("فرن", "افران", "أفران", "طباخ"), "p71"),
    (("مكيف", "مكيفات", "تكييف", "مكيفة", "سبليت", "اسبلت", "فريون"), "p13"),
    (("دش", "ستلايت", "ستالايت", "رسيفر", "كاميرات", "كاميرا مراقبه", "كاميرا مراقبة"), db.SATELLITE_PROFESSION_ID),
    (("عفش", "نقل اثاث", "نقل أثاث", "دينا", "وانيت نقل"), "p64"),
    (("حشرات", "صراصير", "رش مبيد", "رش", "نمل ابيض", "بق"), "p63"),
    (("سباكه", "سباكة", "تسريب", "تسربات", "مواسير", "انسداد", "مجاري"), "p12"),
    (("كهربا", "كهرباء", "كهربائي", "التماس"), "p17"),
    (("بويه", "بوية", "صباغ", "دهانات"), "p14"),
    (("المنيوم", "ألمنيوم", "الومنيوم"), "p59"),
]


def synonym_profession(text: str) -> str | None:
    """لو الكلام فيه كلمة يومية معروفة لمهنة، يرجع رقم المهنة (الأطول تطابقًا أول)."""
    t = " " + " ".join((text or "").replace("ة", "ه").split()) + " "
    best = None
    for words, pid in SYNONYMS:
        for w in words:
            w2 = w.replace("ة", "ه")
            if f" {w2} " in t or t.strip().startswith(w2) and len(w2) >= 3 and w2 in t:
                if not best or len(w2) > best[0]:
                    best = (len(w2), pid)
    return best[1] if best else None
