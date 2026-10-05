# تقسيم أحياء المدن الكبيرة (أكثر من 60 حي) لمجموعات متقاربة جغرافيًا (طلب المالك).
#
# كل مجموعة = أحياء قريبة من بعض (تجميع k-means على إحداثيات مراكز الأحياء)، وتنسمّى
# حسب اتجاهها من وسط المدينة (شمال، جنوب شرق، وسط…) + اسم حي معروف بنصها. داخل المجموعة
# الأحياء مرتبة سلسلة (كل حي بعده أقرب حي له) عشان الجيران يجون ورا بعض بالقائمة.
# الترقيم يبقى متسلسل على كل القائمة (1، 2، 3…) — المجموعات بس عناوين تسهّل البحث بالعين.

import math
import re

import db

GROUP_MIN_DISTRICTS = 60   # أقل من كذا: قائمة وحدة بدون مجموعات
TARGET_GROUP_SIZE = 22
MAX_GROUP_SIZE = 32
MIN_GROUP_SIZE = 8

_DIRS = ["شمال", "شمال شرق", "شرق", "جنوب شرق", "جنوب", "جنوب غرب", "غرب", "شمال غرب"]
_cache: dict = {}


def _xy(lat, lon, lat0):
    return lon * math.cos(math.radians(lat0)), lat


def _d2(a, b):
    return (a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2


def _short(name: str) -> str:
    return re.sub(r"^حي\s+", "", name or "")


def _kmeans(points: list[tuple], k: int) -> list[int]:
    # بذور ثابتة (أبعد نقطة عن اللي قبلها) عشان النتيجة نفسها كل مرة لنفس المدينة
    seeds = [min(range(len(points)), key=lambda i: (points[i][1], points[i][0]))]
    while len(seeds) < k:
        seeds.append(max(range(len(points)), key=lambda i: min(_d2(points[i], points[s]) for s in seeds)))
    cents = [points[s] for s in seeds]
    assign = [0] * len(points)
    for _ in range(30):
        new = [min(range(k), key=lambda c: _d2(p, cents[c])) for p in points]
        if new == assign and _ > 0:
            break
        assign = new
        for c in range(k):
            mem = [points[i] for i in range(len(points)) if assign[i] == c]
            if mem:
                cents[c] = (sum(p[0] for p in mem) / len(mem), sum(p[1] for p in mem) / len(mem))
    return assign


def _chain(items: list[dict], start_xy) -> list[dict]:
    """ترتيب سلسلة: نبدأ بأقرب حي لنقطة البداية، وبعده كل مرة أقرب حي للي قبله."""
    left = list(items)
    out = []
    cur = start_xy
    while left:
        nxt = min(left, key=lambda d: _d2(d["_xy"], cur))
        out.append(nxt)
        left.remove(nxt)
        cur = nxt["_xy"]
    return out


def _build(city_id: int) -> dict | None:
    ds = db.list_sa_districts_by_city(city_id)
    if len(ds) <= GROUP_MIN_DISTRICTS:
        return None
    with_c = [dict(d) for d in ds if d.get("lat") is not None and d.get("lon") is not None]
    no_c = [d for d in ds if d.get("lat") is None or d.get("lon") is None]
    if len(with_c) < GROUP_MIN_DISTRICTS // 2:
        return None
    lat0 = sum(d["lat"] for d in with_c) / len(with_c)
    for d in with_c:
        d["_xy"] = _xy(d["lat"], d["lon"], lat0)
    center = (sum(d["_xy"][0] for d in with_c) / len(with_c), sum(d["_xy"][1] for d in with_c) / len(with_c))
    k = max(3, math.ceil(len(with_c) / TARGET_GROUP_SIZE))
    assign = _kmeans([d["_xy"] for d in with_c], k)
    def centroid(mem):
        return (sum(d["_xy"][0] for d in mem) / len(mem), sum(d["_xy"][1] for d in mem) / len(mem))

    parts = [[with_c[i] for i in range(len(with_c)) if assign[i] == c] for c in range(k)]
    parts = [m for m in parts if m]
    # توازن: نقسم أي مجموعة كبيرة (وسط المدينة غالبًا مزدحم)، وندمج الصغيرة جدًا بأقرب مجموعة
    changed = True
    while changed:
        changed = False
        for m in list(parts):
            if len(m) > MAX_GROUP_SIZE:
                a = _kmeans([d["_xy"] for d in m], 2)
                halves = [[m[i] for i in range(len(m)) if a[i] == h] for h in (0, 1)]
                if all(halves):
                    parts.remove(m)
                    parts.extend(halves)
                    changed = True
    for m in sorted([m for m in parts if len(m) < MIN_GROUP_SIZE], key=len):
        if len(parts) <= 2 or m not in parts:
            continue
        c = centroid(m)
        others = [o for o in parts if o is not m]
        target = min(others, key=lambda o: _d2(centroid(o), c))
        target.extend(m)
        parts.remove(m)
    groups = [{"members": m, "c": centroid(m)} for m in parts]
    # «وسط» = قريب من مركز المدينة مقارنة بنص قطر الأحياء المعتاد (الوسيط — ما يتأثر بالضواحي البعيدة)
    dists = sorted(math.sqrt(_d2(d["_xy"], center)) for d in with_c)
    r_med = dists[len(dists) // 2] or 1
    for g in groups:
        dx, dy = g["c"][0] - center[0], g["c"][1] - center[1]
        dist = math.sqrt(dx * dx + dy * dy)
        ang = (math.degrees(math.atan2(dx, dy)) + 360) % 360       # 0 = شمال، باتجاه عقارب الساعة
        g["dir"] = "وسط" if dist < 0.45 * r_med else _DIRS[int(((ang + 22.5) % 360) // 45)]
        g["ang"] = -1 if g["dir"] == "وسط" else ang
        mid = min(g["members"], key=lambda d: _d2(d["_xy"], g["c"]))
        g["landmark"] = _short(mid["name"])
        g["members"] = _chain(g["members"], center if g["dir"] == "وسط" else
                              min((d["_xy"] for d in g["members"]), key=lambda p: _d2(p, center)))
    groups.sort(key=lambda g: g["ang"])
    if no_c:
        groups.append({"members": no_c, "dir": None, "landmark": None, "c": None, "ang": 999})
    return {"groups": groups, "lat0": lat0}


def city_groups(city_id: int) -> dict | None:
    if city_id not in _cache:
        _cache[city_id] = _build(city_id)
    return _cache[city_id]


def ordered_groups(city_id: int, city_name: str, near: tuple | None = None) -> list[tuple[str | None, list[dict]]]:
    """[(عنوان المجموعة, [أحياء])]. near=(lat, lon): مجموعة الفني أول، وداخلها الأقرب له أول.
    يرجع [(None, كل الأحياء)] للمدن الصغيرة (بدون مجموعات)."""
    g = city_groups(city_id)
    if not g:
        return [(None, db.list_sa_districts_by_city(city_id))]
    groups = [dict(x) for x in g["groups"]]
    if near and near[0] is not None:
        p = _xy(near[0], near[1], g["lat0"])
        geo = [x for x in groups if x["c"] is not None]
        geo.sort(key=lambda x: min(_d2(d["_xy"], p) for d in x["members"]))
        first = geo[0]
        first["members"] = _chain(first["members"], p)
        groups = geo + [x for x in groups if x["c"] is None]
    used: dict = {}
    out = []
    for x in groups:
        if x["dir"] is None:
            title = "📍 أحياء أخرى"
        else:
            base = f"وسط {city_name}" if x["dir"] == "وسط" else f"{x['dir']} {city_name}"
            used[base] = used.get(base, 0) + 1
            title = f"🧭 {base} — حول {x['landmark']}"
        out.append((title, x["members"]))
    return out
