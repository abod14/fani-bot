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

from flask import Flask, Response, flash, redirect, render_template, request, session, url_for

import config
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

def login_required(view):
    @functools.wraps(view)
    def wrapped(*args, **kwargs):
        if not session.get("logged_in"):
            return redirect(url_for("login", next=request.full_path))
        return view(*args, **kwargs)
    return wrapped


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username", "")
        password = request.form.get("password", "")
        if username == config.ADMIN_PANEL_USERNAME and password == config.ADMIN_PANEL_PASSWORD:
            session["logged_in"] = True
            flash("تم تسجيل الدخول بنجاح.", "success")
            next_url = request.args.get("next")
            return redirect(next_url or url_for("dashboard"))
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
    stats = db.get_admin_stats()
    return render_template("dashboard.html", stats=stats, active_page="dashboard")


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

    total_count = db.admin_count_professionals(
        status=status, city=city, profession_id=profession_id, subscribed=subscribed, query=query
    )
    total_pages = max(1, (total_count + PAGE_SIZE - 1) // PAGE_SIZE)
    page = min(page, total_pages)

    professionals = db.admin_list_professionals(
        status=status, city=city, profession_id=profession_id, subscribed=subscribed, query=query,
        limit=PAGE_SIZE, offset=(page - 1) * PAGE_SIZE,
    )

    filters = {"status": status, "city": city, "profession_id": profession_id, "subscribed": subscribed_raw, "q": query}
    filters_qs = {k: v for k, v in filters.items() if v}

    return render_template(
        "professionals.html",
        professionals=professionals,
        total_count=total_count,
        page=page,
        total_pages=total_pages,
        filters=filters,
        filters_qs=filters_qs,
        cities=db.admin_list_cities(),
        profession_options=_profession_options(),
        status_labels=db.STATUS_LABELS_AR,
        active_page="professionals",
    )


@app.route("/professionals/export.xlsx")
@login_required
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

    total_count = db.admin_count_professionals(
        status=status, city=city, profession_id=profession_id, subscribed=subscribed, query=query
    )
    professionals = db.admin_list_professionals(
        status=status, city=city, profession_id=profession_id, subscribed=subscribed, query=query,
        limit=max(total_count, 1), offset=0,
    )

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "الفنيون"
    ws.sheet_view.rightToLeft = True

    headers = [
        "الاسم", "رقم الواتساب", "رقم تواصل تيليجرام", "المهنة", "المجال",
        "المدينة", "الحي", "الحالة", "مشترك", "تاريخ انتهاء الاشتراك",
        "فرص مجانية مستخدمة", "تاريخ التسجيل",
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
            p["city"],
            p["neighborhood"] or "",
            db.STATUS_LABELS_AR.get(p["status"], p["status"]),
            "نعم" if p["is_subscribed"] else "لا",
            (p["subscription_expires_at"] or "")[:10],
            p["free_contacts_used"],
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
    p = db.get_professional_by_id(professional_id)
    if not p:
        flash("الفني غير موجود.", "error")
        return redirect(url_for("professionals_list"))
    return render_template(
        "professional_detail.html", p=p, status_labels=db.STATUS_LABELS_AR, active_page="professionals"
    )


@app.route("/professionals/<int:professional_id>/status", methods=["POST"])
@login_required
def professional_set_status(professional_id):
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
    db.admin_reset_free_contacts(professional_id)
    flash("تم تصفير عداد الفرص المجانية.", "success")
    return redirect(url_for("professional_detail", professional_id=professional_id))


@app.route("/professionals/<int:professional_id>/delete", methods=["POST"])
@login_required
def professional_delete(professional_id):
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
    summary = db.admin_coverage_summary()
    matrix_rows = db.admin_coverage_matrix()

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
        active_page="coverage",
    )


# ─────────────────────────── الاشتراكات والمدفوعات ───────────────────────────

@app.route("/payments")
@login_required
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
}


@app.route("/settings", methods=["GET", "POST"])
@login_required
def settings_page():
    if request.method == "POST":
        for key in SETTINGS_DEFAULTS:
            value = request.form.get(key)
            if value:
                db.set_setting(key, value)
        flash("تم حفظ الإعدادات — تنعكس فورًا على البوت.", "success")
        return redirect(url_for("settings_page"))

    current = {key: db.get_setting(key, default) for key, default in SETTINGS_DEFAULTS.items()}
    return render_template("settings.html", settings=current, active_page="settings")


# ─────────────────────────── إدارة المهن والمجالات ───────────────────────────

@app.route("/professions")
@login_required
def professions_page():
    return render_template("professions.html", domains=_profession_options(), active_page="professions")


@app.route("/professions/domains/add", methods=["POST"])
@login_required
def domain_add():
    name = request.form.get("name", "").strip()
    if name:
        db.create_domain(name)
        flash("تمت إضافة المجال.", "success")
    return redirect(url_for("professions_page"))


@app.route("/professions/domains/<domain_id>/rename", methods=["POST"])
@login_required
def domain_rename(domain_id):
    name = request.form.get("name", "").strip()
    if name:
        db.rename_domain(domain_id, name)
        flash("تم تعديل اسم المجال.", "success")
    return redirect(url_for("professions_page"))


@app.route("/professions/domains/<domain_id>/delete", methods=["POST"])
@login_required
def domain_delete(domain_id):
    if db.delete_domain(domain_id):
        flash("تم حذف المجال.", "success")
    else:
        flash("لا يمكن حذف مجال يحتوي على مهن — احذف/انقل مهنه أولًا.", "error")
    return redirect(url_for("professions_page"))


def _parse_services(raw: str) -> list:
    return [s.strip() for s in raw.split("،" if "،" in raw else ",") if s.strip()]


@app.route("/professions/domains/<domain_id>/professions/add", methods=["POST"])
@login_required
def profession_add(domain_id):
    name = request.form.get("name", "").strip()
    isco_code = request.form.get("isco_code", "").strip() or None
    services = _parse_services(request.form.get("services", ""))
    if name:
        db.create_profession(domain_id, name, isco_code, services)
        flash("تمت إضافة المهنة.", "success")
    return redirect(url_for("professions_page"))


@app.route("/professions/<profession_id>/edit", methods=["GET", "POST"])
@login_required
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
@login_required
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
