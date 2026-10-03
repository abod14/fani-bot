# لوحة تحكم بوت «فني» — صفحة ويب بسيطة (Flask) بكلمة مرور، تقرأ/تكتب نفس قاعدة
# بيانات SQLite اللي يستخدمها البوت مباشرة، بدون أي طبقة تزامن إضافية.
#
# التشغيل: python admin_panel/app.py  (بعد ضبط ADMIN_PANEL_USERNAME/ADMIN_PANEL_PASSWORD بملف .env)

import functools
import secrets
import sys
from pathlib import Path

# نضيف مجلد المشروع الرئيسي (اللي فيه db.py و config.py) لمسار البحث، لأن هذا الملف
# داخل مجلد فرعي (admin_panel/).
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import io
import os
import shutil

from flask import Flask, Response, abort, flash, redirect, render_template, request, session, url_for
from werkzeug.security import check_password_hash, generate_password_hash

import config
import countries
import db
import professions_repo

if not config.ADMIN_PANEL_PASSWORD:
    raise RuntimeError(
        "ADMIN_PANEL_PASSWORD غير موجود. أضف بملف .env:\n"
        "  ADMIN_PANEL_USERNAME=admin\n"
        "  ADMIN_PANEL_PASSWORD=كلمة_مرور_قوية_تختارها\n"
        "بدون كلمة مرور، أي شخص يعرف رابط اللوحة يقدر يدخلها — لذا نرفض التشغيل."
    )

app = Flask(__name__)
app.secret_key = config.ADMIN_PANEL_SECRET_KEY or secrets.token_hex(32)

PAGE_SIZE = 20

db.init_db()
db.seed_professions_from_json_if_empty(config.PROFESSIONS_JSON_PATH)
db.seed_saudi_geo_if_empty(
    config.SAUDI_REGIONS_JSON_PATH, config.SAUDI_CITIES_JSON_PATH, config.SAUDI_DISTRICTS_JSON_PATH
)


# ─────────────────────────── تسجيل الدخول ───────────────────────────

# صلاحيتان:
#   super   — المدير العام (بيانات الدخول من ملف .env): كل شي.
#   country — مدير دولة (يُضاف من صفحة «المدراء»): يشوف ويدير فنيي دولته فقط، بدون
#             تنزيل إكسل، ولا إعدادات عامة، ولا تعديل المهن، ولا المدفوعات، ولا المدراء.

def login_required(view):
    @functools.wraps(view)
    def wrapped(*args, **kwargs):
        if not session.get("logged_in"):
            return redirect(url_for("login", next=request.full_path))
        return view(*args, **kwargs)
    return wrapped


def is_super() -> bool:
    return session.get("role", "super") == "super"


def super_required(view):
    """صفحات للمدير العام فقط — مدير الدولة يرجع للرئيسية مع تنبيه."""
    @functools.wraps(view)
    @login_required
    def wrapped(*args, **kwargs):
        if not is_super():
            flash("هذي الصفحة متاحة للمدير العام فقط.", "error")
            return redirect(url_for("dashboard"))
        return view(*args, **kwargs)
    return wrapped


def scope_country() -> str | None:
    """الدولة اللي تنحصر فيها البيانات: مدير الدولة دائمًا دولته (ما يقدر يغيّرها)،
    والمدير العام حسب فلتر ?country= (فاضي = كل الدول)."""
    if not is_super():
        return session.get("country")
    code = (request.args.get("country") or "").upper()
    return code if countries.get(code) else None


def _professional_or_404(professional_id: int):
    """يجيب الفني ويتأكد إن المستخدم الحالي له صلاحية عليه (مدير الدولة: دولته فقط)."""
    p = db.get_professional_by_id(professional_id)
    if not p:
        return None
    if not is_super() and (p.get("country") or "SA") != session.get("country"):
        abort(403)
    return p


@app.context_processor
def inject_role():
    return {
        "is_super": is_super() if session.get("logged_in") else False,
        "manager_country": session.get("country"),
        "country_label": countries.label,
        "all_countries": countries.COUNTRIES,
    }


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        next_url = request.args.get("next")
        if username == config.ADMIN_PANEL_USERNAME and password == config.ADMIN_PANEL_PASSWORD:
            session.clear()
            session["logged_in"] = True
            session["role"] = "super"
            flash("تم تسجيل الدخول بنجاح.", "success")
            return redirect(next_url or url_for("dashboard"))
        manager = db.get_admin_user_by_username(username)
        if manager and check_password_hash(manager["password_hash"], password):
            session.clear()
            session["logged_in"] = True
            session["role"] = "country"
            session["country"] = manager["country"]
            session["username"] = manager["username"]
            flash(f"أهلًا {manager['username']} — مدير {countries.label(manager['country'])}.", "success")
            return redirect(url_for("dashboard"))
        flash("اسم المستخدم أو كلمة المرور غير صحيحة.", "error")
    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    flash("تم تسجيل الخروج.", "success")
    return redirect(url_for("login"))


# ─────────────────────────── الرئيسية / الإحصائيات ───────────────────────────

@app.route("/")
@login_required
def dashboard():
    country = scope_country()
    stats = db.get_admin_stats(country=country)
    health = _server_health() if is_super() else None
    return render_template(
        "dashboard.html", stats=stats, health=health, selected_country=country,
        top_referrers=db.admin_top_referrers(country), active_page="dashboard",
    )


# ─────────────────────────── صحة السيرفر (للمدير العام) ───────────────────────────
# حدود الألوان: أخضر = مرتاح، أصفر = قربت (خطط للترقية)، أحمر = رقّ الآن.
PEAK_USERS_YELLOW, PEAK_USERS_RED = 30, 50       # مستخدمين بنفس الدقيقة
RAM_YELLOW, RAM_RED = 75, 90                      # ٪ ذاكرة مستخدمة
DISK_YELLOW, DISK_RED = 80, 90                    # ٪ مساحة مستخدمة
CPU_YELLOW, CPU_RED = 0.7, 1.0                    # متوسط الحمل لكل نواة
DB_YELLOW_MB, DB_RED_MB = 2048, 5120              # حجم قاعدة البيانات

_LEVEL_ORDER = {"green": 0, "yellow": 1, "red": 2}


def _level(value, yellow, red) -> str:
    if value is None:
        return "green"
    return "red" if value >= red else ("yellow" if value >= yellow else "green")


def _server_health() -> dict:
    items = []

    # الحمل على المعالج (متوسط آخر 5 دقائق ÷ عدد الأنوية)
    try:
        load5 = os.getloadavg()[1]
        cores = os.cpu_count() or 1
        per_core = load5 / cores
        items.append({"label": "المعالج (CPU)", "value": f"{per_core * 100:.0f}٪ (أنوية: {cores})",
                      "level": _level(per_core, CPU_YELLOW, CPU_RED)})
    except (OSError, AttributeError):
        pass

    # الذاكرة (من /proc/meminfo — بدون أي مكتبة إضافية)
    try:
        info = {}
        with open("/proc/meminfo", encoding="utf-8") as f:
            for line in f:
                k, v = line.split(":", 1)
                info[k] = int(v.strip().split()[0])  # kB
        total, avail = info["MemTotal"], info.get("MemAvailable", info.get("MemFree", 0))
        used_pct = (total - avail) * 100 / total
        items.append({"label": "الذاكرة (RAM)", "value": f"{used_pct:.0f}٪ من {total / 1024 / 1024:.1f} GB",
                      "level": _level(used_pct, RAM_YELLOW, RAM_RED)})
    except (OSError, KeyError, ValueError, ZeroDivisionError):
        pass

    # المساحة
    try:
        du = shutil.disk_usage(str(config.DB_PATH.parent))
        disk_pct = du.used * 100 / du.total
        items.append({"label": "المساحة (Disk)", "value": f"{disk_pct:.0f}٪ من {du.total / 1024 ** 3:.0f} GB",
                      "level": _level(disk_pct, DISK_YELLOW, DISK_RED)})
    except OSError:
        pass

    # حجم قاعدة البيانات
    try:
        size_mb = sum(
            os.path.getsize(f"{config.DB_PATH}{suffix}")
            for suffix in ("", "-wal") if os.path.exists(f"{config.DB_PATH}{suffix}")
        ) / 1024 / 1024
        items.append({"label": "حجم قاعدة البيانات", "value": f"{size_mb:.1f} MB",
                      "level": _level(size_mb, DB_YELLOW_MB, DB_RED_MB)})
    except OSError:
        pass

    peaks = db.activity_peaks()
    items.append({"label": "أعلى مستخدمين بنفس الدقيقة (آخر يوم)", "value": str(peaks["peak_day"]),
                  "level": _level(peaks["peak_day"], PEAK_USERS_YELLOW, PEAK_USERS_RED)})
    items.append({"label": "أعلى مستخدمين بنفس الدقيقة (آخر أسبوع)", "value": str(peaks["peak_week"]),
                  "level": _level(peaks["peak_week"], PEAK_USERS_YELLOW, PEAK_USERS_RED)})
    items.append({"label": "رسائل وضغطات آخر ساعة", "value": str(peaks["updates_last_hour"]), "level": "green"})

    overall = max((i["level"] for i in items), key=lambda lv: _LEVEL_ORDER[lv], default="green")
    return {"items": items, "overall": overall, "has_activity": peaks["has_data"]}


# ─────────────────────────── الفنيون ───────────────────────────

def _profession_options():
    """قائمة المجالات مع مهنها، لخيارات الفلترة بصفحة الفنيون."""
    domains = []
    for d in professions_repo.get_domains():
        domains.append({"id": d["id"], "name": d["name"], "professions": professions_repo.get_professions_by_domain(d["id"])})
    return domains


@app.route("/professionals")
@login_required
def professionals_list():
    status = request.args.get("status") or None
    city = request.args.get("city") or None
    profession_id = request.args.get("profession_id") or None
    subscribed_raw = request.args.get("subscribed") or None
    query = request.args.get("q") or None
    page = max(1, request.args.get("page", 1, type=int))

    subscribed = None
    if subscribed_raw == "yes":
        subscribed = True
    elif subscribed_raw == "no":
        subscribed = False

    country = scope_country()
    total_count = db.admin_count_professionals(
        status=status, city=city, profession_id=profession_id, subscribed=subscribed, query=query,
        country=country,
    )
    total_pages = max(1, (total_count + PAGE_SIZE - 1) // PAGE_SIZE)
    page = min(page, total_pages)

    professionals = db.admin_list_professionals(
        status=status, city=city, profession_id=profession_id, subscribed=subscribed, query=query,
        country=country, limit=PAGE_SIZE, offset=(page - 1) * PAGE_SIZE,
    )

    filters = {
        "status": status, "city": city, "profession_id": profession_id, "subscribed": subscribed_raw, "q": query,
        "country": country if is_super() else None,
    }
    filters_qs = {k: v for k, v in filters.items() if v}

    return render_template(
        "professionals.html",
        professionals=professionals,
        total_count=total_count,
        page=page,
        total_pages=total_pages,
        filters=filters,
        filters_qs=filters_qs,
        cities=db.admin_list_cities(country),
        profession_options=_profession_options(),
        status_labels=db.STATUS_LABELS_AR,
        active_page="professionals",
    )


@app.route("/professionals/export.xlsx")
@super_required
def professionals_export():
    """تنزيل قائمة الفنيين (بنفس فلاتر صفحة الفنيون الحالية إن وُجدت) كملف إكسل."""
    try:
        import openpyxl
        from openpyxl.styles import Alignment, Font
    except ImportError:
        flash("ميزة التصدير تحتاج مكتبة openpyxl غير مثبتة على السيرفر — شغّل: pip install openpyxl", "error")
        return redirect(url_for("professionals_list"))

    status = request.args.get("status") or None
    city = request.args.get("city") or None
    profession_id = request.args.get("profession_id") or None
    subscribed_raw = request.args.get("subscribed") or None
    query = request.args.get("q") or None

    subscribed = None
    if subscribed_raw == "yes":
        subscribed = True
    elif subscribed_raw == "no":
        subscribed = False

    country = scope_country()
    total_count = db.admin_count_professionals(
        status=status, city=city, profession_id=profession_id, subscribed=subscribed, query=query,
        country=country,
    )
    professionals = db.admin_list_professionals(
        status=status, city=city, profession_id=profession_id, subscribed=subscribed, query=query,
        country=country, limit=max(total_count, 1), offset=0,
    )

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "الفنيون"
    ws.sheet_view.rightToLeft = True

    headers = [
        "الاسم", "رقم الواتساب", "رقم تواصل تيليجرام", "المهنة", "المجال",
        "الدولة", "المدينة", "الحي", "الحالة", "مشترك", "تاريخ انتهاء الاشتراك",
        "فرص مجانية مستخدمة", "مصدر التسجيل", "تاريخ التسجيل",
    ]
    ws.append(headers)
    for cell in ws[1]:
        cell.font = Font(bold=True)
        cell.alignment = Alignment(horizontal="center")

    for p in professionals:
        ws.append([
            p["full_name"],
            p["whatsapp_number"],
            p["telegram_contact_number"] or "",
            p["profession_name"],
            p["domain_name"],
            countries.name(p.get("country") or "SA"),
            p["city"],
            "المدينة كاملة" if p.get("covers_whole_city") else (p["neighborhood"] or ""),
            db.STATUS_LABELS_AR.get(p["status"], p["status"]),
            "نعم" if p["is_subscribed"] else "لا",
            (p["subscription_expires_at"] or "")[:10],
            p["free_contacts_used"],
            p.get("source") or "unknown",
            (p["created_at"] or "")[:16],
        ])

    for col in ws.columns:
        max_len = max((len(str(c.value)) for c in col if c.value is not None), default=10)
        ws.column_dimensions[col[0].column_letter].width = min(max_len + 2, 40)

    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)

    # ملاحظة مهمة: اسم ملف بحروف عربية في Content-Disposition العادي (filename=...)
    # يكسر الترويسة (HTTP headers لازم تكون ASCII/latin-1) ويسبب خطأ 500 بدل ما
    # ينزل الملف — لازم نستخدم الصيغة المشفّرة filename*=UTF-8''... مع اسم احتياطي
    # إنجليزي بسيط بالصيغة العادية لأي متصفح قديم ما يفهم الصيغة الجديدة.
    from urllib.parse import quote

    encoded_name = quote("الفنيون.xlsx")
    return Response(
        buf.getvalue(),
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={
            "Content-Disposition": f"attachment; filename=professionals.xlsx; filename*=UTF-8''{encoded_name}"
        },
    )


@app.route("/professionals/<int:professional_id>")
@login_required
def professional_detail(professional_id):
    p = _professional_or_404(professional_id)
    if not p:
        flash("الفني غير موجود.", "error")
        return redirect(url_for("professionals_list"))
    return render_template(
        "professional_detail.html", p=p, status_labels=db.STATUS_LABELS_AR, active_page="professionals"
    )


@app.route("/professionals/<int:professional_id>/status", methods=["POST"])
@login_required
def professional_set_status(professional_id):
    if not _professional_or_404(professional_id):
        flash("الفني غير موجود.", "error")
        return redirect(url_for("professionals_list"))
    new_status = request.form.get("status")
    if new_status not in (db.STATUS_PENDING, db.STATUS_ACTIVE, db.STATUS_REJECTED):
        flash("حالة غير معروفة.", "error")
    else:
        db.set_status(professional_id, new_status)
        flash("تم تحديث حالة الفني.", "success")
    next_url = request.form.get("next")
    return redirect(next_url or url_for("professional_detail", professional_id=professional_id))


@app.route("/professionals/<int:professional_id>/edit", methods=["POST"])
@login_required
def professional_edit(professional_id):
    if not _professional_or_404(professional_id):
        flash("الفني غير موجود.", "error")
        return redirect(url_for("professionals_list"))
    db.admin_update_professional(
        professional_id,
        full_name=request.form.get("full_name") or None,
        city=request.form.get("city") or None,
        neighborhood=request.form.get("neighborhood") or "",
        whatsapp_number=request.form.get("whatsapp_number") or None,
        telegram_contact_number=request.form.get("telegram_contact_number") or "",
        has_whatsapp=request.form.get("has_whatsapp") == "1",
    )
    flash("تم حفظ بيانات الفني.", "success")
    return redirect(url_for("professional_detail", professional_id=professional_id))


@app.route("/professionals/<int:professional_id>/subscription", methods=["POST"])
@login_required
def professional_subscription(professional_id):
    if not _professional_or_404(professional_id):
        flash("الفني غير موجود.", "error")
        return redirect(url_for("professionals_list"))
    action = request.form.get("action")
    expires_at = request.form.get("expires_at") or None
    if action == "activate":
        db.admin_set_subscription(professional_id, True, expires_at)
        flash("تم تفعيل الاشتراك يدويًا.", "success")
    elif action == "deactivate":
        db.admin_set_subscription(professional_id, False, None)
        flash("تم إلغاء الاشتراك.", "success")
    return redirect(url_for("professional_detail", professional_id=professional_id))


@app.route("/professionals/<int:professional_id>/reset-free-contacts", methods=["POST"])
@login_required
def professional_reset_free(professional_id):
    if not _professional_or_404(professional_id):
        flash("الفني غير موجود.", "error")
        return redirect(url_for("professionals_list"))
    db.admin_reset_free_contacts(professional_id)
    flash("تم تصفير عداد الفرص المجانية.", "success")
    return redirect(url_for("professional_detail", professional_id=professional_id))


@app.route("/professionals/<int:professional_id>/delete", methods=["POST"])
@login_required
def professional_delete(professional_id):
    if not _professional_or_404(professional_id):
        flash("الفني غير موجود.", "error")
        return redirect(url_for("professionals_list"))
    db.admin_delete_professional(professional_id)
    flash("تم حذف الفني نهائيًا.", "success")
    return redirect(url_for("professionals_list"))


# ─────────────────────────── مؤشرات التغطية (جاهزية الإطلاق) ───────────────────────────

# أي مدينة فيها "عدد كافٍ" من الفنيين لمهنة معينة تُعتبر مغطّاة بهالمهنة — حد أدنى
# بسيط قابل للتعديل لاحقًا حسب الحاجة الفعلية.
COVERAGE_READY_THRESHOLD = 3


@app.route("/coverage")
@login_required
def coverage_page():
    # مدن الدول المختلفة ممكن تتشابه أسماؤها، فالتغطية دائمًا لدولة وحدة (الافتراضي السعودية)
    country = scope_country() or countries.DEFAULT_COUNTRY
    summary = db.admin_coverage_summary(country)
    matrix_rows = db.admin_coverage_matrix(country)

    # counts[profession_id][city] = عدد الفنيين النشطين
    counts: dict[str, dict[str, int]] = {}
    for r in matrix_rows:
        counts.setdefault(r["profession_id"], {})[r["city"]] = r["cnt"]

    domains = []
    total_professions = 0
    for d in professions_repo.get_domains():
        profs = professions_repo.get_professions_by_domain(d["id"])
        domains.append({"id": d["id"], "name": d["name"], "professions": profs})
        total_professions += len(profs)

    # عدد المهن "الجاهزة" (وصلت الحد الأدنى) لكل مدينة — لحساب نسبة الجاهزية
    cities = [row["city"] for row in summary]
    ready_counts = {city: 0 for city in cities}
    for prof_counts in counts.values():
        for city, cnt in prof_counts.items():
            if city in ready_counts and cnt >= COVERAGE_READY_THRESHOLD:
                ready_counts[city] += 1

    return render_template(
        "coverage.html",
        summary=summary,
        cities=cities,
        counts=counts,
        domains=domains,
        total_professions=total_professions,
        ready_counts=ready_counts,
        ready_threshold=COVERAGE_READY_THRESHOLD,
        selected_country=country,
        active_page="coverage",
    )


# ─────────────────────────── الاشتراكات والمدفوعات ───────────────────────────

@app.route("/payments")
@super_required
def payments_list():
    status = request.args.get("status") or None
    method = request.args.get("method") or None
    page = max(1, request.args.get("page", 1, type=int))

    total_count = db.admin_count_payments(status=status, method=method)
    total_pages = max(1, (total_count + PAGE_SIZE - 1) // PAGE_SIZE)
    page = min(page, total_pages)

    payments = db.admin_list_payments(status=status, method=method, limit=PAGE_SIZE, offset=(page - 1) * PAGE_SIZE)

    filters = {"status": status, "method": method}
    filters_qs = {k: v for k, v in filters.items() if v}

    return render_template(
        "payments.html",
        payments=payments,
        total_count=total_count,
        page=page,
        total_pages=total_pages,
        filters=filters,
        filters_qs=filters_qs,
        active_page="payments",
    )


# ─────────────────────────── الإعدادات العامة ───────────────────────────

SETTINGS_DEFAULTS = {
    "subscription_price_sar": str(config.SUBSCRIPTION_PRICE_SAR),
    "subscription_price_stars": str(config.SUBSCRIPTION_PRICE_STARS),
    "subscription_days": str(config.SUBSCRIPTION_DAYS),
    "free_contacts_limit": str(db.FREE_CONTACTS_LIMIT),
    "referral_bonus": str(db.REFERRAL_BONUS_DEFAULT),
}


@app.route("/settings", methods=["GET", "POST"])
@super_required
def settings_page():
    if request.method == "POST":
        for key in SETTINGS_DEFAULTS:
            value = request.form.get(key)
            if value:
                db.set_setting(key, value)
        enabled = [code for code in countries.ALL_CODES if request.form.get(f"country_{code}") == "1"]
        if countries.DEFAULT_COUNTRY not in enabled:
            enabled.insert(0, countries.DEFAULT_COUNTRY)
        db.set_setting("enabled_countries", ",".join(enabled))
        flash("تم حفظ الإعدادات — تنعكس فورًا على البوت.", "success")
        return redirect(url_for("settings_page"))

    current = {key: db.get_setting(key, default) for key, default in SETTINGS_DEFAULTS.items()}
    return render_template(
        "settings.html", settings=current, enabled_countries=countries.enabled_codes(), active_page="settings"
    )


# ─────────────────────────── مدراء الدول ───────────────────────────

@app.route("/admins", methods=["GET", "POST"])
@super_required
def admins_page():
    if request.method == "POST":
        action = request.form.get("action")
        if action == "add":
            username = request.form.get("username", "").strip()
            password = request.form.get("password", "")
            country = (request.form.get("country") or "").upper()
            if not username or len(password) < 6 or not countries.get(country):
                flash("اكتب اسم مستخدم، وكلمة مرور 6 أحرف على الأقل، واختر الدولة.", "error")
            elif username == config.ADMIN_PANEL_USERNAME:
                flash("هذا الاسم محجوز للمدير العام — اختر اسم ثاني.", "error")
            elif db.create_admin_user(username, generate_password_hash(password), country):
                flash(f"تمت إضافة المدير «{username}» لـ {countries.label(country)}.", "success")
            else:
                flash("اسم المستخدم مستخدم مسبقًا.", "error")
        elif action == "password":
            password = request.form.get("password", "")
            if len(password) < 6:
                flash("كلمة المرور لازم تكون 6 أحرف على الأقل.", "error")
            else:
                db.update_admin_user_password(int(request.form["user_id"]), generate_password_hash(password))
                flash("تم تغيير كلمة المرور.", "success")
        elif action == "delete":
            db.delete_admin_user(int(request.form["user_id"]))
            flash("تم حذف المدير.", "success")
        return redirect(url_for("admins_page"))

    return render_template("admins.html", admins=db.list_admin_users(), active_page="admins")


# ─────────────────────────── إدارة المهن والمجالات ───────────────────────────

@app.route("/professions")
@super_required
def professions_page():
    return render_template("professions.html", domains=_profession_options(), active_page="professions")


@app.route("/professions/domains/add", methods=["POST"])
@super_required
def domain_add():
    name = request.form.get("name", "").strip()
    if name:
        db.create_domain(name)
        flash("تمت إضافة المجال.", "success")
    return redirect(url_for("professions_page"))


@app.route("/professions/domains/<domain_id>/rename", methods=["POST"])
@super_required
def domain_rename(domain_id):
    name = request.form.get("name", "").strip()
    if name:
        db.rename_domain(domain_id, name)
        flash("تم تعديل اسم المجال.", "success")
    return redirect(url_for("professions_page"))


@app.route("/professions/domains/<domain_id>/delete", methods=["POST"])
@super_required
def domain_delete(domain_id):
    if db.delete_domain(domain_id):
        flash("تم حذف المجال.", "success")
    else:
        flash("لا يمكن حذف مجال يحتوي على مهن — احذف/انقل مهنه أولًا.", "error")
    return redirect(url_for("professions_page"))


def _parse_services(raw: str) -> list:
    return [s.strip() for s in raw.split("،" if "،" in raw else ",") if s.strip()]


@app.route("/professions/domains/<domain_id>/professions/add", methods=["POST"])
@super_required
def profession_add(domain_id):
    name = request.form.get("name", "").strip()
    isco_code = request.form.get("isco_code", "").strip() or None
    services = _parse_services(request.form.get("services", ""))
    if name:
        db.create_profession(domain_id, name, isco_code, services)
        flash("تمت إضافة المهنة.", "success")
    return redirect(url_for("professions_page"))


@app.route("/professions/<profession_id>/edit", methods=["GET", "POST"])
@super_required
def profession_edit_page(profession_id):
    prof = db.get_profession_by_id(profession_id)
    if not prof:
        flash("المهنة غير موجودة.", "error")
        return redirect(url_for("professions_page"))

    if request.method == "POST":
        name = request.form.get("name", "").strip()
        isco_code = request.form.get("isco_code", "").strip() or None
        services = _parse_services(request.form.get("services", ""))
        allow_city_wide = request.form.get("allow_city_wide") == "1"
        if name:
            db.update_profession(profession_id, name, isco_code, services, allow_city_wide=allow_city_wide)
            flash("تم حفظ تعديلات المهنة.", "success")
            return redirect(url_for("professions_page"))
        flash("اسم المهنة مطلوب.", "error")

    import json as _json
    prof_view = {
        "id": prof["id"],
        "name": prof["name"],
        "isco_code": prof.get("isco_code"),
        "services": _json.loads(prof["services_json"]) if prof.get("services_json") else [],
        "allow_city_wide": bool(prof.get("allow_city_wide")),
    }
    return render_template("profession_edit.html", profession=prof_view, active_page="professions")


@app.route("/professions/<profession_id>/delete", methods=["POST"])
@super_required
def profession_delete(profession_id):
    if db.delete_profession(profession_id):
        flash("تم حذف المهنة.", "success")
    else:
        flash("لا يمكن حذف مهنة مرتبط بها فنيون مسجّلون حاليًا.", "error")
    return redirect(url_for("professions_page"))


if __name__ == "__main__":
    import os as _os

    # الافتراضي 127.0.0.1 (محلي فقط، للتطوير) — على السيرفر نضبط ADMIN_PANEL_HOST=0.0.0.0
    # عبر متغير بيئة (systemd Environment=) حتى يكون الرابط قابل للفتح من المتصفح مباشرة.
    host = _os.environ.get("ADMIN_PANEL_HOST", "127.0.0.1")
    port = int(_os.environ.get("ADMIN_PANEL_PORT", "5050"))
    app.run(host=host, port=port, debug=False)
