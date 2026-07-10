import secrets
from datetime import date, datetime

from flask import Flask, render_template, redirect, url_for, request, flash
from flask_login import LoginManager, login_required, current_user
from sqlalchemy import func

import config
from models import db, Activity, Target, User, ServiceArea, calc_quarter, calc_fiscal_year
from forms import ActivityForm, TargetForm
from auth import auth_bp, admin_required
from extensions import mail

login_manager = LoginManager()
login_manager.login_view = "auth.login"
login_manager.login_message = "Please log in to continue."
login_manager.login_message_category = "info"



@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


def create_app():
    app = Flask(__name__)
    app.config.from_object(config.Config)

    db.init_app(app)
    login_manager.init_app(app)
    mail.init_app(app)
    app.register_blueprint(auth_bp)

    with app.app_context():
        db.create_all()
        _ensure_user_columns()
        _seed_if_empty()
        _seed_default_admin()
        _seed_service_areas_if_empty()

    register_routes(app)
    return app

def _ensure_user_columns():
    """
    Safety net: db.create_all() only creates NEW tables, it never adds
    columns to a table that already exists. This adds any columns the
    User model needs but the live database is still missing, so old
    deployments upgrade themselves automatically without losing data.
    """
    from sqlalchemy import text
    statements = [
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS position VARCHAR(120)",
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS department VARCHAR(120)",
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS otp_code VARCHAR(6)",
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS otp_expires_at TIMESTAMP",
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS email_verified BOOLEAN DEFAULT FALSE",
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS contact_phone VARCHAR(30)",
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS id_no VARCHAR(50)",
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS segment VARCHAR(120)",
    ]
    with db.engine.connect() as conn:
        for stmt in statements:
            try:
                conn.execute(text(stmt))
            except Exception as e:
                print(f"Column migration skipped/failed: {e}")
        conn.commit()

def _seed_default_admin():
    existing_admin = User.query.filter_by(role="admin").first()
    if existing_admin:
        return

    default_password = "Mimi7957@"

    admin = User(
        full_name="Administrator",
        email="ulfatazawude79@gmail.com",
        role="admin",
        is_approved=True,
        email_verified=True,
    )
    admin.set_password(default_password)

    db.session.add(admin)
    db.session.commit()

    print("=" * 70)
    print("Default admin created")
    print("Email: ulfatazawude79@gmail.com")
    print(f"Password: {default_password}")
    print("=" * 70)
def _seed_service_areas_if_empty():
    if ServiceArea.query.first() is not None:
        return
    for i, name in enumerate(config.SERVICE_AREAS):
        db.session.add(ServiceArea(name=name, is_active=True, sort_order=i))
    db.session.commit()
# ---------------------------------------------------------------------------
# Seed the database with the sample rows that were already in the workbook,
# the first time the app runs against an empty database.
# ---------------------------------------------------------------------------
def _seed_if_empty():
    if Activity.query.first() is not None:
        return

    sample_rows = [
        dict(date=date(2026, 7, 1), service_area="Partnership Development",
             specific_activity="Initial meeting with UNDP Ethiopia",
             description="Discussed potential partnership on rural SME financing programme; agreed to draft a concept note.",
             where_location="Coop Bank Head Office",
             whom="Mr. Dawit Alemu (UNDP), Ms. Sara Tesfaye (Coop Bank)",
             engagement_type="Meeting",
             doc_link="https://drive.example.com/undp-meeting-minutes-01jun2026",
             result_outcome="Agreement in principle to collaborate; UNDP to share concept template",
             financial_result=0,
             future_plan="Draft and share concept note by 15 Jun 2026",
             status="Completed",
             responsible_org="Coop Bank (Sara Tesfaye)",
             remarks="Follow-up email sent"),
        dict(date=date(2026, 7, 2), service_area="Proposal Development and Resource Mobilization",
             specific_activity="GCF funding proposal - budget section",
             description="Prepared budget section of proposal for Green Climate Fund submission.",
             where_location="Coop Bank Head Office",
             whom="N/A (desk work)",
             engagement_type="Office Work / Desk Task",
             doc_link="https://drive.example.com/gcf-proposal-budget-v2",
             result_outcome="Budget section completed and shared with team for review",
             financial_result=0,
             future_plan="Incorporate reviewer comments and finalize by end of month",
             status="Ongoing",
             responsible_org="Coop Bank (Sara Tesfaye)",
             remarks=""),
        dict(date=date(2026, 7, 3), service_area="Training and Capacity Building",
             specific_activity="ToT for branch SME officers",
             description="Delivered training of trainers for 25 branch SME officers on green financing products.",
             where_location="Branch Office",
             whom="25 SME officers; facilitated by Sara Tesfaye and Abel Getachew",
             engagement_type="Workshop / Training",
             doc_link="https://drive.example.com/tot-report-adama-jun2026",
             result_outcome="25 officers certified; post-training assessment average score 87%",
             financial_result=0,
             future_plan="Roll out same training to Hawassa and Bahir Dar branches",
             status="Completed",
             responsible_org="Coop Bank (Abel Getachew)",
             remarks=""),
        dict(date=date(2026, 7, 4), service_area="Legal and Institutional Documentation",
             specific_activity="MoU drafting with Ministry of Agriculture",
             description="Drafted MoU covering joint agri-finance pilot programme; sent to legal department for review.",
             where_location="Government Office",
             whom="W/ro Meron Bekele (Legal), Mr. Yonas Kebede (MoA)",
             engagement_type="Meeting",
             doc_link="https://drive.example.com/mou-draft-moa-v1",
             result_outcome="Draft MoU sent for legal review",
             financial_result=0,
             future_plan="Legal review expected within 2 weeks; signing ceremony to be scheduled",
             status="Ongoing",
             responsible_org="Government Ministry / Agency (Yonas Kebede)",
             remarks=""),
        dict(date=date(2026, 7, 5), service_area="Research and Assessments",
             specific_activity="Feasibility study - digital lending product",
             description="Conducted market feasibility assessment for new digital lending product targeting youth entrepreneurs.",
             where_location="Field / Site Visit",
             whom="42 respondents (youth entrepreneurs, cooperative members)",
             engagement_type="Site Assessment / Survey",
             doc_link="https://drive.example.com/feasibility-digital-lending-report",
             result_outcome="Report finalized: 78% demand interest; recommended pilot in 3 branches",
             financial_result=0,
             future_plan="Present findings to management for pilot approval",
             status="Completed",
             responsible_org="Coop Bank (Sara Tesfaye)",
             remarks=""),
    ]

    for row in sample_rows:
        a = Activity()
        a.set_date(row.pop("date"))
        for k, v in row.items():
            setattr(a, k, v)
        db.session.add(a)

    # Empty target grid for FY2026, all four quarters x all service areas
    for year in [2026]:
        for quarter in config.QUARTERS:
            for sa in [s for s in config.SERVICE_AREAS if s != "Other"]:
                db.session.add(Target(year=year, quarter=quarter, service_area=sa,
                                       target_count=0, target_etb=0))

    db.session.commit()


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------
def register_routes(app: Flask):

    @app.route("/")
    def home():
        return redirect(url_for("dashboard"))

    @app.route("/dashboard")
    @login_required
    def dashboard():
        staff_id = request.args.get("staff_id", type=int)

        query = Activity.query
        if current_user.is_admin:
            if staff_id:
                query = query.filter_by(user_id=staff_id)
            # else: admin sees everyone (combined) by default
        else:
            # Non-admin staff always see only their own activities
            query = query.filter_by(user_id=current_user.id)

        total = query.count()
        completed = query.filter(Activity.status == "Completed").count()
        ongoing = query.filter(Activity.status == "Ongoing").count()
        delayed = query.filter(Activity.status == "Delayed").count()
        total_etb = db.session.query(func.coalesce(func.sum(Activity.financial_result), 0))\
            .filter(Activity.user_id == staff_id if (current_user.is_admin and staff_id) else
                    (Activity.user_id == current_user.id if not current_user.is_admin else True)).scalar()
        recent = query.order_by(Activity.date.desc()).limit(8).all()

        staff_list = User.query.filter_by(role="staff", is_approved=True).order_by(User.full_name).all() if current_user.is_admin else []
        selected_staff = User.query.get(staff_id) if (current_user.is_admin and staff_id) else None

        return render_template("dashboard.html", total=total, completed=completed,
                                ongoing=ongoing, delayed=delayed, total_etb=total_etb,
                                recent=recent, staff_list=staff_list, selected_staff=selected_staff)

    # ------------------------------------------------------------------
    # Activity Log — CRUD (the master sheet)
    # ------------------------------------------------------------------
    @app.route("/activities")
    @login_required
    def activity_list():
        year = request.args.get("year", type=int)
        month = request.args.get("month")
        status = request.args.get("status")
        service_area = request.args.get("service_area")

        q = Activity.query
        if year:
            q = q.filter(Activity.year == year)
        if month:
            q = q.filter(Activity.month == month)
        if status:
            q = q.filter(Activity.status == status)
        if service_area:
            q = q.filter(Activity.service_area == service_area)

        activities = q.order_by(Activity.date.desc()).all()
        years = [r[0] for r in db.session.query(Activity.year).distinct().order_by(Activity.year.desc())]

        return render_template("activities/activity_list.html", activities=activities,
                                years=years, months=config.MONTHS, statuses=config.STATUSES,
                                service_areas=config.SERVICE_AREAS,
                                filters=dict(year=year, month=month, status=status, service_area=service_area))

    @app.route("/activities/add", methods=["GET", "POST"])
    @login_required
    def activity_add():
        form = ActivityForm()
        if form.validate_on_submit():
            a = Activity()
            a.set_date(form.date.data)
            _apply_form(a, form)
            db.session.add(a)
            db.session.commit()
            flash("Activity added.", "success")
            return redirect(url_for("activity_list"))
        return render_template("activities/activity_form.html", form=form, title="Add Activity")

    @app.route("/activities/<int:activity_id>/edit", methods=["GET", "POST"])
    @login_required
    def activity_edit(activity_id):
        a = Activity.query.get_or_404(activity_id)
        form = ActivityForm(obj=a)
        if request.method == "GET":
            form.where_location.data = a.where_location
            form.result_outcome.data = a.result_outcome
            form.responsible_org.data = a.responsible_org
        if form.validate_on_submit():
            a.set_date(form.date.data)
            _apply_form(a, form)
            db.session.commit()
            flash("Activity updated.", "success")
            return redirect(url_for("activity_list"))
        return render_template("activities/activity_form.html", form=form, title="Edit Activity")

    @app.route("/activities/<int:activity_id>/delete", methods=["POST"])
    @login_required
    @admin_required
    def activity_delete(activity_id):
        a = Activity.query.get_or_404(activity_id)
        db.session.delete(a)
        db.session.commit()
        flash("Activity deleted.", "info")
        return redirect(url_for("activity_list"))

    def _apply_form(a: Activity, form: ActivityForm):
        a.service_area = form.service_area.data
        a.specific_activity = form.specific_activity.data
        a.description = form.description.data
        a.where_location = form.where_location.data
        a.whom = form.whom.data
        a.engagement_type = form.engagement_type.data
        a.doc_link = form.doc_link.data
        a.result_outcome = form.result_outcome.data
        a.financial_result = form.financial_result.data or 0
        a.future_plan = form.future_plan.data
        a.status = form.status.data
        a.responsible_org = form.responsible_org.data
        a.remarks = form.remarks.data

    # ------------------------------------------------------------------
    # Monthly Dashboard  (mirrors "Monthly Dashboard" sheet)
    # ------------------------------------------------------------------
    @app.route("/monthly")
    @login_required
    def monthly_dashboard():
        year = request.args.get("year", type=int, default=datetime.now().year)
        month = request.args.get("month", default=config.MONTHS[datetime.now().month - 1])

        base = Activity.query.filter(Activity.year == year, Activity.month == month)
        summary = dict(
            total=base.count(),
            completed=base.filter(Activity.status == "Completed").count(),
            ongoing=base.filter(Activity.status == "Ongoing").count(),
            delayed=base.filter(Activity.status == "Delayed").count(),
            total_etb=db.session.query(func.coalesce(func.sum(Activity.financial_result), 0))
                .filter(Activity.year == year, Activity.month == month).scalar(),
        )

        breakdown = []
        for sa in [s for s in config.SERVICE_AREAS if s != "Other"]:
            rows = base.filter(Activity.service_area == sa)
            breakdown.append(dict(
                service_area=sa,
                total=rows.count(),
                completed=rows.filter(Activity.status == "Completed").count(),
                ongoing=rows.filter(Activity.status == "Ongoing").count(),
                delayed=rows.filter(Activity.status == "Delayed").count(),
                etb=db.session.query(func.coalesce(func.sum(Activity.financial_result), 0))
                    .filter(Activity.year == year, Activity.month == month,
                            Activity.service_area == sa).scalar(),
            ))

        return render_template("monthly.html", year=year, month=month, summary=summary,
                                breakdown=breakdown, years=config.YEARS, months=config.MONTHS)

    # ------------------------------------------------------------------
    # Quarterly Dashboard  (mirrors "Quarterly Dashboard" sheet)
    # ------------------------------------------------------------------
    @app.route("/quarterly")
    @login_required
    def quarterly_dashboard():
        year = request.args.get("year", type=int, default=calc_fiscal_year(date.today()))
        quarter = request.args.get("quarter", default=calc_quarter(date.today()))

        base = Activity.query.filter(Activity.fiscal_year == year, Activity.quarter == quarter)
        summary = dict(
            total=base.count(),
            completed=base.filter(Activity.status == "Completed").count(),
            ongoing=base.filter(Activity.status == "Ongoing").count(),
            delayed=base.filter(Activity.status == "Delayed").count(),
            total_etb=db.session.query(func.coalesce(func.sum(Activity.financial_result), 0))
                .filter(Activity.fiscal_year == year, Activity.quarter == quarter).scalar(),
        )

        breakdown = []
        for sa in [s for s in config.SERVICE_AREAS if s != "Other"]:
            rows = base.filter(Activity.service_area == sa)
            breakdown.append(dict(
                service_area=sa,
                total=rows.count(),
                completed=rows.filter(Activity.status == "Completed").count(),
                ongoing=rows.filter(Activity.status == "Ongoing").count(),
                delayed=rows.filter(Activity.status == "Delayed").count(),
                etb=db.session.query(func.coalesce(func.sum(Activity.financial_result), 0))
                    .filter(Activity.fiscal_year == year, Activity.quarter == quarter,
                            Activity.service_area == sa).scalar(),
            ))

        return render_template("quarterly.html", year=year, quarter=quarter, summary=summary,
                                breakdown=breakdown, years=config.YEARS, quarters=config.QUARTERS)

   # ------------------------------------------------------------------
    # Quarterly Target vs Achievement (mirrors that sheet + "Targets" sheet)
    # ------------------------------------------------------------------

    @app.route("/quarterly-target")
    @login_required
    def quarterly_target():
        from flask_login import current_user
        from datetime import date
        from flask import request, render_template
        from sqlalchemy import func

        year = request.args.get("year", type=int, default=calc_fiscal_year(date.today()))
        quarter = request.args.get("quarter", default=calc_quarter(date.today()))

        # ✅ current logged-in user
        user_id = current_user.id

        rows = []
        total_target_count = 0
        total_actual_count = 0
        total_target_etb = 0
        total_actual_etb = 0

        for sa in [s for s in config.SERVICE_AREAS if s != "Other"]:

            # ✅ TARGETS
            target_count = db.session.query(
                func.coalesce(func.sum(Target.target_count), 0)
            ).filter(
                Target.year == year,
                Target.quarter == quarter,
                Target.service_area == sa,
                Target.user_id == user_id
            ).scalar()

            target_etb = db.session.query(
                func.coalesce(func.sum(Target.target_etb), 0)
            ).filter(
                Target.year == year,
                Target.quarter == quarter,
                Target.service_area == sa,
                Target.user_id == user_id
            ).scalar()

            # ✅ ACTUALS (FIXED: use user_id, NOT staff_id)
            actual_q = Activity.query.filter(
                Activity.fiscal_year == year,
                Activity.quarter == quarter,
                Activity.service_area == sa,
                Activity.user_id == user_id
            )

            actual_count = actual_q.count()

            actual_etb = db.session.query(
                func.coalesce(func.sum(Activity.financial_result), 0)
            ).filter(
                Activity.fiscal_year == year,
                Activity.quarter == quarter,
                Activity.service_area == sa,
                Activity.user_id == user_id
            ).scalar()

            rows.append({
                "service_area": sa,
                "target_count": target_count,
                "actual_count": actual_count,
                "pct_count": (actual_count / target_count) if target_count else 0,
                "target_etb": target_etb,
                "actual_etb": actual_etb,
                "pct_etb": (actual_etb / target_etb) if target_etb else 0,
            })

            total_target_count += target_count
            total_actual_count += actual_count
            total_target_etb += target_etb
            total_actual_etb += actual_etb

        totals = {
            "target_count": total_target_count,
            "actual_count": total_actual_count,
            "pct_count": (total_actual_count / total_target_count) if total_target_count else 0,
            "target_etb": total_target_etb,
            "actual_etb": total_actual_etb,
            "pct_etb": (total_actual_etb / total_target_etb) if total_target_etb else 0,
        }

        return render_template(
            "quarterly_target.html",
            year=year,
            quarter=quarter,
            rows=rows,
            totals=totals,
            years=config.YEARS,
            quarters=config.QUARTERS
        )
    # ------------------------------------------------------------------
    # Targets — data entry screen (mirrors "Targets" sheet)
    # ------------------------------------------------------------------
    @app.route("/targets", methods=["GET", "POST"])
    @login_required
    @admin_required
    def targets():
        year = request.args.get("year", type=int, default=calc_fiscal_year(date.today()))

        # All approved staff, so the admin can pick who they're setting targets for.
        staff = User.query.filter_by(role="staff", is_approved=True).order_by(User.full_name).all()

        if request.method == "POST":
            staff_id = request.form.get("staff_id", type=int)
        else:
            staff_id = request.args.get("staff_id", type=int)
        if staff_id is None and staff:
            staff_id = staff[0].id  # default to first staff member

        if request.method == "POST":
            for key, value in request.form.items():
                if key.startswith("count_") or key.startswith("etb_"):
                    kind, target_id = key.split("_", 1)
                    t = Target.query.get(int(target_id))
                    if t:
                        try:
                            num = float(value) if value not in ("", None) else 0
                        except ValueError:
                            num = 0
                        if kind == "count":
                            t.target_count = num
                        else:
                            t.target_etb = num
            db.session.commit()
            flash("Targets saved.", "success")
            return redirect(url_for("targets", year=year, staff_id=staff_id))

        grid = {}
        for quarter in config.QUARTERS:
            grid[quarter] = []
            for sa in [s for s in config.SERVICE_AREAS if s != "Other"]:
                t = Target.query.filter_by(year=year, quarter=quarter, service_area=sa,
                                            user_id=staff_id).first()
                if not t:
                    t = Target(year=year, quarter=quarter, service_area=sa, user_id=staff_id,
                               target_count=0, target_etb=0)
                    db.session.add(t)
                    db.session.commit()
                grid[quarter].append(t)

        return render_template("targets.html", year=year, grid=grid, years=config.YEARS,
                                quarters=config.QUARTERS, staff=staff, staff_id=staff_id)

    # ------------------------------------------------------------------
    # Annual Dashboard (mirrors "Annual Dashboard" sheet)
    # ------------------------------------------------------------------
    @app.route("/annual")
    @login_required
    def annual_dashboard():
        year = request.args.get("year", type=int, default=calc_fiscal_year(date.today()))

        base = Activity.query.filter(Activity.fiscal_year == year)
        summary = dict(
            total=base.count(),
            completed=base.filter(Activity.status == "Completed").count(),
            ongoing=base.filter(Activity.status == "Ongoing").count(),
            delayed=base.filter(Activity.status == "Delayed").count(),
            total_etb=db.session.query(func.coalesce(func.sum(Activity.financial_result), 0))
                .filter(Activity.fiscal_year == year).scalar(),
        )

        matrix = []
        for sa in [s for s in config.SERVICE_AREAS if s != "Other"]:
            row = {"service_area": sa, "months": [], "total": 0}
            for m in config.FISCAL_MONTHS:
                c = Activity.query.filter(Activity.fiscal_year == year, Activity.service_area == sa,
                                           Activity.month == m).count()
                row["months"].append(c)
                row["total"] += c
            matrix.append(row)

        return render_template("annual.html", year=year, summary=summary, matrix=matrix,
                                fiscal_months=config.FISCAL_MONTHS, years=config.YEARS)
# ------------------------------------------------------------------
    # Admin: manage Service Areas
    # ------------------------------------------------------------------
    @app.route("/admin/service-areas")
    @login_required
    @admin_required
    def service_area_list():
        areas = ServiceArea.query.order_by(ServiceArea.sort_order, ServiceArea.name).all()
        return render_template("admin/service_areas.html", areas=areas)

    @app.route("/admin/service-areas/add", methods=["POST"])
    @login_required
    @admin_required
    def service_area_add():
        name = (request.form.get("name") or "").strip()
        if not name:
            flash("Name is required.", "danger")
        elif ServiceArea.query.filter_by(name=name).first():
            flash("That service area already exists.", "danger")
        else:
            max_order = db.session.query(func.coalesce(func.max(ServiceArea.sort_order), 0)).scalar()
            db.session.add(ServiceArea(name=name, is_active=True, sort_order=max_order + 1))
            db.session.commit()
            flash("Service area added.", "success")
        return redirect(url_for("service_area_list"))

    @app.route("/admin/service-areas/<int:area_id>/rename", methods=["POST"])
    @login_required
    @admin_required
    def service_area_rename(area_id):
        area = ServiceArea.query.get_or_404(area_id)
        new_name = (request.form.get("name") or "").strip()
        if not new_name:
            flash("Name is required.", "danger")
            return redirect(url_for("service_area_list"))
        if ServiceArea.query.filter(ServiceArea.name == new_name, ServiceArea.id != area_id).first():
            flash("Another service area already has that name.", "danger")
            return redirect(url_for("service_area_list"))

        old_name = area.name
        area.name = new_name
        Activity.query.filter_by(service_area=old_name).update({"service_area": new_name})
        Target.query.filter_by(service_area=old_name).update({"service_area": new_name})
        db.session.commit()
        flash(f"Renamed '{old_name}' to '{new_name}' (existing records updated too).", "success")
        return redirect(url_for("service_area_list"))

    @app.route("/admin/service-areas/<int:area_id>/toggle", methods=["POST"])
    @login_required
    @admin_required
    def service_area_toggle(area_id):
        area = ServiceArea.query.get_or_404(area_id)
        area.is_active = not area.is_active
        db.session.commit()
        flash(f"'{area.name}' is now {'active' if area.is_active else 'inactive'}.", "info")
        return redirect(url_for("service_area_list"))

    @app.route("/admin/service-areas/<int:area_id>/delete", methods=["POST"])
    @login_required
    @admin_required
    def service_area_delete(area_id):
        area = ServiceArea.query.get_or_404(area_id)
        in_use = (Activity.query.filter_by(service_area=area.name).first()
                  or Target.query.filter_by(service_area=area.name).first())
        if in_use:
            flash("This service area is used by existing records — deactivate it instead of deleting.", "danger")
        else:
            db.session.delete(area)
            db.session.commit()
            flash("Service area deleted.", "success")
        return redirect(url_for("service_area_list"))


app = create_app()

if __name__ == "__main__":
    app.run(debug=True)
