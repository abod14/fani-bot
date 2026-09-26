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

from flask import Flask, flash, redirect, render_template, request, session, url_for

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
        if name:
            db.update_profession(profession_id, name, isco_code, services)
            flash("تم حفظ تعديلات المهنة.", "success")
            return redirect(url_for("professions_page"))
        flash("اسم المهنة مطلوب.", "error")

    import json as _json
    prof_view = {
        "id": prof["id"],
        "name": prof["name"],
        "isco_code": prof.get("isco_code"),
        "services": _json.loads(prof["services_json"]) if prof.get("services_json") else [],
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
    app.run(host="127.0.0.1", port=5050, debug=False)
