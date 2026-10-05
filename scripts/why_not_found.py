# تشخيص: «ليش الفني الفلاني ما طلع بالبحث؟»
#
# التشغيل على السيرفر:
#   cd /root/fani-bot && venv/bin/python scripts/why_not_found.py عبدالمحسن
#
# يطبع لكل فني اسمه فيه الكلمة: حالته، مهنته، مدينته وأحياؤه، فرصه المجانية، وهل يطلع
# ببحث المدينة وبحث كل حي من أحيائه — مع السبب لو ما يطلع. وآخر عمليات بحث عن مهنته.
# ما يغيّر أي شي بقاعدة البيانات (قراءة فقط) وما يطبع أرقام الجوالات.

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import db  # noqa: E402


def main():
    if len(sys.argv) < 2:
        print("اكتب جزء من اسم الفني، مثال: venv/bin/python scripts/why_not_found.py عبدالمحسن")
        return
    q = " ".join(sys.argv[1:]).strip()
    free_limit = int(db.get_setting("free_contacts_limit", str(db.FREE_CONTACTS_LIMIT)))
    with db.get_conn() as conn:
        rows = [dict(r) for r in conn.execute(
            "SELECT * FROM professionals WHERE full_name LIKE ? ORDER BY id DESC", (f"%{q}%",)
        ).fetchall()]
    if not rows:
        print(f"❌ ما فيه أي فني اسمه فيه «{q}» — يمكن ما كمّل التسجيل، أو مسجّل باسم ثاني.")
        return

    for p in rows:
        print("=" * 50)
        print(f"👷 {p['full_name']}  (رقم {p['id']})  — سجّل من: {'واتساب' if p.get('wa_id') else 'تلغرام'}")
        print(f"🛠️ المهنة: {p['profession_name']} [{p['profession_id']}]"
              + (f" + {p.get('profession2_name')} [{p.get('profession2_id')}]" if p.get("profession2_id") else ""))
        print(f"📍 {p.get('country')} / {p['city']} (city_id={p.get('city_id')})"
              f" — {'المدينة كاملة 🌍' if p.get('covers_whole_city') else 'أحياء: ' + str(p.get('neighborhood'))}")
        reasons = []
        if p["status"] != db.STATUS_ACTIVE:
            label = {"pending": "قيد المراجعة (ما وافقت عليه من اللوحة)", "rejected": "مرفوض"}.get(p["status"], p["status"])
            reasons.append(f"الحالة: {label} — ما يطلع إلا لما يكون «نشط»")
        used, bonus = p.get("free_contacts_used") or 0, p.get("bonus_contacts") or 0
        if not p.get("is_subscribed") and used >= free_limit + bonus:
            reasons.append(f"خلّص فرصه المجانية ({used} من {free_limit + bonus}) وما هو مشترك — يختفي من البحث")
        print(f"🎟️ الفرص: استخدم {used} من {free_limit + bonus} | مشترك: {'نعم' if p.get('is_subscribed') else 'لا'}"
              f" | الحالة: {p['status']}")

        with db.get_conn() as conn:
            dists = [dict(r) for r in conn.execute(
                "SELECT d.id, d.name FROM professional_districts pd JOIN sa_districts d ON d.id = pd.district_id "
                "WHERE pd.professional_id = ?", (p["id"],)
            ).fetchall()]
        if dists:
            print("🏘️ أحياؤه بالنظام:", "، ".join(d["name"] for d in dists))

        for pid in [x for x in (p["profession_id"], p.get("profession2_id")) if x]:
            city_ids = db.search_active_professional_ids(pid, p["city"], None, None, None, p.get("city_id"))
            print(f"🔎 بحث «{pid}» بمدينة {p['city']} (بدون حي): {'✅ يطلع' if p['id'] in city_ids else '❌ ما يطلع'}"
                  f" — مجموع النتائج {len(city_ids)}")
            for d in dists:
                ids = db.search_active_professional_ids(pid, p["city"], d["name"], d["id"], None, p.get("city_id"))
                print(f"   {d['name']}: {'✅' if p['id'] in ids else '❌'}")

        if reasons:
            print("⚠️ السبب:")
            for r in reasons:
                print("   •", r)
        else:
            print("✅ حالته سليمة. لو ما طلع لك: غالبًا بحثت من حي مو من أحيائه (شوف آخر عمليات البحث تحت).")

        with db.get_conn() as conn:
            logs = [dict(r) for r in conn.execute(
                "SELECT searched_at, city, neighborhood, results_count FROM search_log "
                "WHERE profession_id IN (?, ?) ORDER BY id DESC LIMIT 5",
                (p["profession_id"], p.get("profession2_id") or ""),
            ).fetchall()]
        if logs:
            print("🕘 آخر عمليات بحث عن نفس المهنة:")
            for l in logs:
                print(f"   {l['searched_at'][:16]} | {l['city']} | حي: {l['neighborhood'] or 'كل المدينة'} | نتائج: {l['results_count']}")


if __name__ == "__main__":
    main()
