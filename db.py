# طبقة قاعدة البيانات — SQLite بسيطة (أو Turso/libSQL عند توفر متغيرات البيئة
# TURSO_DATABASE_URL و TURSO_AUTH_TOKEN، عشان تكون البيانات دائمة على استضافات
# ما تدعم تخزين دائم مثل Render المجاني). كل الدوال هنا متزامنة (sync) عمدًا؛
# نناديها من الهاندلرز غير المتزامنة عبر asyncio.to_thread.

import json
import math
import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone

from config import DB_PATH

TURSO_DATABASE_URL = os.environ.get("TURSO_DATABASE_URL", "")
TURSO_AUTH_TOKEN = os.environ.get("TURSO_AUTH_TOKEN", "")

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
FREE_CONTACTS_LIMIT = 7

RESULTS_PAGE_SIZE = 5


def _bulk_insert(conn, table, columns, rows, chunk_size=100):
    """إدخال عدة صفوف بأقل عدد ممكن من الاتصالات (مهم جدًا مع قاعدة بيانات
    شبكية مثل Turso، حيث كل استعلام منفصل يكلّف رحلة شبكة كاملة — إدخال
    آلاف الصفوف واحدًا تلو الآخر ممكن ياخذ دقائق طويلة أو يتجمّد ظاهريًا)."""
    if not rows:
        return
    col_list = ", ".join(columns)
    row_placeholder = "(" + ", ".join(["?"] * len(columns)) + ")"
    for i in range(0, len(rows), chunk_size):
        chunk = rows[i : i + chunk_size]
        values_sql = ", ".join([row_placeholder] * len(chunk))
        flat_params = [v for row in chunk for v in row]
        conn.execute(f"INSERT INTO {table} ({col_list}) VALUES {values_sql}", flat_params)


class _LibsqlRow:
    """صف نتيجة يدعم القراءة بالاسم (row["col"]) والموضع (row[0]) معًا،
    لأن libsql (Turso) يرجّع صفوف كـ tuple عادي ولا يدعم sqlite3.Row مباشرة."""

    __slots__ = ("_map", "_values")

    def __init__(self, description, values):
        self._values = tuple(values)
        self._map = {d[0]: v for d, v in zip(description or (), values)}

    def __getitem__(self, key):
        if isinstance(key, str):
            return self._map[key]
        return self._values[key]

    def get(self, key, default=None):
        return self._map.get(key, default)

    def keys(self):
        return self._map.keys()

    def __contains__(self, key):
        return key in self._map

    def __iter__(self):
        return iter(self._values)

    def __len__(self):
        return len(self._values)

    def __repr__(self):
        return f"_LibsqlRow({self._map!r})"


class _LibsqlCursorWrapper:
    def __init__(self, cursor):
        self._cursor = cursor

    def _wrap(self, row):
        if row is None:
            return None
        return _LibsqlRow(self._cursor.description, row)

    def fetchone(self):
        return self._wrap(self._cursor.fetchone())

    def fetchall(self):
        return [self._wrap(r) for r in self._cursor.fetchall()]

    def __getattr__(self, name):
        return getattr(self._cursor, name)


class _LibsqlConnWrapper:
    """يجعل اتصال libsql يتصرف مثل sqlite3.Connection (execute يرجّع صفوف
    بأسماء أعمدة)، بدون الحاجة لتعديل أي دالة أخرى بهذا الملف."""

    def __init__(self, conn):
        self._conn = conn

    def execute(self, sql, params=()):
        return _LibsqlCursorWrapper(self._conn.execute(sql, params))

    def cursor(self):
        return _LibsqlCursorWrapper(self._conn.cursor())

    def __getattr__(self, name):
        return getattr(self._conn, name)


@contextmanager
def get_conn():
    if TURSO_DATABASE_URL:
        # قاعدة بيانات خارجية دائمة (Turso/libSQL) — متوافقة تقريبًا 1:1 مع sqlite3.
        import libsql

        raw_conn = libsql.connect(database=TURSO_DATABASE_URL, auth_token=TURSO_AUTH_TOKEN)
        conn = _LibsqlConnWrapper(raw_conn)
    else:
        # timeout/busy_timeout: ثلاث برامج تكتب بنفس القاعدة (بوت تلغرام، بوت واتساب، اللوحة)
        # — لو صادف كتابتين بنفس اللحظة، الثانية تنتظر ثواني بدل ما تفشل بـ«database is locked».
        conn = sqlite3.connect(DB_PATH, timeout=15)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA busy_timeout = 15000")

    try:
        conn.execute("PRAGMA foreign_keys = ON")
    except Exception:
        pass

    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db():
    if not TURSO_DATABASE_URL:
        # WAL: القراءة ما توقف الكتابة والعكس — أنسب لعدة برامج على نفس الملف. إعداد دائم بالملف.
        try:
            with get_conn() as conn:
                conn.execute("PRAGMA journal_mode = WAL")
        except Exception:
            pass
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
        for col, ddl in (("wa_nudge_cycle_start", "TEXT"), ("wa_nudge_cycle_count", "INTEGER NOT NULL DEFAULT 0"),
                         ("nudge_first_at", "TEXT"),
                         # الفني ضغط «إيقاف الإشعارات» (تلغرام/واتساب) — الأدمن يقدر يرجّعها من اللوحة
                         ("tg_notify_off", "INTEGER NOT NULL DEFAULT 0"), ("wa_notify_off", "INTEGER NOT NULL DEFAULT 0"),
                         ("notify_off_at", "TEXT"),
                         # رقم واتساب اللي سجّل الفني (مسوّق/المالك أو شخص تحقق برمز) لو غير رقم الفني نفسه
                         ("registered_by", "TEXT")):
            if col not in existing_columns:
                # دورة إشعارات واتساب (المدفوعة): 5 بالشهر، وتوقف تلقائيًا بعد سنة من أول إشعار
                conn.execute(f"ALTER TABLE professionals ADD COLUMN {col} {ddl}")
        if "last_search_nudge_at" not in existing_columns:
            # تُستخدم لتنبيه الفني: "فيه عميل بحث عنك لكن ما ظهرت لأنك خلّصت فرصك
            # المجانية" — بحد أقصى مرة كل عدة ساعات حتى ما نزعجه بإشعارات متكررة.
            conn.execute(
                "ALTER TABLE professionals ADD COLUMN last_search_nudge_at TEXT"
            )
        if "covers_whole_city" not in existing_columns:
            # للمهن النادرة (معلّمة allow_city_wide بجدول professions): الفني يختار
            # يغطي المدينة كاملة بدل حصر نفسه بـ5 أحياء — يظهر بكل بحث بالمدينة
            # بغض النظر عن الحي اللي يبحث منه العميل.
            conn.execute(
                "ALTER TABLE professionals ADD COLUMN covers_whole_city INTEGER NOT NULL DEFAULT 0"
            )
        if "source" not in existing_columns:
            # مصدر وصول الفني للبوت (واتساب/فيسبوك/سناب/تيك توك...) — يُلتقط من
            # الوسم بعد ?start= برابط التسجيل، لمعرفة أي قناة تسويق فعّالة أكثر.
            conn.execute(
                "ALTER TABLE professionals ADD COLUMN source TEXT NOT NULL DEFAULT 'unknown'"
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

        # تبرّع/دعم اختياري من العميل (مو الفني) — منفصل تمامًا عن جدول اشتراكات
        # الفنيين (ما له علاقة بأي professional_id)، يظهر كرسالة اختيارية بعد كل
        # 10 ضغطات تواصل للعميل، وله حرية كاملة يتجاهله ويكمل البحث عادي.
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS donation_payments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                customer_telegram_id INTEGER NOT NULL,
                method TEXT NOT NULL,           -- 'tap' أو 'stars'
                external_id TEXT,
                amount_sar REAL NOT NULL,
                status TEXT NOT NULL DEFAULT 'pending',
                created_at TEXT NOT NULL,
                paid_at TEXT
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
            "CREATE INDEX IF NOT EXISTS idx_search_log_profession ON search_log (profession_id)"
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

        # دعم تعدد اللغات: اسم المجال/المهنة بالإنجليزي والأردو (العربي دائمًا بعمود name
        # الأصلي). أعمدة جديدة على جداول قديمة — نضيفها فقط لو ناقصة.
        for table in ("domains", "professions"):
            cols = {row["name"] for row in conn.execute(f"PRAGMA table_info({table})").fetchall()}
            if "name_en" not in cols:
                conn.execute(f"ALTER TABLE {table} ADD COLUMN name_en TEXT")
            if "name_ur" not in cols:
                conn.execute(f"ALTER TABLE {table} ADD COLUMN name_ur TEXT")

        prof_cols = {row["name"] for row in conn.execute("PRAGMA table_info(professions)").fetchall()}
        if "allow_city_wide" not in prof_cols:
            # مهن نادرة (أدمن يفعّلها يدويًا من لوحة التحكم) — تتيح للفني يختار
            # يغطي المدينة كاملة بدل حصر نفسه بـ5 أحياء بس، لأن قلة عددهم تخليهم
            # يختفون عن عملاء كثير لو حصروا نفسهم بأحياء محددة.
            conn.execute(
                "ALTER TABLE professions ADD COLUMN allow_city_wide INTEGER NOT NULL DEFAULT 0"
            )

        # تفضيل لغة كل مستخدم (عميل أو فني) — مستقل عن التسجيل كفني، ينطبق على أي
        # شخص يتفاعل مع البوت. العربي هو الافتراضي لمن لم يختر بعد.
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS user_languages (
                telegram_user_id INTEGER PRIMARY KEY,
                language TEXT NOT NULL DEFAULT 'ar'
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

        # ─────────────────────────── تعدد الدول (السعودية + مصر + الخليج) ───────────────────────────
        # نفس جداول sa_regions/sa_cities/sa_districts تشيل كل الدول، مع عمود country
        # (الافتراضي 'SA' — كل البيانات والتسجيلات القديمة سعودية).
        for table in ("sa_regions", "sa_cities"):
            cols = {row["name"] for row in conn.execute(f"PRAGMA table_info({table})").fetchall()}
            if "country" not in cols:
                conn.execute(f"ALTER TABLE {table} ADD COLUMN country TEXT NOT NULL DEFAULT 'SA'")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_sa_regions_country ON sa_regions (country)")

        prof_cols2 = {row["name"] for row in conn.execute("PRAGMA table_info(professionals)").fetchall()}
        if "country" not in prof_cols2:
            conn.execute("ALTER TABLE professionals ADD COLUMN country TEXT NOT NULL DEFAULT 'SA'")
        if "city_id" not in prof_cols2:
            # معرّف المدينة الرسمي — البحث يطابق عليه بدل اسم المدينة النصي (أسماء
            # تتكرر بين الدول/المحافظات، مثل «المطرية» بالقاهرة والدقهلية).
            conn.execute("ALTER TABLE professionals ADD COLUMN city_id INTEGER")
        if "profession2_id" not in prof_cols2:
            # مهنة ثانية اختيارية (حد أقصى مهنتين لكل فني). عدّاد الظهور times_shown
            # مشترك بين المهنتين — فالظهور الكلي يبقى عادل مقارنة بصاحب المهنة الواحدة.
            conn.execute("ALTER TABLE professionals ADD COLUMN profession2_id TEXT")
            conn.execute("ALTER TABLE professionals ADD COLUMN profession2_name TEXT")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_professionals_prof2 ON professionals (profession2_id)")
        if "bonus_contacts" not in prof_cols2:
            # فرص مجانية إضافية خاصة بالفني (مكافآت دعوة الزملاء) — تنضاف على الحد العام
            conn.execute("ALTER TABLE professionals ADD COLUMN bonus_contacts INTEGER NOT NULL DEFAULT 0")
        if "referred_by" not in prof_cols2:
            # معرّف الفني اللي دعا هذا الفني (من رابط ?start=ref_<id>)
            conn.execute("ALTER TABLE professionals ADD COLUMN referred_by INTEGER")
        if "wa_id" not in prof_cols2:
            # فني سجّل من بوت واتساب: رقم واتساب حقه (أرقام فقط). telegram_user_id يكون سالب
            # (-رقمه) لين يربط حسابه بتلغرام، وعندها يصير رقم حسابه الحقيقي بتلغرام.
            conn.execute("ALTER TABLE professionals ADD COLUMN wa_id TEXT")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_professionals_wa_id ON professionals (wa_id)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_professionals_country ON professionals (country)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_professionals_city_id ON professionals (city_id)")

        log_cols = {row["name"] for row in conn.execute("PRAGMA table_info(search_log)").fetchall()}
        if "country" not in log_cols:
            conn.execute("ALTER TABLE search_log ADD COLUMN country TEXT NOT NULL DEFAULT 'SA'")

        # آخر دولة اختارها المستخدم (عميل أو فني) — حتى ما نسأله عنها كل مرة يبحث.
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS user_countries (
                telegram_user_id INTEGER PRIMARY KEY,
                country TEXT NOT NULL
            )
            """
        )

        # ─────────────────────────── دعوة الزملاء ───────────────────────────
        # سجل دائم لكل حساب تلغرام انحسبت دعوته — مفتاحه حساب المدعو، فما ينحسب نفس
        # الشخص مرتين حتى لو حذف تسجيله وسجّل من جديد.
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS referral_credits (
                referred_telegram_id INTEGER PRIMARY KEY,
                referrer_id INTEGER NOT NULL,
                referred_professional_id INTEGER,
                bonus INTEGER NOT NULL,
                created_at TEXT NOT NULL
            )
            """
        )
        conn.execute("CREATE INDEX IF NOT EXISTS idx_referral_referrer ON referral_credits (referrer_id)")

        # ─────────────────────────── مدراء لوحة التحكم (حسب الدولة) ───────────────────────────
        # المدير العام (أنت) يبقى من ملف .env دائمًا. هذا الجدول لمدراء الدول (مثل مدير
        # مصر): يشوف فنيي دولته فقط، بدون تنزيل إكسل ولا إعدادات عامة ولا تعديل مهن.
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS admin_users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL UNIQUE,
                password_hash TEXT NOT NULL,
                country TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
            """
        )

        # ─────────────────────────── نشاط البوت (لمربع صحة السيرفر) ───────────────────────────
        # صف واحد لكل دقيقة فيها نشاط: عدد المستخدمين المختلفين وعدد الرسائل/الضغطات —
        # يُكتب مرة وحدة بالدقيقة (مو مع كل ضغطة)، فما له أي ثقل على البوت.
        # كلمات يكتبها الناس بخطوة اختيار المهنة (واتساب) — بدون أي ربط بالشخص (لا رقم ولا
        # معرّف): الكلمة + وش طابقت + التاريخ. لصفحة «الأكثر طلبًا» (مهن ناقصة يدوّرها الناس).
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS search_terms (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                term TEXT NOT NULL,
                term_norm TEXT NOT NULL,
                profession_id TEXT,
                matched_name TEXT,
                source TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
            """
        )
        conn.execute("CREATE INDEX IF NOT EXISTS idx_search_terms_norm ON search_terms (term_norm, created_at)")
        conn.execute("CREATE TABLE IF NOT EXISTS search_terms_ignored (term_norm TEXT PRIMARY KEY)")

        # سجل إشعارات الفنيين (خلصت فرصك / فيه عميل يدوّر عليك / يدوي من اللوحة) — عشان نعرف
        # كم وصله ولا استجاب (ما ضغط اشتراك ولا راسل البوت بعدها).
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS notify_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                professional_id INTEGER NOT NULL,
                kind TEXT NOT NULL,
                channel TEXT NOT NULL,
                paid INTEGER NOT NULL DEFAULT 0,
                ok INTEGER NOT NULL DEFAULT 1,
                sent_at TEXT NOT NULL,
                responded_at TEXT
            )
            """
        )
        conn.execute("CREATE INDEX IF NOT EXISTS idx_notify_prof ON notify_log (professional_id, sent_at)")
        # كل بحث كان سيظهر فيه الفني لولا انتهاء فرصه — للملخص الشهري («بحث عنك X عميل هذا الشهر»)
        conn.execute(
            "CREATE TABLE IF NOT EXISTS missed_searches (id INTEGER PRIMARY KEY AUTOINCREMENT, "
            "professional_id INTEGER NOT NULL, searched_at TEXT NOT NULL)"
        )
        conn.execute("CREATE INDEX IF NOT EXISTS idx_missed_prof ON missed_searches (professional_id, searched_at)")

        # أرقام مسموح لها تسجيل فنيين على أرقام أخرى بدون رمز تحقق (المالك والمسوّقين) — من اللوحة
        conn.execute("CREATE TABLE IF NOT EXISTS wa_registrars (phone TEXT PRIMARY KEY, name TEXT, created_at TEXT)")
        # رموز التحقق المرسلة (لتسجيل فني على رقم آخر) — حد يومي لكل مرسل لأن كل رمز مدفوع
        # آخر نتائج بحث لكل عميل/مهنة — نفس الـ5 تتكرر له 24 ساعة (ما يقدر يعيد البحث ليطلع فنيين أكثر)
        conn.execute("CREATE TABLE IF NOT EXISTS recent_results (customer_id INTEGER NOT NULL, profession_id TEXT NOT NULL, "
                     "ids_json TEXT NOT NULL, created_at TEXT NOT NULL, PRIMARY KEY (customer_id, profession_id))")
        conn.execute("CREATE TABLE IF NOT EXISTS otp_log (id INTEGER PRIMARY KEY AUTOINCREMENT, "
                     "sender TEXT NOT NULL, phone TEXT NOT NULL, sent_at TEXT NOT NULL)")

        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS activity_minutes (
                minute TEXT PRIMARY KEY,
                users INTEGER NOT NULL,
                updates INTEGER NOT NULL
            )
            """
        )
    import ratings   # جداول التقييم (ratings / rating_requests / wa_last_seen)
    ratings.ensure_tables()
    with get_conn() as conn:
        # طلب المالك: أرشيف الفنيين المحذوفين — يُحذفون من البوت نهائيًا (لا يظهرون لأحد)،
        # ونحتفظ هنا باسمهم ورقمهم وتقييمهم وسبب الحذف للتواصل معهم (يظهر في لوحة التحكم فقط).
        conn.execute("""CREATE TABLE IF NOT EXISTS deleted_professionals (
            id INTEGER PRIMARY KEY AUTOINCREMENT, original_id INTEGER, full_name TEXT, phone TEXT,
            profession_name TEXT, city TEXT, channel TEXT, deleted_by TEXT NOT NULL DEFAULT 'self',
            rating_avg REAL, rating_count INTEGER NOT NULL DEFAULT 0,
            registered_at TEXT, deleted_at TEXT NOT NULL, reason TEXT, reason_by TEXT, admin_note TEXT)""")


def _now_iso():
    return datetime.now(timezone.utc).isoformat()


# ─────────────────────────── المهن الأكثر طلبًا (قائمة الـ9 بواتساب + صفحة باللوحة) ───────────────────────────

SATELLITE_PROFESSION_ID = "p69"

# مهن أضافها المالك (طلب مباشر). كل وحدة تنضاف مرة وحدة فقط — لو الأدمن حذفها من
# اللوحة ما ترجع (علامة seed_extra_<id> بجدول settings).
EXTRA_PROFESSIONS = [
    ("p69", "d2", "فني ستالايت وكاميرات", ["تركيب دش", "برمجة رسيفر", "كاميرات مراقبة", "انتركم وجرس", "شبكات واي فاي"]),
    ("p70", "d2", "صيانة غسالات صحون", ["عدم التصريف", "تسريب ماء", "ما تسخّن", "تركيب غسالة صحون", "تغيير قطع"]),
    ("p71", "d2", "صيانة أفران", ["أفران غاز", "أفران كهرباء", "أفران مدمجة (بلت إن)", "تركيب فرن", "تغيير قطع وحساسات"]),
    ("p72", "d1", "نجار مسلح (بناء)", ["نجارة القواعد والأعمدة", "نجارة الأسقف والصبّات", "تركيب الشدات الخشبية", "فك الشدات"]),
]

# مهن تغيّر اسمها (توضيح للعميل) — نحدّث الاسم المحفوظ ببطاقات الفنيين المسجلين عليها
RENAMED_PROFESSION_IDS = ("p5", "p26", "p63", "p64")


def ensure_extra_professions():
    with get_conn() as conn:
        for pid, domain_id, name, services in EXTRA_PROFESSIONS:
            flag = f"seed_extra_{pid}"
            if conn.execute("SELECT 1 FROM settings WHERE key = ?", (flag,)).fetchone():
                continue
            if not conn.execute("SELECT 1 FROM domains WHERE id = ?", (domain_id,)).fetchone():
                continue  # البذر الأساسي للمهن ما صار بعد — نحاول بالتشغيل الجاي
            if not conn.execute("SELECT 1 FROM professions WHERE id = ?", (pid,)).fetchone():
                max_order = conn.execute(
                    "SELECT COALESCE(MAX(sort_order), -1) FROM professions WHERE domain_id = ?", (domain_id,)
                ).fetchone()[0]
                conn.execute(
                    "INSERT INTO professions (id, domain_id, name, isco_code, status, services_json, sort_order) "
                    "VALUES (?, ?, ?, NULL, 'مضافة يدويًا', ?, ?)",
                    (pid, domain_id, name, json.dumps(services, ensure_ascii=False), max_order + 1),
                )
            conn.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?, '1')", (flag,))
        marks = ",".join("?" * len(RENAMED_PROFESSION_IDS))
        for id_col, name_col in (("profession_id", "profession_name"), ("profession2_id", "profession2_name")):
            conn.execute(
                f"UPDATE professionals SET {name_col} = (SELECT name FROM professions WHERE id = {id_col}) "
                f"WHERE {id_col} IN ({marks}) AND EXISTS (SELECT 1 FROM professions WHERE id = {id_col}) "
                f"AND {name_col} != (SELECT name FROM professions WHERE id = {id_col})",
                RENAMED_PROFESSION_IDS,
            )


def get_profession_demand(days: int = 30) -> dict:
    """{profession_id: {"recent": بحث آخر N يوم, "total": كل البحث, "empty": بحث آخر N يوم بدون نتائج,
    "techs": فنيين نشطين}} — لصفحة «المهن الأكثر طلبًا» باللوحة."""
    since = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
    out: dict = {}
    with get_conn() as conn:
        for r in conn.execute(
            """
            SELECT profession_id,
                   COUNT(*) AS total,
                   SUM(CASE WHEN searched_at >= ? THEN 1 ELSE 0 END) AS recent,
                   SUM(CASE WHEN searched_at >= ? AND results_count = 0 THEN 1 ELSE 0 END) AS empty
            FROM search_log GROUP BY profession_id
            """,
            (since, since),
        ).fetchall():
            out[r["profession_id"]] = {"total": r["total"], "recent": r["recent"] or 0, "empty": r["empty"] or 0, "techs": 0}
        for col in ("profession_id", "profession2_id"):
            for r in conn.execute(
                f"SELECT {col} AS pid, COUNT(*) AS c FROM professionals WHERE status = ? AND {col} IS NOT NULL GROUP BY {col}",
                (STATUS_ACTIVE,),
            ).fetchall():
                out.setdefault(r["pid"], {"total": 0, "recent": 0, "empty": 0, "techs": 0})["techs"] += r["c"]
    return out


def get_professional_by_wa_id(wa_id: str):
    with get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM professionals WHERE wa_id = ? ORDER BY id DESC LIMIT 1", (wa_id,)
        ).fetchone()
        return dict(row) if row else None


def link_professional_telegram(professional_id: int, telegram_user_id: int) -> str:
    """يربط فني مسجّل من واتساب بحسابه في تلغرام. يرجّع: ok | already | linked_other |
    tg_has_account | not_found."""
    p = get_professional_by_id(professional_id)
    if not p:
        return "not_found"
    if p["telegram_user_id"] and p["telegram_user_id"] > 0:
        return "already" if p["telegram_user_id"] == telegram_user_id else "linked_other"
    other = get_professional_by_telegram_id(telegram_user_id)
    if other and other["id"] != professional_id:
        return "tg_has_account"
    with get_conn() as conn:
        conn.execute("UPDATE professionals SET telegram_user_id = ? WHERE id = ?", (telegram_user_id, professional_id))
    return "ok"


def get_professional_by_telegram_id(telegram_user_id: int):
    with get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM professionals WHERE telegram_user_id = ? "
            "ORDER BY id DESC LIMIT 1",
            (telegram_user_id,),
        ).fetchone()
        return dict(row) if row else None


def create_registration(data: dict) -> int:
    """يحفظ تسجيل فني جديد ويرجّع الـ id. القرار الحالي: موافقة فورية بدون مراجعة
    يدوية من الأدمن — الفني يصير STATUS_ACTIVE فور التسجيل (يظهر للعملاء مباشرة)."""
    with get_conn() as conn:
        cur = conn.execute(
            """
            INSERT INTO professionals (
                telegram_user_id, full_name, city, neighborhood,
                whatsapp_number, has_whatsapp, telegram_contact_number,
                domain_name, profession_id, profession_name,
                services_json, status, created_at, covers_whole_city, source,
                country, city_id, referred_by, profession2_id, profession2_name
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
                STATUS_ACTIVE,
                _now_iso(),
                1 if data.get("covers_whole_city") else 0,
                (data.get("source") or "unknown").strip()[:30] or "unknown",
                data.get("country") or "SA",
                data.get("city_id"),
                data.get("referred_by"),
                data.get("profession2_id") or None,
                data.get("profession2_name") or None,
            ),
        )
        professional_id = cur.lastrowid
        if data.get("wa_id"):
            conn.execute("UPDATE professionals SET wa_id = ? WHERE id = ?", (data["wa_id"], professional_id))
        if data.get("registered_by"):
            conn.execute("UPDATE professionals SET registered_by = ? WHERE id = ?",
                         (data["registered_by"], professional_id))
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


def _city_condition(conn, city: str, city_id: int | None):
    """شرط مطابقة المدينة لاستعلامات البحث. مع city_id (الحالة الطبيعية الآن):
    مطابقة دقيقة على المعرّف، + توافق مع تسجيلات قديمة ما فيها city_id (سعودية
    كلها) عبر الاسم بنفس الدولة فقط — حتى ما يطلع فني من دولة ثانية بسبب تشابه
    أسماء المدن. بدون city_id: السلوك القديم (مطابقة نصية على الاسم)."""
    if city_id:
        row = conn.execute("SELECT country FROM sa_cities WHERE id = ?", (city_id,)).fetchone()
        country = row["country"] if row else "SA"
        return (
            "(city_id = ? OR (city_id IS NULL AND country = ? AND city LIKE ?))",
            [city_id, country, f"%{city.strip()}%"],
        )
    return "city LIKE ?", [f"%{city.strip()}%"]


def search_active_professional_ids(
    profession_id: str, city: str, neighborhood: str | list[str] | None, district_id: int | list[int] | None = None,
    service: str | list[str] | None = None, city_id: int | None = None,
):
    """
    بحث العميل: مهنة (تطابق تام) + مدينة (تطابق تقريبي) + حي (اختياري، تطابق تقريبي)
    + خدمة فرعية (اختياري — يقلّل النتائج للفنيين اللي حدّدوا (وحدة أو أكثر) من هذي
    الخدمة عند التسجيل؛ اختيار متعدد بمنطق "أو" — يكفي إن الفني يقدّم خدمة وحدة على
    الأقل من المُعلَّمة حتى يظهر. لو ما اختار العميل خدمة معيّنة "الكل" يرجع كل فنيي
    هذي المهنة بغض النظر عن خدماتهم الفرعية).
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
        city_sql, city_params = _city_condition(conn, city, city_id)
        where = [
            "status = ?",
            "(profession_id = ? OR profession2_id = ?)",
            city_sql,
            "(free_contacts_used < ? + bonus_contacts OR is_subscribed = 1)",
        ]
        params = [STATUS_ACTIVE, profession_id, profession_id, *city_params, free_limit]

        if district_id:
            # اختيار متعدد للأحياء (منطق "أو" — يكفي تطابق حي وحد من المُعلَّمة).
            # المطابقة الدقيقة: الفني عنده أحد هذي الأحياء ضمن أحيائه المسجّلة (1-5).
            # + توافق مع فنيين قدامى قبل ميزة تعدد الأحياء (ما عندهم صفوف بجدول الربط
            # إطلاقًا) عبر مطابقة نصية على عمود neighborhood القديم كحل احتياطي لهم فقط.
            district_ids = [district_id] if isinstance(district_id, int) else list(district_id)
            neighborhood_names = [neighborhood] if isinstance(neighborhood, str) else (neighborhood or [])
            placeholders = ",".join("?" for _ in district_ids)
            name_conditions = " OR ".join(["neighborhood LIKE ?"] * len(neighborhood_names)) or "0"
            where.append(
                f"(covers_whole_city = 1 "
                f"OR id IN (SELECT professional_id FROM professional_districts WHERE district_id IN ({placeholders})) "
                f"OR (id NOT IN (SELECT professional_id FROM professional_districts) AND ({name_conditions})))"
            )
            params.extend(district_ids)
            for n in neighborhood_names:
                params.append(f"%{n.strip()}%")
        elif neighborhood:
            # توافق مع بيانات/بحث قديم بالنص الحر (بدون district_id محدد)
            names = [neighborhood] if isinstance(neighborhood, str) else neighborhood
            name_conditions = " OR ".join(["neighborhood LIKE ?"] * len(names))
            where.append(f"(covers_whole_city = 1 OR {name_conditions})")
            for n in names:
                params.append(f"%{n.strip()}%")

        where_sql = " AND ".join(where)

        rows = conn.execute(
            f"""
            SELECT id, services_json FROM professionals
            WHERE {where_sql}
            ORDER BY times_shown ASC, RANDOM()
            """,
            params,
        ).fetchall()

        if not service:
            return [r["id"] for r in rows]

        # فلترة الخدمة الفرعية تصير هنا بايثون (بدل SQL LIKE) لتفادي مشاكل ترميز
        # نصوص عربية تحتوي أقواس أو رموز خاصة داخل services_json. دعم اختيار متعدد
        # (قائمة خدمات) بمنطق "أو" — يكفي تقاطع وحدة على الأقل.
        wanted = {service} if isinstance(service, str) else set(service)
        matching_ids = []
        for r in rows:
            try:
                services = json.loads(r["services_json"]) if r["services_json"] else []
            except (TypeError, ValueError):
                services = []
            if wanted & set(services):
                matching_ids.append(r["id"])
        return matching_ids


# ─────────────────────────── تنبيه الفنيين اللي فاتهم البحث بسبب الاشتراك ───────────────────────────

NUDGE_COOLDOWN_HOURS = 6


def find_subscription_missed_professionals(
    profession_id: str, city: str, neighborhood: str | list[str] | None, district_id: int | list[int] | None = None,
    city_id: int | None = None,
):
    """يرجّع الفنيين اللي كانوا سيظهرون بهذا البحث (نفس المهنة/المدينة/الحي) لولا
    إنهم خلّصوا فرصهم المجانية ولا يوجد لهم اشتراك فعّال — نستخدمها لتنبيههم إن فيه
    طلب فاتهم، تشجيعًا على الاشتراك. لا نكرر التنبيه لنفس الفني أكثر من مرة كل
    NUDGE_COOLDOWN_HOURS ساعات حتى ما نزعجه."""
    free_limit = int(get_setting("free_contacts_limit", str(FREE_CONTACTS_LIMIT)))
    with get_conn() as conn:
        city_sql, city_params = _city_condition(conn, city, city_id)
        # بدون حد زمني (طلب المالك: تلغرام كل ما بحث عنه أحد). حدود واتساب (المدفوع) تنطبق
        # بموديول nudges.py — هنا نرجع كل الفنيين المخفيين بسبب انتهاء فرصهم.
        where = [
            "status = ?",
            "(profession_id = ? OR profession2_id = ?)",
            city_sql,
            "is_subscribed = 0",
            "free_contacts_used >= ? + bonus_contacts",
        ]
        params = [STATUS_ACTIVE, profession_id, profession_id, *city_params, free_limit]

        if district_id:
            district_ids = [district_id] if isinstance(district_id, int) else list(district_id)
            neighborhood_names = [neighborhood] if isinstance(neighborhood, str) else (neighborhood or [])
            placeholders = ",".join("?" for _ in district_ids)
            name_conditions = " OR ".join(["neighborhood LIKE ?"] * len(neighborhood_names)) or "0"
            where.append(
                f"(covers_whole_city = 1 "
                f"OR id IN (SELECT professional_id FROM professional_districts WHERE district_id IN ({placeholders})) "
                f"OR (id NOT IN (SELECT professional_id FROM professional_districts) AND ({name_conditions})))"
            )
            params.extend(district_ids)
            for n in neighborhood_names:
                params.append(f"%{n.strip()}%")
        elif neighborhood:
            names = [neighborhood] if isinstance(neighborhood, str) else neighborhood
            name_conditions = " OR ".join(["neighborhood LIKE ?"] * len(names))
            where.append(f"(covers_whole_city = 1 OR {name_conditions})")
            for n in names:
                params.append(f"%{n.strip()}%")

        where_sql = " AND ".join(where)
        rows = conn.execute(
            f"SELECT * FROM professionals WHERE {where_sql}", params
        ).fetchall()
        return [dict(r) for r in rows]


def mark_search_nudge_sent(professional_ids: list[int]):
    if not professional_ids:
        return
    with get_conn() as conn:
        now = _now_iso()
        conn.executemany(
            "UPDATE professionals SET last_search_nudge_at = ? WHERE id = ?",
            [(now, pid) for pid in professional_ids],
        )


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


CONTACT_DEDUPE_HOURS = 24


def professional_can_receive_contacts(p: dict | None) -> bool:
    """نفس شرط الظهور بالبحث: فني نشط، ومشترك أو باقي عنده فرص مجانية. يُستخدم عند
    الضغط على فني من نتائج قديمة — عشان ما يوصل رقم فني خلّصت فرصه وما اشترك."""
    if not p or p.get("status") != STATUS_ACTIVE:
        return False
    if p.get("is_subscribed"):
        return True
    limit = int(get_setting("free_contacts_limit", str(FREE_CONTACTS_LIMIT))) + (p.get("bonus_contacts") or 0)
    return (p.get("free_contacts_used") or 0) < limit


def register_contact(professional_id: int, customer_telegram_id: int) -> bool:
    """يسجّل تواصل عميل مع فني ويخصم فرصة مجانية — إلا لو نفس العميل تواصل مع نفس
    الفني خلال آخر 24 ساعة (ضغطة مكررة على نفس الزر ما تخصم فرصة ثانية من الفني).
    يرجّع True لو انحسبت كتواصل جديد."""
    since = (datetime.now(timezone.utc) - timedelta(hours=CONTACT_DEDUPE_HOURS)).isoformat()
    with get_conn() as conn:
        dup = conn.execute(
            "SELECT 1 FROM contact_clicks WHERE professional_id = ? AND customer_telegram_id = ? AND clicked_at >= ? LIMIT 1",
            (professional_id, customer_telegram_id, since),
        ).fetchone()
    if dup:
        return False
    log_contact_click(professional_id, customer_telegram_id)
    try:   # لو هذي آخر فرصة مجانية: ننبه الفني فورًا (بخيط منفصل — ما يأخر رد العميل)
        import limit_notice
        limit_notice.notify_if_exhausted_async(professional_id)
    except Exception:  # noqa: BLE001
        pass
    try:   # سؤال التقييم بعد 20 ساعة (ratings.py)
        import ratings
        ratings.enqueue(professional_id, customer_telegram_id)
    except Exception:  # noqa: BLE001
        pass
    return True


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

def activate_subscription(professional_id: int, days: int) -> str:
    """يفعّل اشتراك الفني (is_subscribed=1) ويمدّد تاريخ الانتهاء من اليوم + عدد الأيام.
    يرجّع تاريخ الانتهاء (ISO) عشان يُستخدم فورًا برسالة تأكيد الاشتراك للفني."""
    expires = (datetime.now(timezone.utc) + timedelta(days=days)).isoformat()
    with get_conn() as conn:
        conn.execute(
            "UPDATE professionals SET is_subscribed = 1, subscription_expires_at = ? WHERE id = ?",
            (expires, professional_id),
        )
    mark_notifications_responded(professional_id)
    return expires


def supersede_pending_payments(professional_id: int, method: str):
    """عملية دفع جديدة تلغي المعلّقة القديمة (عشان ما نفعّل الاشتراك مرتين من رابطين)."""
    with get_conn() as conn:
        conn.execute("UPDATE subscription_payments SET status = 'superseded' WHERE professional_id = ? "
                     "AND method = ? AND status = 'pending'", (professional_id, method))


def get_latest_pending_payment(professional_id: int, method: str, max_age_hours: int = 6):
    since = (datetime.now(timezone.utc) - timedelta(hours=max_age_hours)).isoformat()
    with get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM subscription_payments WHERE professional_id = ? AND method = ? AND status = 'pending' "
            "AND external_id IS NOT NULL AND created_at >= ? ORDER BY id DESC LIMIT 1",
            (professional_id, method, since),
        ).fetchone()
        return dict(row) if row else None


def find_expired_subscriptions():
    """يرجّع الفنيين المشتركين اللي انتهت مدة اشتراكهم فعليًا (تاريخ الانتهاء
    فات) وما زالوا مُعلَّمين is_subscribed=1 — يُستخدم من مهمة دورية تنبّههم
    بانتهاء الاشتراك وتوقف امتيازاتهم تلقائيًا."""
    now = datetime.now(timezone.utc).isoformat()
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM professionals WHERE is_subscribed = 1 "
            "AND subscription_expires_at IS NOT NULL AND subscription_expires_at <= ?",
            (now,),
        ).fetchall()
        return [dict(r) for r in rows]


def deactivate_expired_subscriptions(professional_ids: list[int]):
    if not professional_ids:
        return
    with get_conn() as conn:
        conn.executemany(
            "UPDATE professionals SET is_subscribed = 0 WHERE id = ?",
            [(pid,) for pid in professional_ids],
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


# ─────────────────────────── تبرّع/دعم اختياري من العميل ───────────────────────────

def count_contact_clicks_by_customer(customer_telegram_id: int) -> int:
    """عدد كل ضغطات التواصل (واتساب/تلغرام) اللي سواها هذا العميل بكل تاريخه —
    هذا هو مقياس "الاستخدام" اللي نعرض عليه رسالة الدعم الاختيارية كل 10 ضغطات."""
    with get_conn() as conn:
        row = conn.execute(
            "SELECT COUNT(*) AS c FROM contact_clicks WHERE customer_telegram_id = ?",
            (customer_telegram_id,),
        ).fetchone()
        return row["c"] if row else 0


def create_pending_donation(customer_telegram_id: int, method: str, external_id: str | None, amount_sar: float) -> int:
    with get_conn() as conn:
        cur = conn.execute(
            """
            INSERT INTO donation_payments
                (customer_telegram_id, method, external_id, amount_sar, status, created_at)
            VALUES (?, ?, ?, ?, 'pending', ?)
            """,
            (customer_telegram_id, method, external_id, amount_sar, _now_iso()),
        )
        return cur.lastrowid


def get_donation_by_external_id(method: str, external_id: str):
    with get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM donation_payments WHERE method = ? AND external_id = ? "
            "ORDER BY id DESC LIMIT 1",
            (method, external_id),
        ).fetchone()
        return dict(row) if row else None


def mark_donation_paid(donation_id: int):
    with get_conn() as conn:
        conn.execute(
            "UPDATE donation_payments SET status = 'paid', paid_at = ? WHERE id = ?",
            (_now_iso(), donation_id),
        )


def update_donation_external_id(donation_id: int, external_id: str):
    with get_conn() as conn:
        conn.execute(
            "UPDATE donation_payments SET external_id = ? WHERE id = ?",
            (external_id, donation_id),
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
                city: str, neighborhood: str | None, results_count: int, country: str = "SA"):
    if isinstance(neighborhood, list):
        neighborhood = "، ".join(neighborhood)
    with get_conn() as conn:
        conn.execute(
            """
            INSERT INTO search_log
                (customer_telegram_id, profession_id, profession_name, city,
                 neighborhood, results_count, searched_at, country)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (customer_telegram_id, profession_id, profession_name, city,
             neighborhood, results_count, _now_iso(), country or "SA"),
        )


def get_profession_popularity() -> dict:
    """يرجّع {profession_id: عدد مرات البحث} من سجل البحث بالكامل — استعلام
    COUNT/GROUP BY وحيد وخفيف (search_log مفهرس على profession_id)، يُستخدم
    لترتيب قائمة المهن بالعميل حسب الأكثر طلبًا. يشتغل مرة وحدة كل ما يفتح
    عميل /search، مو بكل ضغطة زر — تكلفته على السيرفر تافهة حتى مع آلاف السجلات."""
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT profession_id, COUNT(*) AS c FROM search_log GROUP BY profession_id"
        ).fetchall()
        return {r["profession_id"]: r["c"] for r in rows}


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

        domain_rows = []
        profession_rows = []
        for d_order, domain in enumerate(data["domains"]):
            domain_rows.append((domain["id"], domain["name"], d_order))
            for p_order, prof in enumerate(domain["professions"]):
                profession_rows.append((
                    prof["id"], domain["id"], prof["name"], prof.get("isco_code"),
                    prof.get("status"), _json.dumps(prof.get("services", []), ensure_ascii=False),
                    p_order,
                ))

        _bulk_insert(conn, "domains", ["id", "name", "sort_order"], domain_rows)
        _bulk_insert(
            conn, "professions",
            ["id", "domain_id", "name", "isco_code", "status", "services_json", "sort_order"],
            profession_rows,
        )
        return True


def sync_professions_from_json(json_path):
    """يزامن جداول domains/professions مع data/professions.json في كل تشغيل للبوت
    (UPSERT: يضيف مهنة/مجال جديد أو يحدّث اسمه/خدماته لو تغيّر بالملف)، بدل الدالة
    القديمة أعلاه اللي كانت تبذر مرة واحدة فقط وتتجاهل أي تعديل لاحق على الملف.
    لا تحذف أي مهنة/مجال — فقط تضيف/تحدّث، حتى ما تنكسر بيانات فنيين مسجّلين
    مسبقًا بمهنة قديمة."""
    import json as _json

    with open(json_path, encoding="utf-8") as f:
        data = _json.load(f)

    with get_conn() as conn:
        for d_order, domain in enumerate(data["domains"]):
            conn.execute(
                """
                INSERT INTO domains (id, name, sort_order) VALUES (?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET name = excluded.name, sort_order = excluded.sort_order
                """,
                (domain["id"], domain["name"], d_order),
            )
            for p_order, prof in enumerate(domain["professions"]):
                conn.execute(
                    """
                    INSERT INTO professions
                        (id, domain_id, name, isco_code, status, services_json, sort_order)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(id) DO UPDATE SET
                        domain_id = excluded.domain_id, name = excluded.name,
                        isco_code = excluded.isco_code, status = excluded.status,
                        services_json = excluded.services_json, sort_order = excluded.sort_order
                    """,
                    (
                        prof["id"], domain["id"], prof["name"], prof.get("isco_code"),
                        prof.get("status"), _json.dumps(prof.get("services", []), ensure_ascii=False),
                        p_order,
                    ),
                )
    # اسم المهنة محفوظ أيضًا بصف كل فني — نحدّثه لو تغيّر اسم المهنة (مثل «ميكب آرتست» ← «خبيرة مكياج»)
    with get_conn() as conn:
        conn.execute(
            "UPDATE professionals SET profession_name = (SELECT name FROM professions WHERE id = professionals.profession_id) "
            "WHERE profession_id IN (SELECT id FROM professions) "
            "AND profession_name != (SELECT name FROM professions WHERE id = professionals.profession_id)")
        conn.execute(
            "UPDATE professionals SET profession2_name = (SELECT name FROM professions WHERE id = professionals.profession2_id) "
            "WHERE profession2_id IN (SELECT id FROM professions) "
            "AND profession2_name != (SELECT name FROM professions WHERE id = professionals.profession2_id)")


def apply_name_translations(domain_translations: dict, profession_translations: dict):
    """يحدّث name_en/name_ur لكل مجال/مهنة من قواميس ثابتة بالكود (translations_data.py).
    آمن يتكرر تشغيله (idempotent) — نفّذه كل تشغيل بعد البذر عشان أي إضافة ترجمة جديدة
    بالكود تنعكس فورًا بدون ما نحتاج نمسح قاعدة البيانات."""
    with get_conn() as conn:
        for domain_id, tr in domain_translations.items():
            conn.execute(
                # تعبئة الفارغ فقط — ما نكتب فوق ترجمة عدّلها المالك من لوحة التحكم
                "UPDATE domains SET name_en = COALESCE(NULLIF(name_en, ''), ?), "
                "name_ur = COALESCE(NULLIF(name_ur, ''), ?) WHERE id = ?",
                (tr.get("en"), tr.get("ur"), domain_id),
            )
        for profession_id, tr in profession_translations.items():
            conn.execute(
                "UPDATE professions SET name_en = COALESCE(NULLIF(name_en, ''), ?), "
                "name_ur = COALESCE(NULLIF(name_ur, ''), ?) WHERE id = ?",
                (tr.get("en"), tr.get("ur"), profession_id),
            )


def get_user_language(telegram_user_id: int) -> str:
    """يرجّع لغة المستخدم المحفوظة، أو 'ar' افتراضيًا لمن لم يختر بعد."""
    with get_conn() as conn:
        row = conn.execute(
            "SELECT language FROM user_languages WHERE telegram_user_id = ?", (telegram_user_id,)
        ).fetchone()
        return row["language"] if row else "ar"


def has_chosen_language(telegram_user_id: int) -> bool:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT 1 FROM user_languages WHERE telegram_user_id = ?", (telegram_user_id,)
        ).fetchone()
        return row is not None


def set_user_language(telegram_user_id: int, language: str):
    with get_conn() as conn:
        conn.execute(
            """
            INSERT INTO user_languages (telegram_user_id, language) VALUES (?, ?)
            ON CONFLICT (telegram_user_id) DO UPDATE SET language = excluded.language
            """,
            (telegram_user_id, language),
        )


def get_user_country(telegram_user_id: int) -> str | None:
    """آخر دولة اختارها المستخدم (أو None لو ما اختار بعد)."""
    with get_conn() as conn:
        row = conn.execute(
            "SELECT country FROM user_countries WHERE telegram_user_id = ?", (telegram_user_id,)
        ).fetchone()
        return row["country"] if row else None


def set_user_country(telegram_user_id: int, country: str):
    # جدول مستقل عن user_languages عمدًا — الإضافة هناك تعتبر المستخدم "اختار لغته"
    # وتدخل بعدد المستخدمين بالإحصائيات، وهذا مو المقصود هنا.
    with get_conn() as conn:
        conn.execute(
            """
            INSERT INTO user_countries (telegram_user_id, country) VALUES (?, ?)
            ON CONFLICT (telegram_user_id) DO UPDATE SET country = excluded.country
            """,
            (telegram_user_id, country),
        )


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


def update_profession(
    profession_id: str, name: str, isco_code: str | None, services: list[str],
    allow_city_wide: bool | None = None,
):
    with get_conn() as conn:
        if allow_city_wide is None:
            conn.execute(
                "UPDATE professions SET name = ?, isco_code = ?, services_json = ? WHERE id = ?",
                (name, isco_code, json.dumps(services, ensure_ascii=False), profession_id),
            )
        else:
            conn.execute(
                "UPDATE professions SET name = ?, isco_code = ?, services_json = ?, allow_city_wide = ? WHERE id = ?",
                (name, isco_code, json.dumps(services, ensure_ascii=False), 1 if allow_city_wide else 0, profession_id),
            )


def set_domain_translations(domain_id: str, name_en: str | None, name_ur: str | None):
    with get_conn() as conn:
        conn.execute("UPDATE domains SET name_en = ?, name_ur = ? WHERE id = ?",
                     ((name_en or "").strip() or None, (name_ur or "").strip() or None, domain_id))


def set_profession_translations(profession_id: str, name_en: str | None, name_ur: str | None):
    """ترجمة اسم المهنة (لوحة التحكم) — طلب المالك: أي مهنة جديدة تُترجم لكل لغات البوت."""
    with get_conn() as conn:
        conn.execute("UPDATE professions SET name_en = ?, name_ur = ? WHERE id = ?",
                     ((name_en or "").strip() or None, (name_ur or "").strip() or None, profession_id))


def delete_profession(profession_id: str) -> bool:
    """يحذف المهنة فقط لو ما فيه فنيين مسجّلين عليها حاليًا (حماية من كسر بيانات موجودة)."""
    with get_conn() as conn:
        count = conn.execute(
            "SELECT COUNT(*) FROM professionals WHERE profession_id = ? OR profession2_id = ?",
            (profession_id, profession_id),
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
    country: str | None = None,
    channel: str | None = None,
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
        where.append("(profession_id = ? OR profession2_id = ?)")
        params.extend([profession_id, profession_id])
    if subscribed is not None:
        where.append("is_subscribed = ?")
        params.append(1 if subscribed else 0)
    if query:
        where.append("(full_name LIKE ? OR whatsapp_number LIKE ? OR telegram_contact_number LIKE ?)")
        like = f"%{query.strip()}%"
        params.extend([like, like, like])
    if channel == "whatsapp":
        where.append("wa_id IS NOT NULL")
    elif channel == "telegram":
        where.append("wa_id IS NULL")
    if country:
        where.append("country = ?")
        params.append(country)

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
    country: str | None = None,
    channel: str | None = None,
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
        where.append("(profession_id = ? OR profession2_id = ?)")
        params.extend([profession_id, profession_id])
    if subscribed is not None:
        where.append("is_subscribed = ?")
        params.append(1 if subscribed else 0)
    if query:
        where.append("(full_name LIKE ? OR whatsapp_number LIKE ? OR telegram_contact_number LIKE ?)")
        like = f"%{query.strip()}%"
        params.extend([like, like, like])
    if channel == "whatsapp":
        where.append("wa_id IS NOT NULL")
    elif channel == "telegram":
        where.append("wa_id IS NULL")
    if country:
        where.append("country = ?")
        params.append(country)

    where_sql = f"WHERE {' AND '.join(where)}" if where else ""

    with get_conn() as conn:
        return conn.execute(
            f"SELECT COUNT(*) FROM professionals {where_sql}", params
        ).fetchone()[0]


def admin_list_cities(country: str | None = None) -> list[str]:
    """مدن مميزة موجودة فعليًا بجدول الفنيين — تُستخدم كخيارات فلترة جاهزة باللوحة."""
    with get_conn() as conn:
        if country:
            rows = conn.execute(
                "SELECT DISTINCT city FROM professionals WHERE country = ? ORDER BY city", (country,)
            ).fetchall()
        else:
            rows = conn.execute("SELECT DISTINCT city FROM professionals ORDER BY city").fetchall()
        return [r["city"] for r in rows]


def admin_coverage_summary(country: str | None = None) -> list[dict]:
    """ملخص جاهزية كل مدينة للإطلاق: عدد الفنيين النشطين فيها، وعدد المهن
    المختلفة اللي عندها فني نشط واحد على الأقل. تُستخدم بصفحة "مؤشرات التغطية"
    باللوحة لمعرفة أي مدينة جاهزة تُفتح للعملاء وأيهم ناقصة فنيين."""
    with get_conn() as conn:
        rows = conn.execute(
            """
            SELECT p.city,
                   COUNT(*) AS total_active,
                   (SELECT COUNT(DISTINCT pid) FROM (
                        SELECT profession_id AS pid FROM professionals
                        WHERE status = ? AND city = p.city AND (? IS NULL OR country = ?)
                        UNION
                        SELECT profession2_id FROM professionals
                        WHERE status = ? AND city = p.city AND profession2_id IS NOT NULL
                              AND (? IS NULL OR country = ?)
                   )) AS distinct_professions
            FROM professionals p
            WHERE p.status = ? AND (? IS NULL OR p.country = ?)
            GROUP BY p.city
            ORDER BY total_active DESC
            """,
            (STATUS_ACTIVE, country, country, STATUS_ACTIVE, country, country, STATUS_ACTIVE, country, country),
        ).fetchall()
        return [dict(r) for r in rows]


def admin_coverage_matrix(country: str | None = None) -> list[dict]:
    """عدد الفنيين النشطين لكل (مدينة × مهنة) — المادة الخام لجدول التغطية
    التفصيلي (صفوف = مهن، أعمدة = مدن) بصفحة "مؤشرات التغطية"."""
    with get_conn() as conn:
        rows = conn.execute(
            """
            SELECT city, profession_id, COUNT(*) AS cnt FROM (
                SELECT city, profession_id FROM professionals
                WHERE status = ? AND (? IS NULL OR country = ?)
                UNION ALL
                SELECT city, profession2_id FROM professionals
                WHERE status = ? AND profession2_id IS NOT NULL AND (? IS NULL OR country = ?)
            )
            GROUP BY city, profession_id
            """,
            (STATUS_ACTIVE, country, country, STATUS_ACTIVE, country, country),
        ).fetchall()
        return [dict(r) for r in rows]


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


def archive_professional(professional_id: int, deleted_by: str = "self") -> int | None:
    """ينسخ بيانات التواصل الأساسية للفني إلى أرشيف المحذوفين قبل حذفه (طلب المالك). يرجّع رقم سجل الأرشيف."""
    p = get_professional_by_id(professional_id)
    if not p:
        return None
    try:
        import ratings
        phone = _phone_digits(p.get("whatsapp_number") or "")
        avg, cnt = ratings.summary_by_phones([phone]).get(phone, (None, 0))
        ratings.forget_professional(professional_id)
    except Exception:
        phone, avg, cnt = _phone_digits(p.get("whatsapp_number") or ""), None, 0
    prof = p.get("profession_name") or ""
    if p.get("profession2_name"):
        prof += f" + {p['profession2_name']}"
    with get_conn() as conn:
        cur = conn.execute(
            "INSERT INTO deleted_professionals (original_id, full_name, phone, profession_name, city, channel, "
            "deleted_by, rating_avg, rating_count, registered_at, deleted_at) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            (professional_id, p.get("full_name"), phone, prof, p.get("city"),
             "wa" if p.get("wa_id") else "tg", deleted_by, avg, cnt, p.get("created_at"), _now_iso()))
        return cur.lastrowid


def set_deletion_reason(archive_id: int, reason: str, by: str = "pro"):
    with get_conn() as conn:
        conn.execute("UPDATE deleted_professionals SET reason=?, reason_by=? WHERE id=?",
                     ((reason or "").strip()[:500], by, archive_id))


def set_deletion_note(archive_id: int, note: str):
    with get_conn() as conn:
        conn.execute("UPDATE deleted_professionals SET admin_note=? WHERE id=?", ((note or "").strip()[:1000], archive_id))


def list_deleted_professionals(limit: int = 300) -> list[dict]:
    with get_conn() as conn:
        return [dict(r) for r in conn.execute(
            "SELECT * FROM deleted_professionals ORDER BY id DESC LIMIT ?", (limit,)).fetchall()]


ARCHIVE_DAYS = 90   # طلب المالك + نظام حماية البيانات (م18): أرشيف المحذوفين وتقييماتهم يُحذف بعد 90 يومًا


def purge_archive(archive_ids: list[int]):
    """حذف كلي فوري (زر «احذف كل شيء» أو انتهاء الـ90 يومًا): سجل الأرشيف + تقييماته المربوطة برقمه
    (إلا لو رجع وسجّل بنفس الرقم — تقييماته صارت تخص تسجيله الحالي)."""
    with get_conn() as conn:
        active = {_phone_digits(r[0] or "") for r in conn.execute("SELECT whatsapp_number FROM professionals").fetchall()}
        for aid in archive_ids:
            row = conn.execute("SELECT phone FROM deleted_professionals WHERE id=?", (aid,)).fetchone()
            if row and row[0] and row[0] not in active:
                conn.execute("DELETE FROM ratings WHERE phone=?", (row[0],))
            conn.execute("DELETE FROM deleted_professionals WHERE id=?", (aid,))


def purge_expired_archive(days: int = ARCHIVE_DAYS) -> int:
    from datetime import datetime as _dt, timedelta as _td, timezone as _tz
    cutoff = (_dt.now(_tz.utc) - _td(days=days)).isoformat()
    with get_conn() as conn:
        ids = [r[0] for r in conn.execute("SELECT id FROM deleted_professionals WHERE deleted_at < ?", (cutoff,)).fetchall()]
    if ids:
        purge_archive(ids)
    return len(ids)


def remove_deleted_archive(archive_id: int):
    """حذف السجل من الأرشيف نفسه (لو طلب الفني حذف بياناته كليًا) — مع تقييماته."""
    purge_archive([archive_id])


def admin_delete_professional(professional_id: int):
    """حذف نهائي لسجل فني (مع سجلات التواصل والدفعات المرتبطة به) — إجراء لا رجعة فيه."""
    archive_professional(professional_id, deleted_by="admin")
    with get_conn() as conn:
        conn.execute("DELETE FROM contact_clicks WHERE professional_id = ?", (professional_id,))
        conn.execute("DELETE FROM subscription_payments WHERE professional_id = ?", (professional_id,))
        conn.execute("DELETE FROM professional_districts WHERE professional_id = ?", (professional_id,))
        conn.execute("DELETE FROM professionals WHERE id = ?", (professional_id,))


def delete_wa_professional(wa_id: str) -> list[int]:
    """حذف نهائي لتسجيل الفني المسجّل من واتساب (بطلبه هو عبر «d») مع كل ما يرتبط به.
    يرجّع أرقام سجلاته في أرشيف المحذوفين (لحفظ سبب الحذف)."""
    with get_conn() as conn:
        ids = [r["id"] for r in conn.execute("SELECT id FROM professionals WHERE wa_id = ?", (wa_id,)).fetchall()]
    archived = [a for a in (archive_professional(pid) for pid in ids) if a]
    with get_conn() as conn:
        for pid in ids:
            for t in ("contact_clicks", "subscription_payments", "professional_districts", "notify_log", "missed_searches"):
                conn.execute(f"DELETE FROM {t} WHERE professional_id = ?", (pid,))
        conn.execute("DELETE FROM professionals WHERE wa_id = ?", (wa_id,))
    return archived


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


def delete_all_user_data(telegram_user_id: int) -> list[int]:
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
    archived = [a for a in (archive_professional(pid) for pid in prof_ids) if a]
    try:
        import ratings
        ratings.forget_customer(telegram_user_id)
    except Exception:
        pass
    with get_conn() as conn:
        for pid in prof_ids:
            conn.execute("DELETE FROM contact_clicks WHERE professional_id = ?", (pid,))
            conn.execute("DELETE FROM subscription_payments WHERE professional_id = ?", (pid,))
            conn.execute("DELETE FROM professional_districts WHERE professional_id = ?", (pid,))
            conn.execute("DELETE FROM referral_credits WHERE referrer_id = ?", (pid,))
        conn.execute("DELETE FROM referral_credits WHERE referred_telegram_id = ?", (telegram_user_id,))
        conn.execute("DELETE FROM professionals WHERE telegram_user_id = ?", (telegram_user_id,))
        conn.execute("DELETE FROM search_log WHERE customer_telegram_id = ?", (telegram_user_id,))
        conn.execute("DELETE FROM contact_clicks WHERE customer_telegram_id = ?", (telegram_user_id,))
        conn.execute("DELETE FROM user_languages WHERE telegram_user_id = ?", (telegram_user_id,))
        conn.execute("DELETE FROM user_countries WHERE telegram_user_id = ?", (telegram_user_id,))
    return archived


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
            SELECT sp.*, p.full_name, p.profession_name, p.whatsapp_number, p.country
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


def get_admin_stats(country: str | None = None) -> dict:
    """إحصائيات عامة للوحة الرئيسية: أعداد الفنيين بكل حالة، التواصلات، الإيرادات،
    وأكثر المهن والمدن طلبًا. country (اختياري) يحصر كل الأرقام بدولة وحدة —
    يُستخدم لمدير الدولة، والمدير العام يقدر يفلتر فيه أيضًا."""
    # شرط دولة جاهز لإعادة الاستخدام: (? IS NULL OR country = ?) يرجع كل شي لو country فاضي
    cflag = (country, country)
    with get_conn() as conn:
        # إجمالي المستخدمين اللي دخلوا البوت وسووا /start ولو مرة (كل مستخدم
        # يُسجَّل بجدول user_languages أول ما يختار لغته). لمدير الدولة: من اختاروا
        # دولته (بالبحث أو التسجيل) — أقرب تقدير متاح لمستخدمي دولة معيّنة.
        if country:
            total_users = conn.execute(
                "SELECT COUNT(*) FROM user_countries WHERE country = ?", (country,)
            ).fetchone()[0]
        else:
            total_users = conn.execute("SELECT COUNT(*) FROM user_languages").fetchone()[0]

        status_counts = {
            row["status"]: row["c"]
            for row in conn.execute(
                "SELECT status, COUNT(*) AS c FROM professionals "
                "WHERE (? IS NULL OR country = ?) GROUP BY status",
                cflag,
            ).fetchall()
        }
        total_professionals = sum(status_counts.values())
        subscribed_count = conn.execute(
            "SELECT COUNT(*) FROM professionals WHERE is_subscribed = 1 AND (? IS NULL OR country = ?)",
            cflag,
        ).fetchone()[0]
        total_contact_clicks = conn.execute(
            """
            SELECT COUNT(*) FROM contact_clicks cc
            JOIN professionals p ON p.id = cc.professional_id
            WHERE (? IS NULL OR p.country = ?)
            """,
            cflag,
        ).fetchone()[0]
        total_searches = conn.execute(
            "SELECT COUNT(*) FROM search_log WHERE (? IS NULL OR country = ?)", cflag
        ).fetchone()[0]

        paid_payments = conn.execute(
            """
            SELECT sp.method, sp.amount FROM subscription_payments sp
            JOIN professionals p ON p.id = sp.professional_id
            WHERE sp.status = 'paid' AND (? IS NULL OR p.country = ?)
            """,
            cflag,
        ).fetchall()
        revenue_sar = sum(_parse_amount_sar(r["amount"]) for r in paid_payments if r["method"] == "tap")
        stars_paid_count = sum(1 for r in paid_payments if r["method"] == "stars")

        top_professions = conn.execute(
            """
            SELECT profession_name, COUNT(*) AS c FROM search_log
            WHERE (? IS NULL OR country = ?)
            GROUP BY profession_name ORDER BY c DESC LIMIT 5
            """,
            cflag,
        ).fetchall()
        top_cities = conn.execute(
            """
            SELECT city, COUNT(*) AS c FROM search_log
            WHERE (? IS NULL OR country = ?)
            GROUP BY city ORDER BY c DESC LIMIT 5
            """,
            cflag,
        ).fetchall()

        source_counts = conn.execute(
            """
            SELECT source, COUNT(*) AS c FROM professionals
            WHERE (? IS NULL OR country = ?)
            GROUP BY source ORDER BY c DESC
            """,
            cflag,
        ).fetchall()

        country_counts = conn.execute(
            "SELECT country, COUNT(*) AS c FROM professionals GROUP BY country ORDER BY c DESC"
        ).fetchall()

        return {
            "total_users": total_users,
            "status_counts": status_counts,
            "total_professionals": total_professionals,
            "subscribed_count": subscribed_count,
            "total_contact_clicks": total_contact_clicks,
            "total_searches": total_searches,
            "revenue_sar": revenue_sar,
            "stars_paid_count": stars_paid_count,
            "top_professions": [dict(r) for r in top_professions],
            "top_cities": [dict(r) for r in top_cities],
            "source_counts": [dict(r) for r in source_counts],
            "country_counts": [dict(r) for r in country_counts],
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

        _bulk_insert(
            conn, "sa_regions", ["id", "name"],
            [(r["id"], r["name"]) for r in regions],
        )
        _bulk_insert(
            conn, "sa_cities", ["id", "region_id", "name", "has_districts", "lat", "lon"],
            [
                (
                    c["id"], c["region_id"], c["name"],
                    1 if c["id"] in cities_with_districts else 0,
                    c.get("lat"), c.get("lon"),
                )
                for c in cities
            ],
        )
        _bulk_insert(
            conn, "sa_districts", ["id", "city_id", "name", "lat", "lon"],
            [(d["id"], d["city_id"], d["name"], d.get("lat"), d.get("lon")) for d in districts],
        )
        return True


def sync_saudi_geo_from_json(regions_path, cities_path, districts_path):
    """يزامن جداول sa_regions/sa_cities/sa_districts مع ملفات JSON الرسمية في كل
    تشغيل للبوت (UPSERT)، بدل الدالة القديمة أعلاه اللي تبذر مرة واحدة فقط وتتجاهل
    أي تصحيح/إضافة لاحقة (هذا كان سبب نقص أحياء بعض المدن مثل جدة على السيرفر رغم
    اكتمالها بالملف). لا تحذف أي حي/مدينة — فقط تضيف/تحدّث."""
    import json as _json

    with open(regions_path, encoding="utf-8") as f:
        regions = _json.load(f)
    with open(cities_path, encoding="utf-8") as f:
        cities = _json.load(f)
    with open(districts_path, encoding="utf-8") as f:
        districts = _json.load(f)

    cities_with_districts = {d["city_id"] for d in districts}

    with get_conn() as conn:
        for r in regions:
            conn.execute(
                "INSERT INTO sa_regions (id, name) VALUES (?, ?) "
                "ON CONFLICT(id) DO UPDATE SET name = excluded.name",
                (r["id"], r["name"]),
            )
        for c in cities:
            conn.execute(
                """
                INSERT INTO sa_cities (id, region_id, name, has_districts, lat, lon)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    region_id = excluded.region_id, name = excluded.name,
                    has_districts = excluded.has_districts, lat = excluded.lat, lon = excluded.lon
                """,
                (
                    c["id"], c["region_id"], c["name"],
                    1 if c["id"] in cities_with_districts else 0,
                    c.get("lat"), c.get("lon"),
                ),
            )
        for d in districts:
            conn.execute(
                """
                INSERT INTO sa_districts (id, city_id, name, lat, lon)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    city_id = excluded.city_id, name = excluded.name,
                    lat = excluded.lat, lon = excluded.lon
                """,
                (d["id"], d["city_id"], d["name"], d.get("lat"), d.get("lon")),
            )


def sync_extra_geo_from_json(geo_path):
    """يزامن (UPSERT) بيانات دول التوسع (مصر + الخليج) من data/extra_geo/geo.json
    لنفس جداول المناطق/المدن/الأحياء، مع عمود country. لا يحذف شي — فقط يضيف/يحدّث.
    المدن بدون أحياء (has_districts=0) تُعرض عادي، والفني فيها يغطي المدينة كاملة."""
    import json as _json

    with open(geo_path, encoding="utf-8") as f:
        data = _json.load(f)

    cities_with_districts = {d["city_id"] for d in data["districts"]}

    with get_conn() as conn:
        _bulk_upsert(
            conn, "sa_regions", ["id", "name", "country"],
            [(r["id"], r["name"], r["country"]) for r in data["regions"]],
        )
        _bulk_upsert(
            conn, "sa_cities", ["id", "region_id", "name", "has_districts", "lat", "lon", "country"],
            [
                (c["id"], c["region_id"], c["name"], 1 if c["id"] in cities_with_districts else 0,
                 c.get("lat"), c.get("lon"), c["country"])
                for c in data["cities"]
            ],
        )
        _bulk_upsert(
            conn, "sa_districts", ["id", "city_id", "name", "lat", "lon"],
            [(d["id"], d["city_id"], d["name"], d.get("lat"), d.get("lon")) for d in data["districts"]],
        )

        # تنظيف: أي منطقة/مدينة/حي لدول التوسع اختفى من الملف (اسم تغيّر أو تكرار
        # انشال) ينحذف — حتى ما يظهر مكرر بالقوائم. ما نلمس أبدًا السعودية، ولا أي
        # حي/مدينة مربوط بفني مسجّل فعليًا (يبقى حتى ما تنكسر بياناته).
        keep_d = {d["id"] for d in data["districts"]}
        keep_c = {c["id"] for c in data["cities"]}
        keep_r = {r["id"] for r in data["regions"]}
        used_d = {r[0] for r in conn.execute("SELECT DISTINCT district_id FROM professional_districts").fetchall()}
        used_c = {r[0] for r in conn.execute("SELECT DISTINCT city_id FROM professionals WHERE city_id IS NOT NULL").fetchall()}

        stale_d = [
            r["id"] for r in conn.execute(
                "SELECT d.id FROM sa_districts d JOIN sa_cities c ON c.id = d.city_id WHERE c.country != 'SA'"
            ).fetchall()
            if r["id"] not in keep_d and r["id"] not in used_d
        ]
        for did in stale_d:
            conn.execute("DELETE FROM sa_districts WHERE id = ?", (did,))

        for r in conn.execute("SELECT id FROM sa_cities WHERE country != 'SA'").fetchall():
            cid = r["id"]
            if cid in keep_c or cid in used_c:
                continue
            if conn.execute("SELECT 1 FROM sa_districts WHERE city_id = ? LIMIT 1", (cid,)).fetchone():
                continue
            conn.execute("DELETE FROM sa_cities WHERE id = ?", (cid,))

        for r in conn.execute("SELECT id FROM sa_regions WHERE country != 'SA'").fetchall():
            if r["id"] in keep_r:
                continue
            if conn.execute("SELECT 1 FROM sa_cities WHERE region_id = ? LIMIT 1", (r["id"],)).fetchone():
                continue
            conn.execute("DELETE FROM sa_regions WHERE id = ?", (r["id"],))

        # has_districts قد يتغير لمدينة بقيت فيها أحياء قديمة مربوطة بفنيين
        conn.execute(
            "UPDATE sa_cities SET has_districts = 1 WHERE country != 'SA' AND has_districts = 0 "
            "AND id IN (SELECT DISTINCT city_id FROM sa_districts)"
        )


def _bulk_upsert(conn, table, columns, rows, chunk_size=100):
    """مثل _bulk_insert لكن يحدّث الصف لو المعرّف (id) موجود مسبقًا."""
    if not rows:
        return
    col_list = ", ".join(columns)
    row_placeholder = "(" + ", ".join(["?"] * len(columns)) + ")"
    update_sql = ", ".join(f"{c} = excluded.{c}" for c in columns if c != "id")
    for i in range(0, len(rows), chunk_size):
        chunk = rows[i : i + chunk_size]
        values_sql = ", ".join([row_placeholder] * len(chunk))
        flat_params = [v for row in chunk for v in row]
        conn.execute(
            f"INSERT INTO {table} ({col_list}) VALUES {values_sql} "
            f"ON CONFLICT(id) DO UPDATE SET {update_sql}",
            flat_params,
        )


def backfill_professional_city_ids():
    """يربط تسجيلات الفنيين القديمة (قبل تعدد الدول، كلها سعودية) بمعرّف مدينتها
    الرسمي من اسم المدينة — حتى يطابقهم البحث الجديد (بالمعرّف) بدقة. آمن للتكرار
    بكل تشغيل: يلمس فقط الصفوف اللي city_id فيها فاضي."""
    with get_conn() as conn:
        conn.execute(
            """
            UPDATE professionals
            SET city_id = (
                SELECT c.id FROM sa_cities c
                WHERE c.name = professionals.city AND c.country = professionals.country
                ORDER BY c.has_districts DESC
                LIMIT 1
            )
            WHERE city_id IS NULL
            """
        )


def _listed_city_sql(alias: str = "") -> str:
    """المدن اللي تُعرض للاختيار: بالسعودية فقط المدن الكبرى (عندها أحياء رسمية) —
    نفس السلوك القديم؛ بباقي الدول كل المدن (أغلبها بدون أحياء = تغطية المدينة كاملة)."""
    p = f"{alias}." if alias else ""
    return f"({p}has_districts = 1 OR {p}country != 'SA')"


def list_sa_regions(country: str = "SA"):
    with get_conn() as conn:
        # السعودية: الترتيب الرسمي للمناطق (الرياض 1، مكة المكرمة 2، ... = أرقامها في البيانات الرسمية)
        order = "id" if country == "SA" else "name"
        rows = conn.execute(
            f"SELECT * FROM sa_regions WHERE country = ? ORDER BY {order}", (country,)
        ).fetchall()
        return [dict(r) for r in rows]


def get_sa_region_by_id(region_id: int):
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM sa_regions WHERE id = ?", (region_id,)).fetchone()
        return dict(row) if row else None


def list_sa_major_cities_by_region(region_id: int):
    """المدن «الكبرى» بمنطقة معيّنة (اللي عندها بيانات أحياء فعلية) — تُعرض كأزرار أولًا."""
    with get_conn() as conn:
        rows = conn.execute(
            f"SELECT * FROM sa_cities WHERE region_id = ? AND {_listed_city_sql()} ORDER BY name",
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
            f"""
            SELECT * FROM sa_cities
            WHERE region_id = ? AND {_listed_city_sql()} AND name LIKE ?
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


def _approx_dist_sq(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """مسافة إقليدية تقريبية (مربّعة) بين نقطتين، مع تصحيح خط الطول بضرب فرقه
    بجيب تمام خط العرض (cos) — بدون هذا التصحيح، درجة خط الطول تُحسب بنفس "وزن"
    درجة خط العرض رغم إنها بالكيلومترات الفعلية أقصر (خصوصًا بعيدًا عن خط
    الاستواء)، مما قد يُبعّد حيًا أقرب فعليًا شرقًا/غربًا ويقرّب حيًا أبعد.
    التصحيح يكفي لمسافات صغيرة داخل مدينة وحدة (بدون حاجة لهافرساين الدقيق)."""
    lat_km = lat1 - lat2
    lon_km = (lon1 - lon2) * math.cos(math.radians((lat1 + lat2) / 2))
    return lat_km ** 2 + lon_km ** 2


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
        return _approx_dist_sq(d["lat"], d["lon"], origin["lat"], origin["lon"])

    candidates.sort(key=dist)
    return candidates[:limit]


def find_nearest_sa_district_by_coords(city_id: int, lat: float, lon: float):
    """يرجّع أقرب حي (بنفس المدينة) لإحداثيات موقع شاركه العميل فعليًا (GPS)، بدل
    ما يختاره يدويًا من القائمة. نفس منطق المسافة الإقليدية التقريبية المستخدمة
    بـ nearest_sa_districts (كافية لمسافات صغيرة داخل مدينة وحدة)."""
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM sa_districts WHERE city_id = ? AND lat IS NOT NULL", (city_id,)
        ).fetchall()

    candidates = [dict(r) for r in rows]
    if not candidates:
        return None

    def dist(d):
        return _approx_dist_sq(d["lat"], d["lon"], lat, lon)

    candidates.sort(key=dist)
    return candidates[0]


def find_nearest_sa_city_and_district_by_coords(lat: float, lon: float, countries: list[str] | None = None):
    """يرجّع (أقرب مدينة رسمية، أقرب حي فيها أو None) لإحداثيات موقع شاركه العميل
    — يُستخدم لتحديد المدينة والحي معًا بضغطة وحدة، بدل التصفح اليدوي الكامل
    (منطقة ← مدينة ← حي). يقتصر على نفس المدن المعروضة بالاختيار اليدوي، وعلى
    الدول المفعّلة فقط (countries) لو حُددت — الموقع نفسه يحدد الدولة تلقائيًا."""
    with get_conn() as conn:
        query = f"SELECT * FROM sa_cities WHERE lat IS NOT NULL AND {_listed_city_sql()}"
        params: list = []
        if countries:
            query += f" AND country IN ({','.join('?' for _ in countries)})"
            params.extend(countries)
        rows = conn.execute(query, params).fetchall()

    candidates = [dict(r) for r in rows]
    if not candidates:
        return None

    def dist(c):
        return _approx_dist_sq(c["lat"], c["lon"], lat, lon)

    candidates.sort(key=dist)
    nearest_city = candidates[0]

    # مركز المدينة وحده يخدع بأطراف المدن الكبيرة: حي الملقا (الرياض) أقرب لمركز الدرعية
    # منه لمركز الرياض. لذا نقارن أقرب «حي» ضمن أقرب عدة مدن، ونختار مدينة ذلك الحي —
    # إلا لو مركز أقرب مدينة نفسه أقرب من أي حي (مدينة/قرية صغيرة بدون أحياء).
    best = None
    for city in candidates[:6]:
        d = find_nearest_sa_district_by_coords(city["id"], lat, lon)
        if d:
            dd = _approx_dist_sq(d["lat"], d["lon"], lat, lon)
            if best is None or dd < best[0]:
                best = (dd, city, d)
    if best and best[0] <= dist(nearest_city):
        return best[1], best[2]
    return nearest_city, find_nearest_sa_district_by_coords(nearest_city["id"], lat, lon)


def nearest_sa_cities(city_id: int, exclude_ids: list[int], limit: int = 3):
    """يرجّع أقرب N مدينة (من نفس القائمة الرسمية) بغض النظر عن المنطقة الإدارية —
    مدينة قريبة بمنطقة مجاورة أهم من مدينة بعيدة بنفس المنطقة. يُستخدم فقط لما تنتهي
    كل خيارات الأحياء المجاورة بنفس المدينة الأصلية بلا نتائج."""
    origin = get_sa_city_by_id(city_id)
    if not origin or origin["lat"] is None:
        return []

    with get_conn() as conn:
        placeholders = ",".join("?" for _ in exclude_ids) if exclude_ids else None
        # نفس الدولة فقط — ما نقترح على عميل بالكويت مدينة سعودية لأنها "أقرب".
        query = f"SELECT * FROM sa_cities WHERE lat IS NOT NULL AND country = ? AND {_listed_city_sql()}"
        params = [origin.get("country") or "SA"]
        if placeholders:
            query += f" AND id NOT IN ({placeholders})"
            params.extend(exclude_ids)
        rows = conn.execute(query, params).fetchall()

    candidates = [dict(r) for r in rows]

    def dist(c):
        return _approx_dist_sq(c["lat"], c["lon"], origin["lat"], origin["lon"])

    candidates.sort(key=dist)
    return candidates[:limit]


# ─────────────────────────── مدراء الدول (لوحة التحكم) ───────────────────────────

def list_admin_users():
    with get_conn() as conn:
        rows = conn.execute("SELECT id, username, country, created_at FROM admin_users ORDER BY country, username").fetchall()
        return [dict(r) for r in rows]


def get_admin_user_by_username(username: str):
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM admin_users WHERE username = ?", (username,)).fetchone()
        return dict(row) if row else None


def create_admin_user(username: str, password_hash: str, country: str) -> bool:
    """يرجّع False لو اسم المستخدم مستخدم مسبقًا."""
    with get_conn() as conn:
        exists = conn.execute("SELECT 1 FROM admin_users WHERE username = ?", (username,)).fetchone()
        if exists:
            return False
        conn.execute(
            "INSERT INTO admin_users (username, password_hash, country, created_at) VALUES (?, ?, ?, ?)",
            (username, password_hash, country, _now_iso()),
        )
        return True


def update_admin_user_password(user_id: int, password_hash: str):
    with get_conn() as conn:
        conn.execute("UPDATE admin_users SET password_hash = ? WHERE id = ?", (password_hash, user_id))


def delete_admin_user(user_id: int):
    with get_conn() as conn:
        conn.execute("DELETE FROM admin_users WHERE id = ?", (user_id,))


# ─────────────────────────── نشاط البوت (مربع صحة السيرفر) ───────────────────────────

def record_activity_minute(minute: str, users: int, updates: int):
    """يحفظ ملخص دقيقة وحدة (عدد المستخدمين المختلفين + عدد الرسائل/الضغطات). لو
    نفس الدقيقة انكتبت قبل (نادر — مثلًا إعادة تشغيل بنفس الدقيقة) ناخذ الأكبر."""
    with get_conn() as conn:
        conn.execute(
            """
            INSERT INTO activity_minutes (minute, users, updates) VALUES (?, ?, ?)
            ON CONFLICT(minute) DO UPDATE SET
                users = MAX(users, excluded.users), updates = MAX(updates, excluded.updates)
            """,
            (minute, users, updates),
        )
        # تنظيف تلقائي: نحتفظ بآخر 30 يوم فقط (حجم تافه، لكن ما نخليه يكبر للأبد)
        cutoff = (datetime.now(timezone.utc) - timedelta(days=30)).strftime("%Y-%m-%dT%H:%M")
        conn.execute("DELETE FROM activity_minutes WHERE minute < ?", (cutoff,))


def activity_peaks() -> dict:
    """أعلى عدد مستخدمين بنفس الدقيقة خلال آخر يوم وآخر أسبوع، + نشاط آخر ساعة."""
    now = datetime.now(timezone.utc)
    fmt = "%Y-%m-%dT%H:%M"
    day = (now - timedelta(days=1)).strftime(fmt)
    week = (now - timedelta(days=7)).strftime(fmt)
    hour = (now - timedelta(hours=1)).strftime(fmt)
    with get_conn() as conn:
        def one(sql, params):
            row = conn.execute(sql, params).fetchone()
            return (row[0] or 0) if row else 0

        return {
            "peak_day": one("SELECT MAX(users) FROM activity_minutes WHERE minute >= ?", (day,)),
            "peak_week": one("SELECT MAX(users) FROM activity_minutes WHERE minute >= ?", (week,)),
            "updates_last_hour": one("SELECT SUM(updates) FROM activity_minutes WHERE minute >= ?", (hour,)),
            "has_data": one("SELECT COUNT(*) FROM activity_minutes", ()) > 0,
        }


# ─────────────────────────── دعوة الزملاء ───────────────────────────

REFERRAL_BONUS_DEFAULT = 3


def credit_referral(new_professional_id: int):
    """يُستدعى بعد اكتمال تسجيل فني جديد: لو جاء من رابط دعوة فني ثاني، يضيف للداعي
    فرص مجانية إضافية (إعداد referral_bonus) ويرجّع (الداعي، المكافأة) لإرسال إشعار له.
    يرجّع None لو ما فيه دعوة صالحة. الحماية: ما يدعو نفسه، والداعي لازم يكون مسجّل
    وغير مرفوض، وكل حساب تلغرام ينحسب مرة وحدة فقط للأبد."""
    bonus = int(get_setting("referral_bonus", str(REFERRAL_BONUS_DEFAULT)))
    with get_conn() as conn:
        new = conn.execute(
            "SELECT id, telegram_user_id, referred_by FROM professionals WHERE id = ?", (new_professional_id,)
        ).fetchone()
        if not new or not new["referred_by"]:
            return None
        referrer = conn.execute(
            "SELECT * FROM professionals WHERE id = ?", (new["referred_by"],)
        ).fetchone()
        if (
            not referrer
            or referrer["telegram_user_id"] == new["telegram_user_id"]
            or referrer["status"] == STATUS_REJECTED
        ):
            return None
        already = conn.execute(
            "SELECT 1 FROM referral_credits WHERE referred_telegram_id = ?", (new["telegram_user_id"],)
        ).fetchone()
        if already:
            return None
        conn.execute(
            "INSERT INTO referral_credits (referred_telegram_id, referrer_id, referred_professional_id, bonus, created_at) "
            "VALUES (?, ?, ?, ?, ?)",
            (new["telegram_user_id"], referrer["id"], new["id"], bonus, _now_iso()),
        )
        if bonus > 0:
            conn.execute(
                "UPDATE professionals SET bonus_contacts = bonus_contacts + ? WHERE id = ?", (bonus, referrer["id"])
            )
        return dict(referrer), bonus


def referral_stats(professional_id: int) -> dict:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT COUNT(*) AS n, COALESCE(SUM(bonus), 0) AS b FROM referral_credits WHERE referrer_id = ?",
            (professional_id,),
        ).fetchone()
        return {"count": row["n"], "bonus": row["b"]}


def admin_top_referrers(country: str | None = None, limit: int = 10) -> list[dict]:
    with get_conn() as conn:
        rows = conn.execute(
            """
            SELECT p.id, p.full_name, p.profession_name, p.city, p.country,
                   COUNT(r.referred_telegram_id) AS invited, COALESCE(SUM(r.bonus), 0) AS bonus
            FROM referral_credits r
            JOIN professionals p ON p.id = r.referrer_id
            WHERE (? IS NULL OR p.country = ?)
            GROUP BY p.id
            ORDER BY invited DESC
            LIMIT ?
            """,
            (country, country, limit),
        ).fetchall()
        return [dict(r) for r in rows]


def profession_display(p: dict) -> str:
    """اسم المهنة للعرض — المهنتين مع بعض لو الفني عنده مهنة ثانية: «سباك • كهربائي»."""
    second = p.get("profession2_name")
    return f"{p['profession_name']} • {second}" if second else p["profession_name"]


# ─────────────────────────── كلمات البحث المكتوبة (واتساب) ───────────────────────────

def _term_norm(text: str) -> str:
    import re as _re
    t = _re.sub(r"[ً-ْـ]", "", (text or "").strip().lower())
    for a, b in (("أ", "ا"), ("إ", "ا"), ("آ", "ا"), ("ة", "ه"), ("ى", "ي")):
        t = t.replace(a, b)
    t = _re.sub(r"[^\w\s]", " ", t)
    t = _re.sub(r"^(فني|معلم|ابي|ابغى|ابغي|احتاج|اريد|ودي)\s+", "", _re.sub(r"\s+", " ", t).strip())
    return t.strip()


def log_search_term(text: str, profession_id: str | None, matched_name: str | None, source: str):
    """يحفظ الكلمة بس (بدون صاحبها). نتجاهل الحرف الواحد والأرقام والرموز."""
    try:
        term = " ".join((text or "").split())[:40]
        key = _term_norm(term)
        if len(key.replace(" ", "")) < 2 or key.replace(" ", "").isdigit():
            return
        with get_conn() as conn:
            conn.execute(
                "INSERT INTO search_terms (term, term_norm, profession_id, matched_name, source, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (term, key, profession_id, matched_name, source, _now_iso()),
            )
    except Exception:  # noqa: BLE001 — إحصائية فقط، ما توقف البوت
        pass


def get_search_terms(days: int = 30, min_count: int = 2) -> list[dict]:
    """الكلمات المكتوبة بالفترة (مرتين أو أكثر)، مجمّعة: أكثر كتابة شائعة، العدد، وش طابقت."""
    since = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
    with get_conn() as conn:
        rows = conn.execute(
            """
            SELECT t.term_norm,
                   COUNT(*) AS c,
                   (SELECT t2.term FROM search_terms t2 WHERE t2.term_norm = t.term_norm
                    GROUP BY t2.term ORDER BY COUNT(*) DESC LIMIT 1) AS term,
                   (SELECT t3.matched_name FROM search_terms t3 WHERE t3.term_norm = t.term_norm
                    AND t3.matched_name IS NOT NULL GROUP BY t3.matched_name ORDER BY COUNT(*) DESC LIMIT 1) AS matched,
                   MAX(CASE WHEN t.profession_id IS NOT NULL THEN 1 ELSE 0 END) AS exact
            FROM search_terms t
            WHERE t.created_at >= ? AND t.term_norm NOT IN (SELECT term_norm FROM search_terms_ignored)
            GROUP BY t.term_norm HAVING COUNT(*) >= ?
            ORDER BY c DESC LIMIT 200
            """,
            (since, min_count),
        ).fetchall()
        return [dict(r) for r in rows]


def ignore_search_term(term_norm: str):
    with get_conn() as conn:
        conn.execute("INSERT OR IGNORE INTO search_terms_ignored (term_norm) VALUES (?)", (term_norm,))


# ─────────────────────────── سجل إشعارات الفنيين ───────────────────────────

def log_notification(professional_id: int, kind: str, channel: str, paid: bool, ok: bool):
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO notify_log (professional_id, kind, channel, paid, ok, sent_at) VALUES (?, ?, ?, ?, ?, ?)",
            (professional_id, kind, channel, int(paid), int(ok), _now_iso()),
        )


def mark_notifications_responded(professional_id: int):
    """الفني تفاعل (ضغط اشتراك، راسل البوت، أو اشترك) — كل الإشعارات اللي قبلها انحسبت مستجابة."""
    with get_conn() as conn:
        conn.execute(
            "UPDATE notify_log SET responded_at = ? WHERE professional_id = ? AND responded_at IS NULL",
            (_now_iso(), professional_id),
        )


def notification_summary(professional_id: int) -> dict:
    with get_conn() as conn:
        r = conn.execute(
            """
            SELECT COUNT(*) AS total,
                   SUM(CASE WHEN responded_at IS NULL AND ok = 1 THEN 1 ELSE 0 END) AS unanswered,
                   SUM(paid) AS paid,
                   MAX(sent_at) AS last_sent,
                   MAX(responded_at) AS last_response
            FROM notify_log WHERE professional_id = ?
            """,
            (professional_id,),
        ).fetchone()
        return {k: (r[k] or 0) if k in ("total", "unanswered", "paid") else r[k] for k in r.keys()}


def admin_unresponsive_professionals(min_unanswered: int = 3, country: str | None = None) -> list[dict]:
    """فنيين وصلتهم إشعارات وما استجابوا — للوحة التحكم."""
    with get_conn() as conn:
        rows = conn.execute(
            """
            SELECT p.id, p.full_name, p.profession_name, p.city, p.country, p.wa_id, p.telegram_user_id,
                   p.nudge_first_at,
                   SUM(CASE WHEN n.responded_at IS NULL AND n.ok = 1 THEN 1 ELSE 0 END) AS unanswered,
                   COUNT(n.id) AS total, SUM(n.paid) AS paid, MAX(n.sent_at) AS last_sent
            FROM notify_log n JOIN professionals p ON p.id = n.professional_id
            WHERE p.is_subscribed = 0 AND (? IS NULL OR p.country = ?)
            GROUP BY p.id HAVING unanswered >= ?
            ORDER BY unanswered DESC, last_sent DESC LIMIT 100
            """,
            (country, country, min_unanswered),
        ).fetchall()
        return [dict(r) for r in rows]


def set_notify_off(professional_id: int, channel: str, off: bool):
    col = {"telegram": "tg_notify_off", "whatsapp": "wa_notify_off"}[channel]
    with get_conn() as conn:
        conn.execute(f"UPDATE professionals SET {col} = ?, notify_off_at = CASE WHEN ? THEN ? ELSE notify_off_at END "
                     "WHERE id = ?", (int(off), int(off), _now_iso(), professional_id))


def restart_wa_nudges(professional_id: int):
    """الأدمن يعيد تشغيل إشعارات واتساب من البداية (3 بالشهر الأول ثم 1 بالشهر لسنة)."""
    with get_conn() as conn:
        conn.execute("UPDATE professionals SET nudge_first_at = NULL, wa_notify_off = 0 WHERE id = ?", (professional_id,))


def count_wa_notifications_since(professional_id: int, since_iso: str, kind: str = "missed") -> int:
    with get_conn() as conn:
        return conn.execute(
            "SELECT COUNT(*) FROM notify_log WHERE professional_id = ? AND channel = 'whatsapp' AND kind = ? "
            "AND ok = 1 AND sent_at >= ?", (professional_id, kind, since_iso),
        ).fetchone()[0]


def get_professional_for_wa(wa_id: str):
    """الفني صاحب رقم الواتساب هذا: المسجّل من واتساب (wa_id)، أو المسجّل من تلغرام برقم واتساب نفسه."""
    p = get_professional_by_wa_id(wa_id)
    if p:
        return p
    with get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM professionals WHERE whatsapp_number = ? AND status != ? ORDER BY id DESC LIMIT 1",
            ("+" + wa_id.lstrip("+"), STATUS_REJECTED),
        ).fetchone()
        return dict(row) if row else None


def admin_notify_off_professionals(country: str | None = None) -> list[dict]:
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT id, full_name, profession_name, city, tg_notify_off, wa_notify_off, notify_off_at FROM professionals "
            "WHERE (tg_notify_off = 1 OR wa_notify_off = 1) AND (? IS NULL OR country = ?) ORDER BY notify_off_at DESC LIMIT 100",
            (country, country),
        ).fetchall()
        return [dict(r) for r in rows]


def admin_nudges_expired(days: int = 365, country: str | None = None) -> list[dict]:
    """فنيين غير مشتركين مرت سنة على أول إشعار واتساب لهم — الإشعارات التلقائية توقفت."""
    cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT id, full_name, profession_name, city, nudge_first_at FROM professionals "
            "WHERE is_subscribed = 0 AND nudge_first_at IS NOT NULL AND nudge_first_at < ? "
            "AND (? IS NULL OR country = ?) ORDER BY nudge_first_at LIMIT 100",
            (cutoff, country, country),
        ).fetchall()
        return [dict(r) for r in rows]


def record_missed_searches(professional_ids: list[int]):
    if not professional_ids:
        return
    now = _now_iso()
    with get_conn() as conn:
        conn.executemany("INSERT INTO missed_searches (professional_id, searched_at) VALUES (?, ?)",
                         [(pid, now) for pid in professional_ids])


def count_missed_searches(professional_id: int, since_iso: str, until_iso: str) -> int:
    with get_conn() as conn:
        return conn.execute(
            "SELECT COUNT(*) FROM missed_searches WHERE professional_id = ? AND searched_at >= ? AND searched_at < ?",
            (professional_id, since_iso, until_iso),
        ).fetchone()[0]


def summary_candidates() -> list[dict]:
    """فنيين غير مشتركين بدأت عندهم دورة إشعارات واتساب — نفحصهم للملخص الشهري."""
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM professionals WHERE is_subscribed = 0 AND status = ? AND nudge_first_at IS NOT NULL "
            "AND wa_notify_off = 0", (STATUS_ACTIVE,),
        ).fetchall()
        return [dict(r) for r in rows]


def nearest_cities_km(city_id: int, limit: int = 9) -> list[dict]:
    """أقرب N مدينة (بنفس الدولة، من المدن المعروضة) مع المسافة بالكيلو — [{id, name, km}]."""
    origin = get_sa_city_by_id(city_id) if city_id else None
    if not origin or origin.get("lat") is None:
        return []
    out = []
    for c in nearest_sa_cities(city_id, [city_id], limit):
        km = math.hypot((c["lat"] - origin["lat"]) * 111,
                        (c["lon"] - origin["lon"]) * 111 * math.cos(math.radians(origin["lat"])))
        out.append({"id": c["id"], "name": c["name"], "km": round(km)})
    return out


def nearest3_with_professionals(city_id: int, profession_id: str, n: int = 3) -> list[dict]:
    """أقرب n مدن جغرافيًا حول المدينة (بدون بحث بكل الدولة) — ويرجع منها فقط اللي فيها
    فنيين متاحين لهذي المهنة. [{id, name, km}]."""
    out = []
    for c in nearest_cities_km(city_id, n):
        if search_active_professional_ids(profession_id, c["name"], None, None, None, c["id"]):
            out.append(c)
    return out


def nearby_cities_with_professionals(city_id: int, profession_id: str, limit: int = 8) -> list[dict]:
    """أقرب المدن (بنفس الدولة) اللي فيها فنيين متاحين فعلًا لهذي المهنة — مرتبة بالمسافة.
    [{id, name, count, km}]."""
    origin = get_sa_city_by_id(city_id) if city_id else None
    if not origin or origin.get("lat") is None:
        return []
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT DISTINCT c.id, c.name, c.lat, c.lon FROM professionals p JOIN sa_cities c ON c.id = p.city_id "
            "WHERE p.status = ? AND (p.profession_id = ? OR p.profession2_id = ?) AND c.id != ? "
            "AND c.country = ? AND c.lat IS NOT NULL",
            (STATUS_ACTIVE, profession_id, profession_id, city_id, origin.get("country") or "SA"),
        ).fetchall()
    out = []
    for r in rows:
        n = len(search_active_professional_ids(profession_id, r["name"], None, None, None, r["id"]))
        if not n:
            continue
        km = math.hypot((r["lat"] - origin["lat"]) * 111,
                        (r["lon"] - origin["lon"]) * 111 * math.cos(math.radians(origin["lat"])))
        out.append({"id": r["id"], "name": r["name"], "count": n, "km": round(km)})
    out.sort(key=lambda x: x["km"])
    return out[:limit]


# ─────────────────────────── تسجيل فني على رقم آخر (المسوّقون + رمز التحقق) ───────────────────────────

def _phone_digits(phone: str) -> str:
    """أرقام دولية فقط: 0501234567 أو 501234567 أو 00966… ← 966501234567 (الافتراضي سعودي)."""
    t = (phone or "").translate(str.maketrans("٠١٢٣٤٥٦٧٨٩", "0123456789"))
    t = "".join(ch for ch in t if ch.isdigit())
    if t.startswith("00"):
        t = t[2:]
    if t.startswith("05") and len(t) == 10:
        t = "966" + t[1:]
    elif t.startswith("5") and len(t) == 9:
        t = "966" + t
    return t


def is_wa_registrar(phone: str) -> bool:
    with get_conn() as conn:
        return bool(conn.execute("SELECT 1 FROM wa_registrars WHERE phone = ?", (_phone_digits(phone),)).fetchone())


def add_wa_registrar(phone: str, name: str) -> bool:
    d = _phone_digits(phone)
    if len(d) < 9:
        return False
    with get_conn() as conn:
        conn.execute("INSERT OR REPLACE INTO wa_registrars (phone, name, created_at) VALUES (?, ?, ?)",
                     (d, (name or "").strip()[:40], _now_iso()))
    return True


def remove_wa_registrar(phone: str):
    with get_conn() as conn:
        conn.execute("DELETE FROM wa_registrars WHERE phone = ?", (_phone_digits(phone),))


def list_wa_registrars() -> list[dict]:
    """المسوّقون + كم فني سجّل كل واحد (الكل / النشطين)."""
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT r.phone, r.name, r.created_at, "
            "(SELECT COUNT(*) FROM professionals p WHERE p.registered_by = r.phone) AS total, "
            "(SELECT COUNT(*) FROM professionals p WHERE p.registered_by = r.phone AND p.status = ?) AS active "
            "FROM wa_registrars r ORDER BY total DESC, r.created_at", (STATUS_ACTIVE,)
        ).fetchall()
        return [dict(r) for r in rows]


def count_otp_since(sender: str, hours: int = 24) -> int:
    since = (datetime.now(timezone.utc) - timedelta(hours=hours)).isoformat()
    with get_conn() as conn:
        return conn.execute("SELECT COUNT(*) FROM otp_log WHERE sender = ? AND sent_at >= ?",
                            (_phone_digits(sender), since)).fetchone()[0]


def log_otp(sender: str, phone: str):
    with get_conn() as conn:
        conn.execute("INSERT INTO otp_log (sender, phone, sent_at) VALUES (?, ?, ?)",
                     (_phone_digits(sender), _phone_digits(phone), _now_iso()))


# ─────────────────────────── الفني يعدّل بياناته من واتساب (الخدمات / الأحياء / الاسم) ───────────────────────────

def update_professional_services(professional_id: int, services: list[str]):
    with get_conn() as conn:
        conn.execute("UPDATE professionals SET services_json = ? WHERE id = ?",
                     (json.dumps(services or [], ensure_ascii=False), professional_id))


def update_professional_name(professional_id: int, full_name: str):
    with get_conn() as conn:
        conn.execute("UPDATE professionals SET full_name = ? WHERE id = ?", (full_name, professional_id))


def update_professional_area(professional_id: int, country: str, city: str, city_id: int,
                             district_ids: list[int], covers_whole_city: bool):
    """يستبدل مدينة الفني وأحياءه (نفس شكل التسجيل)."""
    names = []
    for did in district_ids:
        d = get_sa_district_by_id(did)
        if d:
            names.append(d["name"])
    with get_conn() as conn:
        conn.execute(
            "UPDATE professionals SET country = ?, city = ?, city_id = ?, neighborhood = ?, covers_whole_city = ? "
            "WHERE id = ?",
            (country, city, city_id, "، ".join(names) if names else None, 1 if covers_whole_city else 0,
             professional_id))
        conn.execute("DELETE FROM professional_districts WHERE professional_id = ?", (professional_id,))
        for did in ([] if covers_whole_city else district_ids):
            conn.execute("INSERT INTO professional_districts (professional_id, district_id) VALUES (?, ?)",
                         (professional_id, did))


def set_profession2(professional_id: int, profession2_id: str | None, profession2_name: str | None,
                    services: list[str]):
    """يضيف/يغيّر/يحذف المهنة الثانية للفني (نفس مدينته وأحيائه) ويحدّث خدماته."""
    with get_conn() as conn:
        conn.execute("UPDATE professionals SET profession2_id = ?, profession2_name = ?, services_json = ? WHERE id = ?",
                     (profession2_id, profession2_name, json.dumps(services or [], ensure_ascii=False),
                      professional_id))


RECENT_RESULTS_HOURS = 24


def get_recent_results(customer_id: int, profession_id: str) -> list[int] | None:
    """نتائج آخر بحث لنفس العميل بنفس المفتاح (المهنة|المدينة) خلال 24 ساعة (أو None)."""
    since = (datetime.now(timezone.utc) - timedelta(hours=RECENT_RESULTS_HOURS)).isoformat()
    with get_conn() as conn:
        row = conn.execute(
            "SELECT ids_json FROM recent_results WHERE customer_id = ? AND profession_id = ? AND created_at >= ?",
            (customer_id, str(profession_id), since)).fetchone()
    if not row:
        return None
    try:
        ids = [int(x) for x in json.loads(row[0])]
    except Exception:
        return None
    return ids or None


def save_recent_results(customer_id: int, profession_id: str, ids: list[int]):
    if not ids:
        return
    with get_conn() as conn:
        conn.execute("INSERT OR REPLACE INTO recent_results (customer_id, profession_id, ids_json, created_at) "
                     "VALUES (?, ?, ?, ?)", (customer_id, str(profession_id), json.dumps(list(ids)), _now_iso()))


MAX_PLACES_PER_PROFESSION = 2   # طلب المالك: مكانان (حي/مدينة) فقط لنفس المهنة خلال 24 ساعة


def count_recent_places(customer_id: int, profession_id: str) -> int:
    """كم مكان مختلف (مدينة|حي) بحث فيه العميل عن نفس المهنة خلال 24 ساعة."""
    since = (datetime.now(timezone.utc) - timedelta(hours=RECENT_RESULTS_HOURS)).isoformat()
    with get_conn() as conn:
        row = conn.execute(
            "SELECT COUNT(*) FROM recent_results WHERE customer_id = ? AND substr(profession_id, 1, ?) = ? AND created_at >= ?",
            (customer_id, len(str(profession_id)) + 1, f"{profession_id}|", since)).fetchone()
    return int(row[0] or 0)


NEARBY_DISTRICTS = 5   # طلب المالك: ما فيه أحد بحيّه → أقرب 5 أحياء مجاورة، ثم المدينة كلها
RARE_IN_CITY = 5       # طلب المالك: مهنة فيها ≤5 فنيين بالمدينة = نادرة → نعرضهم مباشرة بدون سؤال الحي


def nearest_professional_ids(profession_id: str, city: str, city_id: int | None, district_id: int | None = None,
                             lat: float | None = None, lon: float | None = None) -> tuple[list[int], str]:
    """طلب المالك: ما فيه أحد بحي العميل → فنيو أقرب 5 أحياء مجاورة (الأقرب فالأقرب، وداخل الحي
    الواحد بالتناوب العادل). ما فيه أحد فيها أيضًا → المدينة كلها. يرجّع (ids, "near"|"city")."""
    near: list[dict] = []
    if district_id:
        near = nearest_sa_districts(district_id, [district_id], NEARBY_DISTRICTS)
    elif lat is not None and city_id:
        with get_conn() as conn:
            rows = [dict(r) for r in conn.execute(
                "SELECT * FROM sa_districts WHERE city_id = ? AND lat IS NOT NULL", (city_id,)).fetchall()]
        rows.sort(key=lambda d: _approx_dist_sq(d["lat"], d["lon"], lat, lon))
        near = rows[:NEARBY_DISTRICTS]
    if near:
        rank = {d["id"]: i for i, d in enumerate(near)}
        ids = search_active_professional_ids(profession_id, city, [d["name"] for d in near],
                                             [d["id"] for d in near], None, city_id)
        if ids:
            q = ",".join("?" * len(ids))
            with get_conn() as conn:
                cover: dict[int, int] = {}
                for pid, did in conn.execute(
                        f"SELECT professional_id, district_id FROM professional_districts WHERE professional_id IN ({q})",
                        ids).fetchall():
                    if did in rank:
                        cover[pid] = min(cover.get(pid, 99), rank[did])
            order = {pid: i for i, pid in enumerate(ids)}   # التناوب العادل الأصلي داخل نفس الحي
            return sorted(ids, key=lambda pid: (cover.get(pid, 0), order[pid])), "near"
    return search_active_professional_ids(profession_id, city, None, None, None, city_id), "city"


def count_in_city(profession_id: str, city: str, city_id: int | None) -> int:
    return len(search_active_professional_ids(profession_id, city, None, None, None, city_id))



# طلب المالك: اسم الفني بالحروف العربية أو الإنجليزية فقط (لا الأوردو) (مهما كانت لغة البوت) — يظهر بالعربي للعملاء ولوحة التحكم.
_NAME_MAP = str.maketrans({"ی": "ي", "ي": "ي", "ک": "ك", "ہ": "ه", "ۃ": "ة", "ە": "ه", "ھ": "ه"})


def arabic_name(text: str, min_len: int = 2, max_len: int = 40) -> str | None:
    """يرجّع الاسم منظّفًا لو كان بحروف عربية أو إنجليزية (مع التشكيل والمسافات و' - .)، وإلا None.
    طلب المالك: العربي والإنجليزي مقبولان، وحروف الأوردو الخاصة (ٹ ڈ ڑ ں ے پ گ چ …) مرفوضة.
    الحروف الأردية المطابقة شكلًا للعربية (ی ک ہ ۃ ھ) نحوّلها لنظيرتها العربية."""
    import re as _re
    name = _re.sub(r"\s+", " ", (text or "").strip()).translate(_NAME_MAP)
    if not (min_len <= len(name) <= max_len):
        return None
    if not _re.fullmatch(r"[\u0621-\u063A\u0641-\u064A\u0640\u064B-\u0652\u0670A-Za-z '\-.]+", name):
        return None
    if len(_re.sub(r"[^\u0621-\u063A\u0641-\u064AA-Za-z]", "", name)) < 2:
        return None
    return name
