# طبقة قاعدة البيانات — SQLite بسيطة، ملف واحد، بدون أي إعداد خارجي.
# كل الدوال هنا متزامنة (sync) عمدًا؛ نناديها من الهاندلرز غير المتزامنة عبر asyncio.to_thread.

import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone

from config import DB_PATH

STATUS_PENDING = "pending"
STATUS_ACTIVE = "active"
STATUS_REJECTED = "rejected"

STATUS_LABELS_AR = {
    STATUS_PENDING: "قيد المراجعة",
    STATUS_ACTIVE: "نشط",
    STATUS_REJECTED: "مرفوض",
}

# عدد الفرص (ضغطات تواصل واتساب) المجانية لكل فني قبل ما يحتاج اشتراك.
# لاحقًا (خطوة الاشتراك) نتحقق: إذا free_contacts_used >= هذا الرقم ولا يوجد اشتراك فعّال → يُستبعد من نتائج البحث.
FREE_CONTACTS_LIMIT = 3

RESULTS_PAGE_SIZE = 5


@contextmanager
def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db():
    with get_conn() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS professionals (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                telegram_user_id INTEGER NOT NULL,
                full_name TEXT NOT NULL,
                city TEXT NOT NULL,
                neighborhood TEXT,
                whatsapp_number TEXT NOT NULL,
                telegram_contact_number TEXT,
                domain_name TEXT NOT NULL,
                profession_id TEXT NOT NULL,
                profession_name TEXT NOT NULL,
                services_json TEXT NOT NULL DEFAULT '[]',
                status TEXT NOT NULL DEFAULT 'pending',
                created_at TEXT NOT NULL,
                reviewed_at TEXT,

                -- التناوب العادل: عدد مرات الظهور الفعلي بنتائج بحث (المعيار الأساسي للترتيب)
                -- last_shown_at للعرض/التتبع فقط، مو للترتيب — استخدامه بالترتيب سبب تحيّز
                -- ثابت لصالح IDs الأصغر عند تساوي التوقيت بنفس دفعة العرض (تم اكتشافه وإصلاحه بالاختبار)
                times_shown INTEGER NOT NULL DEFAULT 0,
                last_shown_at TEXT,

                -- الفرص المجانية والاشتراك (الدفع لاحقًا؛ الأعمدة جاهزة من الآن)
                free_contacts_used INTEGER NOT NULL DEFAULT 0,
                is_subscribed INTEGER NOT NULL DEFAULT 0,
                subscription_expires_at TEXT
            )
            """
        )

        # ترحيل: بعض الفنيين رقمهم للاتصال فقط بدون واتساب مفعّل عليه. عمود جديد
        # على جدول قديم — نضيفه فقط لو ناقص (قاعدة بيانات منشورة مسبقًا)، بقيمة
        # افتراضية True حفاظًا على سلوك كل التسجيلات السابقة (كانت تفترض واتساب دائمًا).
        existing_columns = {row["name"] for row in conn.execute("PRAGMA table_info(professionals)").fetchall()}
        if "has_whatsapp" not in existing_columns:
            conn.execute(
                "ALTER TABLE professionals ADD COLUMN has_whatsapp INTEGER NOT NULL DEFAULT 1"
            )

        # فهرس يسرّع بحث العميل: مهنة + مدينة + حي على الفنيين النشطين، مرتّب بالتناوب
        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_search
            ON professionals (status, profession_id, city, neighborhood, times_shown)
            """
        )

        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS contact_clicks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                professional_id INTEGER NOT NULL,
                customer_telegram_id INTEGER NOT NULL,
                clicked_at TEXT NOT NULL,
                FOREIGN KEY (professional_id) REFERENCES professionals (id)
            )
            """
        )

        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS subscription_payments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                professional_id INTEGER NOT NULL,
                method TEXT NOT NULL,           -- 'tap' أو 'stars'
                external_id TEXT,                -- charge id (Tap) أو telegram_payment_charge_id (Stars)
                amount TEXT NOT NULL,            -- نص عشان يشيل ريال أو نجوم بدون لبس
                status TEXT NOT NULL DEFAULT 'pending',  -- pending / paid
                created_at TEXT NOT NULL,
                paid_at TEXT,
                FOREIGN KEY (professional_id) REFERENCES professionals (id)
            )
            """
        )

        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS search_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                customer_telegram_id INTEGER NOT NULL,
                profession_id TEXT NOT NULL,
                profession_name TEXT NOT NULL,
                city TEXT NOT NULL,
                neighborhood TEXT,
                results_count INTEGER NOT NULL,
                searched_at TEXT NOT NULL
            )
            """
        )

        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            )
            """
        )

        # ─────────────────────────── بيانات المهن (قابلة للتعديل من اللوحة) ───────────────────────────
        # هاجرناها من ملف professions.json الثابت لقاعدة البيانات، عشان تعديل/إضافة/حذف
        # مهنة من لوحة التحكم يشتغل فورًا على البوت بدون أي إعادة تشغيل أو تعديل كود.
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS domains (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                sort_order INTEGER NOT NULL
            )
            """
        )

        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS professions (
                id TEXT PRIMARY KEY,
                domain_id TEXT NOT NULL,
                name TEXT NOT NULL,
                isco_code TEXT,
                status TEXT,
                services_json TEXT NOT NULL DEFAULT '[]',
                sort_order INTEGER NOT NULL,
                FOREIGN KEY (domain_id) REFERENCES domains (id)
            )
            """
        )

        # ─────────────────────────── مناطق/مدن/أحياء المملكة (بيانات رسمية جاهزة) ───────────────────────────
        # عشان نستبدل كتابة المدينة/الحي كنص حر (يسبب أخطاء إملاء وتشتت) باختيار من قائمة
        # رسمية حقيقية، ونحل مشكلة "300 سباك بجدة" بعرض أحياء فعلية للفلترة بدل نص حر.
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS sa_regions (
                id INTEGER PRIMARY KEY,
                name TEXT NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS sa_cities (
                id INTEGER PRIMARY KEY,
                region_id INTEGER NOT NULL,
                name TEXT NOT NULL,
                has_districts INTEGER NOT NULL DEFAULT 0,
                lat REAL,
                lon REAL,
                FOREIGN KEY (region_id) REFERENCES sa_regions (id)
            )
            """
        )
        conn.execute("CREATE INDEX IF NOT EXISTS idx_sa_cities_region ON sa_cities (region_id)")
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS sa_districts (
                id INTEGER PRIMARY KEY,
                city_id INTEGER NOT NULL,
                name TEXT NOT NULL,
                lat REAL,
                lon REAL,
                FOREIGN KEY (city_id) REFERENCES sa_cities (id)
            )
            """
        )
        conn.execute("CREATE INDEX IF NOT EXISTS idx_sa_districts_city ON sa_districts (city_id)")

        # ربط الفني بأحيائه (من حي واحد إلى خمسة أحياء كحد أقصى — قرار نهائي) بدل عمود
        # neighborhood النصي الوحيد. عمود professionals.neighborhood ما زال موجود للعرض
        # (نص مجمّع لأسماء الأحياء المختارة) وللتوافق مع أي بحث نصي قديم.
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS professional_districts (
                professional_id INTEGER NOT NULL,
                district_id INTEGER NOT NULL,
                PRIMARY KEY (professional_id, district_id),
                FOREIGN KEY (professional_id) REFERENCES professionals (id),
                FOREIGN KEY (district_id) REFERENCES sa_districts (id)
            )
            """
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_prof_districts_district ON professional_districts (district_id)"
        )


def _now_iso():
    return datetime.now(timezone.utc).isoformat()


def get_professional_by_telegram_id(telegram_user_id: int):
    with get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM professionals WHERE telegram_user_id = ? "
            "ORDER BY id DESC LIMIT 1",
            (telegram_user_id,),
        ).fetchone()
        return dict(row) if row else None


def create_registration(data: dict) -> int:
    """يحفظ تسجيل فني جديد بحالة قيد المراجعة، ويرجّع الـ id."""
    with get_conn() as conn:
        cur = conn.execute(
            """
            INSERT INTO professionals (
                telegram_user_id, full_name, city, neighborhood,
                whatsapp_number, has_whatsapp, telegram_contact_number,
                domain_name, profession_id, profession_name,
                services_json, status, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                data["telegram_user_id"],
                data["full_name"],
                data["city"],
                data.get("neighborhood"),
                data["whatsapp_number"],
                1 if data.get("has_whatsapp", True) else 0,
                data.get("telegram_contact_number"),
                data["domain_name"],
                data["profession_id"],
                data["profession_name"],
                json.dumps(data.get("services", []), ensure_ascii=False),
                STATUS_PENDING,
                _now_iso(),
            ),
        )
        professional_id = cur.lastrowid
        district_ids = data.get("district_ids") or []
        if district_ids:
            conn.executemany(
                "INSERT INTO professional_districts (professional_id, district_id) VALUES (?, ?)",
                [(professional_id, did) for did in district_ids],
            )
        return professional_id


def get_districts_for_professional(professional_id: int):
    with get_conn() as conn:
        rows = conn.execute(
            """
            SELECT sa_districts.* FROM professional_districts
            JOIN sa_districts ON sa_districts.id = professional_districts.district_id
            WHERE professional_districts.professional_id = ?
            ORDER BY sa_districts.name
            """,
            (professional_id,),
        ).fetchall()
        return [dict(r) for r in rows]


def get_professional_by_id(row_id: int):
    with get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM professionals WHERE id = ?", (row_id,)
        ).fetchone()
        return dict(row) if row else None


def set_status(row_id: int, status: str):
    with get_conn() as conn:
        conn.execute(
            "UPDATE professionals SET status = ?, reviewed_at = ? WHERE id = ?",
            (status, _now_iso(), row_id),
        )


def search_active_professional_ids(
    profession_id: str, city: str, neighborhood: str | None, district_id: int | None = None
):
    """
    بحث العميل: مهنة (تطابق تام) + مدينة (تطابق تقريبي) + حي (اختياري، تطابق تقريبي).
    الترتيب: تناوب عادل — الأقل ظهورًا (times_shown الأصغر) يظهر أولاً، وعند التساوي
    نستخدم ترتيب عشوائي (RANDOM()) بدل id، لتفادي تحيّز ثابت لصالح IDs الأصغر
    (هذا بالضبط الخطأ اللي صار وانضبط بالاختبار: last_shown_at ASC + id ASC كتعادل
    كانت تخلي نفس 3 فنيين يظهروا بكل عملية بحث لأنهم يتحدّثوا لنفس التوقيت كدفعة وحدة).
    فني تجاوز فرصه المجانية (FREE_CONTACTS_LIMIT) ولا يوجد له اشتراك فعّال يُستبعد من النتائج.

    يرجّع قائمة IDs مرتّبة بالكامل (بدون LIMIT/OFFSET) — نجلبها مرة واحدة فقط في بداية
    كل جلسة بحث، ونقسّمها بالذاكرة على صفحات. هذا مهم: لو استخدمنا OFFSET مع استعلام
    منفصل لكل صفحة، فإن أول استدعاء لـ mark_shown (بعد عرض الصفحة الأولى) يغيّر ترتيب
    last_shown_at قبل ما نجيب الصفحة الثانية، فتتكرر/تُفقد نتائج بين الصفحات.
    """
    free_limit = int(get_setting("free_contacts_limit", str(FREE_CONTACTS_LIMIT)))
    with get_conn() as conn:
        where = [
            "status = ?",
            "profession_id = ?",
            "city LIKE ?",
            "(free_contacts_used < ? OR is_subscribed = 1)",
        ]
        params = [STATUS_ACTIVE, profession_id, f"%{city.strip()}%", free_limit]

        if district_id:
            # المطابقة الدقيقة: الفني عنده هذا الحي ضمن أحيائه المسجّلة (1 إلى 5 أحياء).
            # + توافق مع فنيين قدامى قبل ميزة تعدد الأحياء (ما عندهم صفوف بجدول الربط
            # إطلاقًا) عبر مطابقة نصية على عمود neighborhood القديم كحل احتياطي لهم فقط.
            where.append(
                "(id IN (SELECT professional_id FROM professional_districts WHERE district_id = ?) "
                "OR (id NOT IN (SELECT professional_id FROM professional_districts) AND neighborhood LIKE ?))"
            )
            params.append(district_id)
            params.append(f"%{(neighborhood or '').strip()}%")
        elif neighborhood:
            # توافق مع بيانات/بحث قديم بالنص الحر (بدون district_id محدد)
            where.append("neighborhood LIKE ?")
            params.append(f"%{neighborhood.strip()}%")

        where_sql = " AND ".join(where)

        rows = conn.execute(
            f"""
            SELECT id FROM professionals
            WHERE {where_sql}
            ORDER BY times_shown ASC, RANDOM()
            """,
            params,
        ).fetchall()

        return [r["id"] for r in rows]


def get_professionals_by_ids(ids: list[int]):
    """يجيب صفوف كاملة لقائمة IDs، مع المحافظة على نفس ترتيب القائمة المُمررة."""
    if not ids:
        return []
    with get_conn() as conn:
        placeholders = ",".join("?" for _ in ids)
        rows = conn.execute(
            f"SELECT * FROM professionals WHERE id IN ({placeholders})", ids
        ).fetchall()
        by_id = {r["id"]: dict(r) for r in rows}
        return [by_id[i] for i in ids if i in by_id]


def mark_shown(professional_ids: list[int]):
    """يزيد عدّاد times_shown ويحدّث last_shown_at لكل فني ظهرت بطاقته فعليًا للعميل —
    times_shown هو أساس عدالة التناوب؛ last_shown_at للعرض/التتبع فقط."""
    if not professional_ids:
        return
    with get_conn() as conn:
        now = _now_iso()
        conn.executemany(
            "UPDATE professionals SET times_shown = times_shown + 1, last_shown_at = ? WHERE id = ?",
            [(now, pid) for pid in professional_ids],
        )


def log_contact_click(professional_id: int, customer_telegram_id: int) -> int:
    """يسجّل ضغطة 'تواصل واتساب' ويزيد عداد الفرص المجانية المستخدمة، ويرجّع العدد الجديد."""
    with get_conn() as conn:
        conn.execute(
            """
            INSERT INTO contact_clicks (professional_id, customer_telegram_id, clicked_at)
            VALUES (?, ?, ?)
            """,
            (professional_id, customer_telegram_id, _now_iso()),
        )
        conn.execute(
            "UPDATE professionals SET free_contacts_used = free_contacts_used + 1 WHERE id = ?",
            (professional_id,),
        )
        new_count = conn.execute(
            "SELECT free_contacts_used FROM professionals WHERE id = ?", (professional_id,)
        ).fetchone()[0]
        return new_count


# ─────────────────────────── الاشتراك والدفع (Tap + Stars) ───────────────────────────

def activate_subscription(professional_id: int, days: int):
    """يفعّل اشتراك الفني (is_subscribed=1) ويمدّد تاريخ الانتهاء من اليوم + عدد الأيام."""
    from datetime import timedelta
    expires = (datetime.now(timezone.utc) + timedelta(days=days)).isoformat()
    with get_conn() as conn:
        conn.execute(
            "UPDATE professionals SET is_subscribed = 1, subscription_expires_at = ? WHERE id = ?",
            (expires, professional_id),
        )


def create_pending_payment(professional_id: int, method: str, external_id: str | None, amount: str) -> int:
    """يسجّل محاولة دفع (Tap أو Stars) بحالة 'pending'، ويرجّع الـ id."""
    with get_conn() as conn:
        cur = conn.execute(
            """
            INSERT INTO subscription_payments
                (professional_id, method, external_id, amount, status, created_at)
            VALUES (?, ?, ?, ?, 'pending', ?)
            """,
            (professional_id, method, external_id, amount, _now_iso()),
        )
        return cur.lastrowid


def get_payment_by_external_id(method: str, external_id: str):
    with get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM subscription_payments WHERE method = ? AND external_id = ? "
            "ORDER BY id DESC LIMIT 1",
            (method, external_id),
        ).fetchone()
        return dict(row) if row else None


def mark_payment_paid(payment_id: int):
    with get_conn() as conn:
        conn.execute(
            "UPDATE subscription_payments SET status = 'paid', paid_at = ? WHERE id = ?",
            (_now_iso(), payment_id),
        )


def update_payment_external_id(payment_id: int, external_id: str):
    """نحدّث external_id بعد ما نستلم رد Tap اللي فيه charge id (نسويها create ثم update)."""
    with get_conn() as conn:
        conn.execute(
            "UPDATE subscription_payments SET external_id = ? WHERE id = ?",
            (external_id, payment_id),
        )


# ─────────────────────────── الإعدادات القابلة للتعديل ───────────────────────────
# قيم افتراضية تُستخدم أول مرة (لو ما فيه شي بجدول settings بعد)، مأخوذة من config.py
# كخطوة انتقالية سلسة، لكن بعد أول تعديل من اللوحة، القيمة بقاعدة البيانات هي الفيصل.

def get_setting(key: str, default: str) -> str:
    with get_conn() as conn:
        row = conn.execute("SELECT value FROM settings WHERE key = ?", (key,)).fetchone()
        return row["value"] if row else default


def set_setting(key: str, value: str):
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO settings (key, value) VALUES (?, ?) "
            "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
            (key, str(value)),
        )


# ─────────────────────────── سجل البحث ───────────────────────────

def log_search(customer_telegram_id: int, profession_id: str, profession_name: str,
                city: str, neighborhood: str | None, results_count: int):
    with get_conn() as conn:
        conn.execute(
            """
            INSERT INTO search_log
                (customer_telegram_id, profession_id, profession_name, city,
                 neighborhood, results_count, searched_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (customer_telegram_id, profession_id, profession_name, city,
             neighborhood, results_count, _now_iso()),
        )


# ─────────────────────────── بذر بيانات المهن (مرة واحدة فقط) ───────────────────────────

def seed_professions_from_json_if_empty(json_path):
    """لو جدول domains فاضي (أول تشغيل)، نعبّيه من data/professions.json.
    بعد هذي المرة، قاعدة البيانات هي المصدر الوحيد — تعديل الملف لاحقًا ما له أي تأثير."""
    import json as _json

    with get_conn() as conn:
        count = conn.execute("SELECT COUNT(*) FROM domains").fetchone()[0]
        if count > 0:
            return False  # مو أول مرة، ما نعيد البذر

        with open(json_path, encoding="utf-8") as f:
            data = _json.load(f)

        for d_order, domain in enumerate(data["domains"]):
            conn.execute(
                "INSERT INTO domains (id, name, sort_order) VALUES (?, ?, ?)",
                (domain["id"], domain["name"], d_order),
            )
            for p_order, prof in enumerate(domain["professions"]):
                conn.execute(
                    """
                    INSERT INTO professions
                        (id, domain_id, name, isco_code, status, services_json, sort_order)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        prof["id"], domain["id"], prof["name"], prof.get("isco_code"),
                        prof.get("status"), _json.dumps(prof.get("services", []), ensure_ascii=False),
                        p_order,
                    ),
                )
        return True


# ─────────────────────────── إدارة المهن (CRUD للوحة التحكم) ───────────────────────────

def list_domains():
    with get_conn() as conn:
        rows = conn.execute("SELECT * FROM domains ORDER BY sort_order").fetchall()
        return [dict(r) for r in rows]


def list_professions_by_domain(domain_id: str):
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM professions WHERE domain_id = ? ORDER BY sort_order", (domain_id,)
        ).fetchall()
        return [dict(r) for r in rows]


def get_domain_by_id(domain_id: str):
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM domains WHERE id = ?", (domain_id,)).fetchone()
        return dict(row) if row else None


def get_profession_by_id(profession_id: str):
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM professions WHERE id = ?", (profession_id,)).fetchone()
        return dict(row) if row else None


def create_domain(name: str) -> str:
    with get_conn() as conn:
        max_order = conn.execute("SELECT COALESCE(MAX(sort_order), -1) FROM domains").fetchone()[0]
        max_id_num = conn.execute(
            "SELECT COUNT(*) FROM domains"
        ).fetchone()[0]
        new_id = f"d_new_{max_id_num + 1}_{int(datetime.now(timezone.utc).timestamp())}"
        conn.execute(
            "INSERT INTO domains (id, name, sort_order) VALUES (?, ?, ?)",
            (new_id, name, max_order + 1),
        )
        return new_id


def rename_domain(domain_id: str, new_name: str):
    with get_conn() as conn:
        conn.execute("UPDATE domains SET name = ? WHERE id = ?", (new_name, domain_id))


def delete_domain(domain_id: str) -> bool:
    """يحذف المجال فقط لو ما فيه مهن جواه (حماية من حذف خاطئ يكسر تسجيلات فنيين حاليين)."""
    with get_conn() as conn:
        count = conn.execute(
            "SELECT COUNT(*) FROM professions WHERE domain_id = ?", (domain_id,)
        ).fetchone()[0]
        if count > 0:
            return False
        conn.execute("DELETE FROM domains WHERE id = ?", (domain_id,))
        return True


def create_profession(domain_id: str, name: str, isco_code: str | None, services: list[str]) -> str:
    with get_conn() as conn:
        max_order = conn.execute(
            "SELECT COALESCE(MAX(sort_order), -1) FROM professions WHERE domain_id = ?", (domain_id,)
        ).fetchone()[0]
        total_count = conn.execute("SELECT COUNT(*) FROM professions").fetchone()[0]
        new_id = f"p_new_{total_count + 1}_{int(datetime.now(timezone.utc).timestamp())}"
        conn.execute(
            """
            INSERT INTO professions (id, domain_id, name, isco_code, status, services_json, sort_order)
            VALUES (?, ?, ?, ?, 'مضافة يدويًا', ?, ?)
            """,
            (new_id, domain_id, name, isco_code, json.dumps(services, ensure_ascii=False), max_order + 1),
        )
        return new_id


def update_profession(profession_id: str, name: str, isco_code: str | None, services: list[str]):
    with get_conn() as conn:
        conn.execute(
            "UPDATE professions SET name = ?, isco_code = ?, services_json = ? WHERE id = ?",
            (name, isco_code, json.dumps(services, ensure_ascii=False), profession_id),
        )


def delete_profession(profession_id: str) -> bool:
    """يحذف المهنة فقط لو ما فيه فنيين مسجّلين عليها حاليًا (حماية من كسر بيانات موجودة)."""
    with get_conn() as conn:
        count = conn.execute(
            "SELECT COUNT(*) FROM professionals WHERE profession_id = ?", (profession_id,)
        ).fetchone()[0]
        if count > 0:
            return False
        conn.execute("DELETE FROM professions WHERE id = ?", (profession_id,))
        return True


# ─────────────────────────── دوال إدارية للوحة التحكم (الأدمن) ───────────────────────────

def admin_list_professionals(
    status: str | None = None,
    city: str | None = None,
    profession_id: str | None = None,
    subscribed: bool | None = None,
    query: str | None = None,
    limit: int = 50,
    offset: int = 0,
):
    """يرجّع قائمة فنيين مع فلاتر اختيارية، الأحدث أولًا. تُستخدم بصفحة إدارة الفنيين باللوحة."""
    where = []
    params: list = []

    if status:
        where.append("status = ?")
        params.append(status)
    if city:
        where.append("city LIKE ?")
        params.append(f"%{city.strip()}%")
    if profession_id:
        where.append("profession_id = ?")
        params.append(profession_id)
    if subscribed is not None:
        where.append("is_subscribed = ?")
        params.append(1 if subscribed else 0)
    if query:
        where.append("(full_name LIKE ? OR whatsapp_number LIKE ? OR telegram_contact_number LIKE ?)")
        like = f"%{query.strip()}%"
        params.extend([like, like, like])

    where_sql = f"WHERE {' AND '.join(where)}" if where else ""

    with get_conn() as conn:
        rows = conn.execute(
            f"""
            SELECT * FROM professionals
            {where_sql}
            ORDER BY created_at DESC
            LIMIT ? OFFSET ?
            """,
            [*params, limit, offset],
        ).fetchall()
        return [dict(r) for r in rows]


def admin_count_professionals(
    status: str | None = None,
    city: str | None = None,
    profession_id: str | None = None,
    subscribed: bool | None = None,
    query: str | None = None,
) -> int:
    """نفس فلاتر admin_list_professionals، لكن يرجّع العدد الكلي (لأجل ترقيم الصفحات)."""
    where = []
    params: list = []

    if status:
        where.append("status = ?")
        params.append(status)
    if city:
        where.append("city LIKE ?")
        params.append(f"%{city.strip()}%")
    if profession_id:
        where.append("profession_id = ?")
        params.append(profession_id)
    if subscribed is not None:
        where.append("is_subscribed = ?")
        params.append(1 if subscribed else 0)
    if query:
        where.append("(full_name LIKE ? OR whatsapp_number LIKE ? OR telegram_contact_number LIKE ?)")
        like = f"%{query.strip()}%"
        params.extend([like, like, like])

    where_sql = f"WHERE {' AND '.join(where)}" if where else ""

    with get_conn() as conn:
        return conn.execute(
            f"SELECT COUNT(*) FROM professionals {where_sql}", params
        ).fetchone()[0]


def admin_list_cities() -> list[str]:
    """مدن مميزة موجودة فعليًا بجدول الفنيين — تُستخدم كخيارات فلترة جاهزة باللوحة."""
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT DISTINCT city FROM professionals ORDER BY city"
        ).fetchall()
        return [r["city"] for r in rows]


def admin_update_professional(
    professional_id: int,
    full_name: str | None = None,
    city: str | None = None,
    neighborhood: str | None = None,
    whatsapp_number: str | None = None,
    telegram_contact_number: str | None = None,
    has_whatsapp: bool | None = None,
):
    """تعديل يدوي لبيانات تواصل/مكان فني من اللوحة. أي حقل None يُترك بدون تغيير."""
    fields = {
        "full_name": full_name,
        "city": city,
        "neighborhood": neighborhood,
        "whatsapp_number": whatsapp_number,
        "telegram_contact_number": telegram_contact_number,
        "has_whatsapp": None if has_whatsapp is None else (1 if has_whatsapp else 0),
    }
    updates = {k: v for k, v in fields.items() if v is not None}
    if not updates:
        return False

    set_sql = ", ".join(f"{k} = ?" for k in updates)
    params = [*updates.values(), professional_id]
    with get_conn() as conn:
        conn.execute(f"UPDATE professionals SET {set_sql} WHERE id = ?", params)
    return True


def admin_set_subscription(professional_id: int, is_subscribed: bool, expires_at: str | None = None):
    """تفعيل/إلغاء اشتراك يدويًا من اللوحة (مثلًا هدية اشتراك، أو إلغاء بسبب نزاع/استرجاع)،
    بدون المرور بمسار دفع فعلي. expires_at بصيغة ISO، أو None لإلغاء تاريخ الانتهاء."""
    with get_conn() as conn:
        conn.execute(
            "UPDATE professionals SET is_subscribed = ?, subscription_expires_at = ? WHERE id = ?",
            (1 if is_subscribed else 0, expires_at, professional_id),
        )


def admin_reset_free_contacts(professional_id: int):
    """يصفّر عدّاد الفرص المجانية المستهلكة لفني معيّن (استثناء يدوي من الأدمن)."""
    with get_conn() as conn:
        conn.execute(
            "UPDATE professionals SET free_contacts_used = 0 WHERE id = ?",
            (professional_id,),
        )


def admin_delete_professional(professional_id: int):
    """حذف نهائي لسجل فني (مع سجلات التواصل والدفعات المرتبطة به) — إجراء لا رجعة فيه."""
    with get_conn() as conn:
        conn.execute("DELETE FROM contact_clicks WHERE professional_id = ?", (professional_id,))
        conn.execute("DELETE FROM subscription_payments WHERE professional_id = ?", (professional_id,))
        conn.execute("DELETE FROM professional_districts WHERE professional_id = ?", (professional_id,))
        conn.execute("DELETE FROM professionals WHERE id = ?", (professional_id,))


def has_any_user_data(telegram_user_id: int) -> bool:
    """يفحص هل عند هذا المستخدم أي بيانات مخزّنة (كفني و/أو كعميل باحث) — تُستخدم قبل عرض
    تأكيد حذف الحساب، حتى ما نعرض الخيار لمن ما عنده شي أصلًا."""
    with get_conn() as conn:
        prof = conn.execute(
            "SELECT 1 FROM professionals WHERE telegram_user_id = ? LIMIT 1", (telegram_user_id,)
        ).fetchone()
        if prof:
            return True
        search = conn.execute(
            "SELECT 1 FROM search_log WHERE customer_telegram_id = ? LIMIT 1", (telegram_user_id,)
        ).fetchone()
        if search:
            return True
        contact = conn.execute(
            "SELECT 1 FROM contact_clicks WHERE customer_telegram_id = ? LIMIT 1", (telegram_user_id,)
        ).fetchone()
        return bool(contact)


def delete_all_user_data(telegram_user_id: int):
    """حذف نهائي وشامل لكل بيانات هذا المستخدم من قاعدة البيانات (حق الحذف/الخصوصية):
    - كل سجلات تسجيله كفني (لو سجّل أكثر من مرة) + سجلات التواصل والدفعات المرتبطة بها.
    - كل سجلات بحثه وضغطاته على واتساب بصفته عميل (customer_telegram_id).
    إجراء لا رجعة فيه."""
    with get_conn() as conn:
        prof_ids = [
            r["id"] for r in conn.execute(
                "SELECT id FROM professionals WHERE telegram_user_id = ?", (telegram_user_id,)
            ).fetchall()
        ]
        for pid in prof_ids:
            conn.execute("DELETE FROM contact_clicks WHERE professional_id = ?", (pid,))
            conn.execute("DELETE FROM subscription_payments WHERE professional_id = ?", (pid,))
            conn.execute("DELETE FROM professional_districts WHERE professional_id = ?", (pid,))
        conn.execute("DELETE FROM professionals WHERE telegram_user_id = ?", (telegram_user_id,))
        conn.execute("DELETE FROM search_log WHERE customer_telegram_id = ?", (telegram_user_id,))
        conn.execute("DELETE FROM contact_clicks WHERE customer_telegram_id = ?", (telegram_user_id,))


def admin_list_payments(
    status: str | None = None,
    method: str | None = None,
    limit: int = 50,
    offset: int = 0,
):
    """سجل الدفعات مع اسم الفني ومهنته، الأحدث أولًا — لصفحة الاشتراكات والمدفوعات."""
    where = []
    params: list = []
    if status:
        where.append("sp.status = ?")
        params.append(status)
    if method:
        where.append("sp.method = ?")
        params.append(method)
    where_sql = f"WHERE {' AND '.join(where)}" if where else ""

    with get_conn() as conn:
        rows = conn.execute(
            f"""
            SELECT sp.*, p.full_name, p.profession_name, p.whatsapp_number
            FROM subscription_payments sp
            JOIN professionals p ON p.id = sp.professional_id
            {where_sql}
            ORDER BY sp.created_at DESC
            LIMIT ? OFFSET ?
            """,
            [*params, limit, offset],
        ).fetchall()
        return [dict(r) for r in rows]


def admin_count_payments(status: str | None = None, method: str | None = None) -> int:
    where = []
    params: list = []
    if status:
        where.append("status = ?")
        params.append(status)
    if method:
        where.append("method = ?")
        params.append(method)
    where_sql = f"WHERE {' AND '.join(where)}" if where else ""
    with get_conn() as conn:
        return conn.execute(
            f"SELECT COUNT(*) FROM subscription_payments {where_sql}", params
        ).fetchone()[0]


def _parse_amount_sar(amount_text: str) -> float:
    """يستخرج القيمة الرقمية من نص المبلغ (مثل '30.00 SAR') — يرجّع 0.0 لو ما كان بالريال."""
    if "SAR" not in amount_text.upper():
        return 0.0
    try:
        return float(amount_text.strip().split()[0])
    except (ValueError, IndexError):
        return 0.0


def get_admin_stats() -> dict:
    """إحصائيات عامة للوحة الرئيسية: أعداد الفنيين بكل حالة، التواصلات، الإيرادات،
    وأكثر المهن والمدن طلبًا."""
    with get_conn() as conn:
        status_counts = {
            row["status"]: row["c"]
            for row in conn.execute(
                "SELECT status, COUNT(*) AS c FROM professionals GROUP BY status"
            ).fetchall()
        }
        total_professionals = sum(status_counts.values())
        subscribed_count = conn.execute(
            "SELECT COUNT(*) FROM professionals WHERE is_subscribed = 1"
        ).fetchone()[0]
        total_contact_clicks = conn.execute(
            "SELECT COUNT(*) FROM contact_clicks"
        ).fetchone()[0]
        total_searches = conn.execute(
            "SELECT COUNT(*) FROM search_log"
        ).fetchone()[0]

        paid_payments = conn.execute(
            "SELECT method, amount FROM subscription_payments WHERE status = 'paid'"
        ).fetchall()
        revenue_sar = sum(_parse_amount_sar(r["amount"]) for r in paid_payments if r["method"] == "tap")
        stars_paid_count = sum(1 for r in paid_payments if r["method"] == "stars")

        top_professions = conn.execute(
            """
            SELECT profession_name, COUNT(*) AS c FROM search_log
            GROUP BY profession_name ORDER BY c DESC LIMIT 5
            """
        ).fetchall()
        top_cities = conn.execute(
            """
            SELECT city, COUNT(*) AS c FROM search_log
            GROUP BY city ORDER BY c DESC LIMIT 5
            """
        ).fetchall()

        return {
            "status_counts": status_counts,
            "total_professionals": total_professionals,
            "subscribed_count": subscribed_count,
            "total_contact_clicks": total_contact_clicks,
            "total_searches": total_searches,
            "revenue_sar": revenue_sar,
            "stars_paid_count": stars_paid_count,
            "top_professions": [dict(r) for r in top_professions],
            "top_cities": [dict(r) for r in top_cities],
        }


# ─────────────────────────── مناطق/مدن/أحياء المملكة (بيانات رسمية) ───────────────────────────

def seed_saudi_geo_if_empty(regions_path, cities_path, districts_path):
    """يبذر جداول sa_regions/sa_cities/sa_districts مرة واحدة من ملفات JSON رسمية
    (منطقة → مدينة → حي). لو الجدول فيه بيانات مسبقًا ما نعيد البذر."""
    import json as _json

    with get_conn() as conn:
        count = conn.execute("SELECT COUNT(*) FROM sa_regions").fetchone()[0]
        if count > 0:
            return False

        with open(regions_path, encoding="utf-8") as f:
            regions = _json.load(f)
        with open(cities_path, encoding="utf-8") as f:
            cities = _json.load(f)
        with open(districts_path, encoding="utf-8") as f:
            districts = _json.load(f)

        cities_with_districts = {d["city_id"] for d in districts}

        conn.executemany(
            "INSERT INTO sa_regions (id, name) VALUES (?, ?)",
            [(r["id"], r["name"]) for r in regions],
        )
        conn.executemany(
            "INSERT INTO sa_cities (id, region_id, name, has_districts, lat, lon) VALUES (?, ?, ?, ?, ?, ?)",
            [
                (
                    c["id"], c["region_id"], c["name"],
                    1 if c["id"] in cities_with_districts else 0,
                    c.get("lat"), c.get("lon"),
                )
                for c in cities
            ],
        )
        conn.executemany(
            "INSERT INTO sa_districts (id, city_id, name, lat, lon) VALUES (?, ?, ?, ?, ?)",
            [(d["id"], d["city_id"], d["name"], d.get("lat"), d.get("lon")) for d in districts],
        )
        return True


def list_sa_regions():
    with get_conn() as conn:
        rows = conn.execute("SELECT * FROM sa_regions ORDER BY name").fetchall()
        return [dict(r) for r in rows]


def get_sa_region_by_id(region_id: int):
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM sa_regions WHERE id = ?", (region_id,)).fetchone()
        return dict(row) if row else None


def list_sa_major_cities_by_region(region_id: int):
    """المدن «الكبرى» بمنطقة معيّنة (اللي عندها بيانات أحياء فعلية) — تُعرض كأزرار أولًا."""
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM sa_cities WHERE region_id = ? AND has_districts = 1 ORDER BY name",
            (region_id,),
        ).fetchall()
        return [dict(r) for r in rows]


def search_sa_cities(region_id: int, query: str, limit: int = 8):
    """بحث نصي (تطابق جزئي) عن مدينة/قرية داخل منطقة معيّنة — يشمل كل المدن حتى الصغيرة،
    مرتّب بحيث المدن الكبرى (عندها أحياء) تطلع أول."""
    with get_conn() as conn:
        rows = conn.execute(
            """
            SELECT * FROM sa_cities
            WHERE region_id = ? AND name LIKE ?
            ORDER BY has_districts DESC, name
            LIMIT ?
            """,
            (region_id, f"%{query.strip()}%", limit),
        ).fetchall()
        return [dict(r) for r in rows]


def search_sa_major_cities(region_id: int, query: str, limit: int = 8):
    """بحث نصي (اكتمال تلقائي) عن مدينة كبرى فقط (عندها أحياء حقيقية) داخل منطقة
    معيّنة — نفس تقييد لوحة الأزرار بالضبط: بدون مراكز صغيرة ولا قرى."""
    with get_conn() as conn:
        rows = conn.execute(
            """
            SELECT * FROM sa_cities
            WHERE region_id = ? AND has_districts = 1 AND name LIKE ?
            ORDER BY name
            LIMIT ?
            """,
            (region_id, f"%{query.strip()}%", limit),
        ).fetchall()
        return [dict(r) for r in rows]


def search_sa_districts(city_id: int, query: str, limit: int = 8):
    """بحث نصي (اكتمال تلقائي) عن حي داخل مدينة معيّنة."""
    with get_conn() as conn:
        rows = conn.execute(
            """
            SELECT * FROM sa_districts
            WHERE city_id = ? AND name LIKE ?
            ORDER BY name
            LIMIT ?
            """,
            (city_id, f"%{query.strip()}%", limit),
        ).fetchall()
        return [dict(r) for r in rows]


def get_sa_city_by_id(city_id: int):
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM sa_cities WHERE id = ?", (city_id,)).fetchone()
        return dict(row) if row else None


def list_sa_districts_by_city(city_id: int):
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM sa_districts WHERE city_id = ? ORDER BY name", (city_id,)
        ).fetchall()
        return [dict(r) for r in rows]


def get_sa_district_by_id(district_id: int):
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM sa_districts WHERE id = ?", (district_id,)).fetchone()
        return dict(row) if row else None


def nearest_sa_districts(district_id: int, exclude_ids: list[int], limit: int = 3):
    """يرجّع أقرب N حي لنفس حي الأصل (بنفس المدينة)، مرتّبة بالمسافة الفعلية (إحداثيات
    مركز كل حي)، باستثناء الأحياء اللي جُرّبت مسبقًا بنفس جلسة البحث. يُستخدم فقط بعد
    ما تنتهي نتائج الحي الأصلي بالكامل (مهما كان عددها) — لا نعرض حي مجاور قبل ذلك."""
    origin = get_sa_district_by_id(district_id)
    if not origin or origin["lat"] is None:
        return []

    with get_conn() as conn:
        placeholders = ",".join("?" for _ in exclude_ids) if exclude_ids else None
        query = "SELECT * FROM sa_districts WHERE city_id = ? AND lat IS NOT NULL"
        params = [origin["city_id"]]
        if placeholders:
            query += f" AND id NOT IN ({placeholders})"
            params.extend(exclude_ids)
        rows = conn.execute(query, params).fetchall()

    candidates = [dict(r) for r in rows]
    # مسافة إقليدية تقريبية على الإحداثيات (كافية لترتيب "الأقرب" داخل نفس المدينة،
    # بدون الحاجة لحساب هافرساين الدقيق على مسافات صغيرة زي هذي).
    def dist(d):
        return (d["lat"] - origin["lat"]) ** 2 + (d["lon"] - origin["lon"]) ** 2

    candidates.sort(key=dist)
    return candidates[:limit]


def nearest_sa_cities(city_id: int, exclude_ids: list[int], limit: int = 3):
    """يرجّع أقرب N مدينة (من نفس القائمة الرسمية) بغض النظر عن المنطقة الإدارية —
    مدينة قريبة بمنطقة مجاورة أهم من مدينة بعيدة بنفس المنطقة. يُستخدم فقط لما تنتهي
    كل خيارات الأحياء المجاورة بنفس المدينة الأصلية بلا نتائج."""
    origin = get_sa_city_by_id(city_id)
    if not origin or origin["lat"] is None:
        return []

    with get_conn() as conn:
        placeholders = ",".join("?" for _ in exclude_ids) if exclude_ids else None
        query = "SELECT * FROM sa_cities WHERE lat IS NOT NULL"
        params = []
        if placeholders:
            query += f" AND id NOT IN ({placeholders})"
            params.extend(exclude_ids)
        rows = conn.execute(query, params).fetchall()

    candidates = [dict(r) for r in rows]

    def dist(c):
        return (c["lat"] - origin["lat"]) ** 2 + (c["lon"] - origin["lon"]) ** 2

    candidates.sort(key=dist)
    return candidates[:limit]
