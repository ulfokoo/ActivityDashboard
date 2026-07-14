import os
import secrets
import uuid
from werkzeug.utils import secure_filename
from datetime import date, datetime
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, abort, send_from_directory
from flask_login import LoginManager, login_required, current_user
from sqlalchemy import func, or_

import config
from models import (
    db, Activity, Target, User, ServiceArea, QuarterServiceArea, Team,
    calc_quarter, calc_fiscal_year, get_all_subordinates,
    ASSIGNABLE_ROLE, ROLE_RANK, can_manage_service_area,
    get_wing_owner_id, visible_service_area_owner_ids,
    Notification, notify_users,
)
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
    @app.teardown_appcontext
    def shutdown_session(exception=None):
            db.session.remove()

    with app.app_context():
        db.create_all()
        _ensure_user_columns()
        _ensure_service_area_columns()
        _ensure_team_support()
        _ensure_activity_columns()
        _seed_if_empty()
        _seed_default_admin()
        _seed_service_areas_if_empty()
 
    os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True) 
    register_routes(app)
    return app

def _ensure_user_columns():
    """
    Safety net: db.create_all() only creates NEW tables, it never adds
    columns to a table that already exists. This adds any columns the
    User model needs but the live database is still missing, so old
    deployments upgrade themselves automatically without losing data.
    """
    from sqlalchemy import text, inspect

    columns_to_add = {
        "position": "VARCHAR(120)",
        "department": "VARCHAR(120)",
        "otp_code": "VARCHAR(6)",
        "otp_expires_at": "TIMESTAMP",
        "email_verified": "BOOLEAN DEFAULT 0",
        "contact_phone": "VARCHAR(30)",
        "id_no": "VARCHAR(50)",
        "segment": "VARCHAR(120)",
        "manager_id": "INTEGER REFERENCES users(id)",
        "team_id": "INTEGER REFERENCES teams(id)"
    }

    with db.engine.connect() as conn:
        inspector = inspect(db.engine)
        existing = {col["name"] for col in inspector.get_columns("users")}
        for col, coltype in columns_to_add.items():
            if col not in existing:
                try:
                    conn.execute(text(f"ALTER TABLE users ADD COLUMN {col} {coltype}"))
                except Exception as e:
                    print(f"Column migration skipped/failed: {e}")
        conn.commit()
def _ensure_service_area_columns():
    """
    Same safety net as _ensure_user_columns(), but for the service_areas
    table — adds any columns the ServiceArea model needs that the live
    database is still missing.
    """
    from sqlalchemy import text, inspect

    columns_to_add = {
        "created_by_id": "INTEGER REFERENCES users(id)",
        "created_by_role": "VARCHAR(30)",
        "assigned_by_id": "INTEGER REFERENCES users(id)",
        "assigned_by_role": "VARCHAR(20)",
    }

    with db.engine.connect() as conn:
        inspector = inspect(db.engine)
        existing = {col["name"] for col in inspector.get_columns("service_areas")}
        for col, coltype in columns_to_add.items():
            if col not in existing:
                try:
                    conn.execute(text(f"ALTER TABLE service_areas ADD COLUMN {col} {coltype}"))
                except Exception as e:
                    print(f"Column migration skipped/failed: {e}")
        conn.commit()
 

def _ensure_team_support():
    """
    Creates the `teams` table if it doesn't exist yet, and adds the
    `team_id` column to `users` if the live database is still missing it.
    """
    from sqlalchemy import text, inspect
    ...     

       
def _ensure_activity_columns():
    from sqlalchemy import text, inspect

    columns_to_add = {
        "document_filename": "VARCHAR(255)",
        "document_original_name": "VARCHAR(255)",
    }

    with db.engine.connect() as conn:
        inspector = inspect(db.engine)
        existing = {col["name"] for col in inspector.get_columns("activities")}
        for col, coltype in columns_to_add.items():
            if col not in existing:
                try:
                    conn.execute(text(f"ALTER TABLE activities ADD COLUMN {col} {coltype}"))
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

def _quarter_service_areas(year, quarter, for_user=None):
    """
    ...(existing docstring, unchanged)...
    """
    scope_user = for_user or current_user

    existing = QuarterServiceArea.query.filter_by(year=year, quarter=quarter).all()
    if not existing:
        active_areas = [a.name for a in _scoped_service_areas_query(scope_user).all()]
        for a in active_areas:
            db.session.add(QuarterServiceArea(year=year, quarter=quarter, service_area=a))
        db.session.commit()
        existing = QuarterServiceArea.query.filter_by(year=year, quarter=quarter).all()

    visible_names = {a.name for a in _scoped_service_areas_query(scope_user).all()}
    return [q.service_area for q in existing if q.service_area in visible_names]


def _scoped_service_areas_query(user, only_active=True):
    """ServiceArea query scoped by role:
       - admin: sees everything
       - director/vp: sees only areas THEY personally assigned (isolated from peer directors/VPs)
       - manager: sees only areas that belong to them
    """
    q = ServiceArea.query
    if only_active:
        q = q.filter_by(is_active=True)

    if user.role == "admin":
        pass  # unrestricted
    elif user.role in ("director", "vp"):
        q = q.filter(ServiceArea.assigned_by_id == user.id)
    elif user.role == "manager":
        q = q.filter(ServiceArea.created_by_id == user.id)
    else:
        q = q.filter(db.false())

    return q.order_by(ServiceArea.sort_order, ServiceArea.name)

def _propagate_new_service_area_to_quarters(area_name):
    """
    When a new Service Area is added, push it into every year/quarter that
    has already been seeded, so it shows up in the Targets dropdown right
    away instead of only appearing the next time a fresh quarter is viewed.
    """
    seeded_quarters = db.session.query(
        QuarterServiceArea.year, QuarterServiceArea.quarter
    ).distinct().all()

    for year, quarter in seeded_quarters:
        exists = QuarterServiceArea.query.filter_by(
            year=year, quarter=quarter, service_area=area_name
        ).first()
        if not exists:
            db.session.add(QuarterServiceArea(year=year, quarter=quarter, service_area=area_name))
    db.session.commit()
# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------
def _apply_form(a, form):
    """Copy ActivityForm fields onto an Activity instance (except date/document/submit)."""
    a.service_area = form.service_area.data
    a.specific_activity = form.specific_activity.data
    a.description = form.description.data
    a.where_location = form.where_location.data
    a.whom = form.whom.data
    a.engagement_type = form.engagement_type.data
    a.result_outcome = form.result_outcome.data
    a.financial_result = form.financial_result.data
    a.future_plan = form.future_plan.data
    a.status = form.status.data
    a.responsible_org = form.responsible_org.data
    a.remarks = form.remarks.data


def _save_uploaded_document(file_storage):
    """Save an uploaded FileField's file to disk. Returns (saved_name, original_name) or (None, None)."""
    if not file_storage or not getattr(file_storage, "filename", ""):
        return None, None

    original_name = secure_filename(file_storage.filename)
    ext = os.path.splitext(original_name)[1]
    saved_name = f"{uuid.uuid4().hex}{ext}"

    upload_folder = getattr(config, "UPLOAD_FOLDER", os.path.join(os.getcwd(), "uploads"))
    os.makedirs(upload_folder, exist_ok=True)
    file_storage.save(os.path.join(upload_folder, saved_name))

    return saved_name, original_name


def register_routes(app: Flask):


    @app.route("/")
    def home():
        return redirect(url_for("dashboard"))

    @app.route("/dashboard")
    @login_required
    def dashboard():
        staff_id = request.args.get("staff_id", type=int)
        filter_ids, selected_staff, staff_groups = _resolve_view_scope(current_user, staff_id)

        base = Activity.query.filter(Activity.user_id.in_(filter_ids))
        total = base.count()
        completed = base.filter(Activity.status == "Completed").count()
        ongoing = base.filter(Activity.status == "Ongoing").count()
        delayed = base.filter(Activity.status == "Delayed").count()
        total_etb = db.session.query(func.coalesce(func.sum(Activity.financial_result), 0)) \
            .filter(Activity.user_id.in_(filter_ids)).scalar()

        recent = base.order_by(Activity.date.desc()).limit(10).all()

        return render_template(
            "dashboard.html",
            total=total, completed=completed, ongoing=ongoing, delayed=delayed, total_etb=total_etb,
            recent=recent,
            staff_groups=staff_groups, selected_staff=selected_staff,
        )
   
    @app.route("/activities")
    @login_required
    def activity_list():
        year = request.args.get("year", type=int)
        month = request.args.get("month")
        status = request.args.get("status")
        service_area = request.args.get("service_area")

        staff_id_param = request.args.get("staff_id", "")
        if staff_id_param == "me":
            staff_id = "me"
        elif staff_id_param == "0":
            staff_id = 0
        elif staff_id_param.isdigit():
            staff_id = int(staff_id_param)
        else:
            staff_id = None

        if staff_id == "me":
            filter_ids = [current_user.id]
            selected_staff = None
            staff_groups = _staff_view_options(current_user)
        else:
            filter_ids, selected_staff, staff_groups = _resolve_view_scope(current_user, staff_id)

        q = Activity.query
        if filter_ids is not None:
            q = q.filter(Activity.user_id.in_(filter_ids))
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
                        filters=dict(year=year, month=month, status=status, service_area=service_area),
                        staff_groups=staff_groups, staff_id=staff_id,
                        selected_staff=selected_staff)

    @app.route("/activities/add", methods=["GET", "POST"])
    @login_required
    def activity_add():
        form = ActivityForm()
        if form.validate_on_submit():
            a = Activity()
            a.set_date(form.date.data)
            _apply_form(a, form)
            saved_name, original_name = _save_uploaded_document(form.document.data)
            if saved_name:
                a.document_filename = saved_name
                a.document_original_name = original_name
            a.user_id = current_user.id
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
            saved_name, original_name = _save_uploaded_document(form.document.data)
            if saved_name:
                a.document_filename = saved_name
                a.document_original_name = original_name
            db.session.commit()
            flash("Activity updated.", "success")
            return redirect(url_for("activity_list"))
        return render_template("activities/activity_form.html", form=form, title="Edit Activity", activity=a)
    def _user_brief(u):
        return {"id": u.id, "full_name": u.full_name, "role": u.role}

    def _build_manager_groups(managers):
        groups = []
        for m in managers:
            staff = User.query.filter_by(manager_id=m.id, is_approved=True).order_by(User.full_name).all()
            team_name = m.team.name if m.team else f"{m.full_name}'s Team"
            groups.append({
                "manager": _user_brief(m),
                "staff": [_user_brief(s) for s in staff],
                "team_name": team_name
            })
        return groups

    def _build_director_groups(directors):
        groups = []
        for d in directors:
            managers = User.query.filter_by(manager_id=d.id, role="manager", is_approved=True).order_by(User.full_name).all()
            groups.append({
                "director": _user_brief(d),
                "manager_groups": _build_manager_groups(managers)
            })
        return groups
    
    def _staff_view_options(user):
        """
        Builds the hierarchy visible to `user` for the 'View Staff' selector.
        Returns {"level": "director"|"manager", "groups": [...]}
        - admin / anyone ranked above director: level="director" -> Directors -> Managers -> Staff
        - director: level="manager" -> their Managers -> Staff
        - manager: level="manager" -> just themselves -> Staff
        - staff: level="manager" -> empty
        """
        user_rank = ROLE_RANK.get(user.role, 0)
        director_rank = ROLE_RANK.get("director", 2)

        if user.role == "admin":
            directors = User.query.filter_by(role="director", is_approved=True).order_by(User.full_name).all()
            return {"level": "director", "groups": _build_director_groups(directors)}
        elif user_rank > director_rank:
            subs = get_all_subordinates(user)
            directors = [u for u in subs if u.role == "director"]
            return {"level": "director", "groups": _build_director_groups(directors)}
        elif user.role == "director":
            subs = get_all_subordinates(user)
            managers = [u for u in subs if u.role == "manager"]
            return {"level": "manager", "groups": _build_manager_groups(managers)}
        elif user.role == "manager":
            return {"level": "manager", "groups": _build_manager_groups([user])}
        else:
            return {"level": "manager", "groups": []}

    def _resolve_view_scope(current_user, staff_id):
        """
        Turns a staff_id from the dropdown into (filter_ids, selected_staff,
        view). `view` is the dict from _staff_view_options — pass it straight
        into the template. Selecting a director rolls up that director's
        entire org (all their managers + all staff); selecting a manager
        rolls up just their team; selecting a staff member drills to just
        that person.
        """
        view = _staff_view_options(current_user)

        # Flatten everything visible into id -> rollup-ids maps.
        director_rollups = {}   # director_id -> [director_id, manager_ids..., staff_ids...]
        manager_rollups = {}    # manager_id -> [manager_id, staff_ids...]
        all_visible_ids = set()

        if view["level"] == "director":
            for dg in view["groups"]:
                d_id = dg["director"]["id"]
                org_ids = [d_id]
                for mg in dg["manager_groups"]:
                    m_ids = [mg["manager"]["id"]] + [s["id"] for s in mg["staff"]]
                    manager_rollups[mg["manager"]["id"]] = m_ids
                    org_ids += m_ids
                director_rollups[d_id] = org_ids
                all_visible_ids.update(org_ids)
        else:
            for mg in view["groups"]:
                m_ids = [mg["manager"]["id"]] + [s["id"] for s in mg["staff"]]
                manager_rollups[mg["manager"]["id"]] = m_ids
                all_visible_ids.update(m_ids)


        selected_staff = None
        if staff_id == 0:
            filter_ids = list(all_visible_ids) if all_visible_ids else [current_user.id]
        elif staff_id and staff_id in director_rollups:
            filter_ids = director_rollups[staff_id]
            selected_staff = User.query.get(staff_id)
        elif staff_id and staff_id in manager_rollups:
            filter_ids = manager_rollups[staff_id]
            selected_staff = User.query.get(staff_id)
        elif staff_id and staff_id in all_visible_ids:
            filter_ids = [staff_id]
            selected_staff = User.query.get(staff_id)
        else:
            filter_ids = [current_user.id]

        return filter_ids, selected_staff, view
       
    
    @app.route("/activities/<int:activity_id>/document")
    @login_required
    def activity_document(activity_id):
            if current_user.role not in ("manager", "director", "vp", "admin"):
                abort(403)
            a = Activity.query.get_or_404(activity_id)
            if not a.document_filename:
                abort(404)
            return send_from_directory(
                app.config["UPLOAD_FOLDER"],
                a.document_filename,
                as_attachment=True,
                download_name=a.document_original_name or a.document_filename,
        )
    
    @app.route("/activities/<int:activity_id>/delete", methods=["POST"])
    @login_required
    @admin_required
    def activity_delete(activity_id):
        a = Activity.query.get_or_404(activity_id)
        db.session.delete(a)
        db.session.commit()
        flash("Activity deleted.", "info")
        return redirect(url_for("activity_list"))
    

    
    def _save_uploaded_document(file_storage):
        """Saves an uploaded FileStorage with a collision-proof name.
        Returns (saved_filename, original_filename) or (None, None) if no file."""
        if not file_storage or not file_storage.filename:
            return None, None
        original_name = secure_filename(file_storage.filename)
        ext = original_name.rsplit(".", 1)[-1].lower() if "." in original_name else ""
        saved_name = f"{uuid.uuid4().hex}.{ext}" if ext else uuid.uuid4().hex
        file_storage.save(os.path.join(app.config["UPLOAD_FOLDER"], saved_name))
        return saved_name, original_name
    def _apply_form(a: Activity, form: ActivityForm):
        a.service_area = form.service_area.data
        a.specific_activity = form.specific_activity.data
        a.description = form.description.data
        a.where_location = form.where_location.data
        a.whom = form.whom.data
        a.engagement_type = form.engagement_type.data
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
        staff_id = request.args.get("staff_id", type=int)

        filter_ids, selected_staff, staff_groups = _resolve_view_scope(current_user, staff_id)

        base = Activity.query.filter(
            Activity.year == year, Activity.month == month, Activity.user_id.in_(filter_ids)
        )
        summary = dict(
            total=base.count(),
            completed=base.filter(Activity.status == "Completed").count(),
            ongoing=base.filter(Activity.status == "Ongoing").count(),
            delayed=base.filter(Activity.status == "Delayed").count(),
            total_etb=db.session.query(func.coalesce(func.sum(Activity.financial_result), 0))
                .filter(Activity.year == year, Activity.month == month, Activity.user_id.in_(filter_ids)).scalar(),
        )

        active_areas = [a.name for a in _scoped_service_areas_query(current_user)
                        .order_by(ServiceArea.sort_order, ServiceArea.name).all()]

        breakdown = []
        for sa in active_areas:
            rows = base.filter(Activity.service_area == sa)
            breakdown.append(dict(
                service_area=sa,
                total=rows.count(),
                completed=rows.filter(Activity.status == "Completed").count(),
                ongoing=rows.filter(Activity.status == "Ongoing").count(),
                delayed=rows.filter(Activity.status == "Delayed").count(),
                etb=db.session.query(func.coalesce(func.sum(Activity.financial_result), 0))
                    .filter(Activity.year == year, Activity.month == month,
                            Activity.service_area == sa, Activity.user_id.in_(filter_ids)).scalar(),
            ))

        return render_template("monthly.html", year=year, month=month, summary=summary,
                                breakdown=breakdown, years=config.YEARS, months=config.MONTHS,
                                staff_groups=staff_groups, selected_staff=selected_staff, staff_id=staff_id)


    # ------------------------------------------------------------------
    # Quarterly Dashboard  (mirrors "Quarterly Dashboard" sheet)
    # ------------------------------------------------------------------
    @app.route("/quarterly")
    @login_required
    def quarterly_dashboard():
        year = request.args.get("year", type=int, default=calc_fiscal_year(date.today()))
        quarter = request.args.get("quarter", default=calc_quarter(date.today()))
        staff_id = request.args.get("staff_id", type=int)

        filter_ids, selected_staff, staff_groups = _resolve_view_scope(current_user, staff_id)

        base = Activity.query.filter(
            Activity.fiscal_year == year, Activity.quarter == quarter, Activity.user_id.in_(filter_ids)
        )
        summary = dict(
            total=base.count(),
            completed=base.filter(Activity.status == "Completed").count(),
            ongoing=base.filter(Activity.status == "Ongoing").count(),
            delayed=base.filter(Activity.status == "Delayed").count(),
            total_etb=db.session.query(func.coalesce(func.sum(Activity.financial_result), 0))
                .filter(Activity.fiscal_year == year, Activity.quarter == quarter,
                        Activity.user_id.in_(filter_ids)).scalar(),
        )

        active_areas = [a.name for a in _scoped_service_areas_query(current_user).all()]

        breakdown = []
        for sa in active_areas:
            rows = base.filter(Activity.service_area == sa)
            breakdown.append(dict(
                service_area=sa,
                total=rows.count(),
                completed=rows.filter(Activity.status == "Completed").count(),
                ongoing=rows.filter(Activity.status == "Ongoing").count(),
                delayed=rows.filter(Activity.status == "Delayed").count(),
                etb=db.session.query(func.coalesce(func.sum(Activity.financial_result), 0))
                    .filter(Activity.fiscal_year == year, Activity.quarter == quarter,
                            Activity.service_area == sa, Activity.user_id.in_(filter_ids)).scalar(),
            ))

        return render_template("quarterly.html", year=year, quarter=quarter, summary=summary,
                                breakdown=breakdown, years=config.YEARS, quarters=config.QUARTERS,
                                staff_groups=staff_groups, selected_staff=selected_staff, staff_id=staff_id)

   # ------------------------------------------------------------------
    # Quarterly Target vs Achievement (mirrors that sheet + "Targets" sheet)
    # ------------------------------------------------------------------

    @app.route("/quarterly-target")
    @login_required
    def quarterly_target():
        year = request.args.get("year", type=int, default=calc_fiscal_year(date.today()))
        quarter = request.args.get("quarter", default=calc_quarter(date.today()))
        staff_id = request.args.get("staff_id", type=int)

        filter_ids, selected_staff, staff_groups = _resolve_view_scope(current_user, staff_id)

        rows = []
        total_target_count = 0
        total_actual_count = 0
        total_target_etb = 0
        total_actual_etb = 0

        active_areas = [a.name for a in _scoped_service_areas_query(current_user).all()]

        for sa in active_areas:
            target_count = db.session.query(func.coalesce(func.sum(Target.target_count), 0)).filter(
                Target.year == year, Target.quarter == quarter, Target.service_area == sa,
                Target.user_id.in_(filter_ids)
            ).scalar()

            target_etb = db.session.query(func.coalesce(func.sum(Target.target_etb), 0)).filter(
                Target.year == year, Target.quarter == quarter, Target.service_area == sa,
                Target.user_id.in_(filter_ids)
            ).scalar()

            actual_q = Activity.query.filter(
                Activity.fiscal_year == year, Activity.quarter == quarter,
                Activity.service_area == sa, Activity.user_id.in_(filter_ids)
            )
            actual_count = actual_q.count()

            actual_etb = db.session.query(func.coalesce(func.sum(Activity.financial_result), 0)).filter(
                Activity.fiscal_year == year, Activity.quarter == quarter,
                Activity.service_area == sa, Activity.user_id.in_(filter_ids)
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
            year=year, quarter=quarter, rows=rows, totals=totals,
            years=config.YEARS, quarters=config.QUARTERS,
            staff_groups=staff_groups, selected_staff=selected_staff, staff_id=staff_id,
        )

    # ------------------------------------------------------------------
    # Targets — data entry screen (mirrors "Targets" sheet)
    # ------------------------------------------------------------------
    @app.route("/targets", methods=["GET", "POST"])
    @login_required
    def targets():
        if current_user.role not in ("admin", "manager", "director", "vp"):
            flash("That page is restricted.", "info")
            return redirect(url_for("dashboard"))

        year = request.args.get("year", type=int, default=calc_fiscal_year(date.today()))

        # staff_id: "" -> Myself (None), "0" -> All My Staff, else a numeric id
        def _parse_staff_id(raw):
            if raw == "":
                return None
            if raw.lstrip("-").isdigit():
                return int(raw)
            return None

        staff_id = _parse_staff_id(request.args.get("staff_id", ""))

        if current_user.role == "admin":
            visible_staff = User.query.filter_by(is_approved=True).order_by(User.full_name).all()
        else:
            # Restrict target assignment to exactly one level down:
            # VP -> Director, Director -> Manager, Manager -> Staff
            target_role = ASSIGNABLE_ROLE.get(current_user.role)
            all_subordinates = get_all_subordinates(current_user)
            visible_staff = [u for u in all_subordinates if u.role == target_role]
        visible_ids = {u.id for u in visible_staff}

        if not visible_staff and current_user.role != "admin":
            flash("You have no staff reporting to you yet.", "info")

        # Fall back to "Myself" if an invalid/unauthorized id sneaks into the URL.
        if staff_id is not None and staff_id != 0 and staff_id not in visible_ids:
            staff_id = None

        def _recipient_for(selected):
            """Who an 'Add' action should assign a target to, given the selection."""
            if selected == 0:
                return None  # "All My Staff" — Add is disabled for this view
            if selected is None:
                return current_user.id
            if selected in visible_ids:
                return selected
            return current_user.id

        if request.method == "POST":
            form = request.form
            posted_staff_id_raw = form.get("staff_id", "")
            posted_selected = _parse_staff_id(posted_staff_id_raw)
            posted_recipient = _recipient_for(posted_selected)

            def _back(anchor=""):
                return redirect(url_for("targets", year=year, staff_id=posted_staff_id_raw) + anchor)

            # 1) Remove
            remove_key = next((k for k in form if k.startswith("remove_")), None)
            if remove_key:
                target_id = int(remove_key.split("_", 1)[1])
                t = Target.query.get(target_id)
                allowed = t and (
                    current_user.role == "admin"
                    or t.user_id in visible_ids
                    or t.user_id == current_user.id
                )
                if allowed:
                    quarter = t.quarter
                    db.session.delete(t)
                    db.session.commit()
                    flash("Target removed.", "success")
                    return _back(f"#{quarter}")
                flash("Not authorized to remove that target.", "danger")
                return _back()

            # 2) Add — assigned to posted_recipient
            add_key = next((k for k in form if k.startswith("add_")), None)
            if add_key:
                quarter = add_key.split("_", 1)[1]
                service_area = form.get(f"new_area_{quarter}")
                count = form.get(f"new_count_{quarter}", 0, type=float)
                etb = form.get(f"new_etb_{quarter}", 0, type=float)

                if posted_recipient is None:
                    flash("Select an individual staff member (or Myself) before adding a target.", "danger")
                    return _back(f"#{quarter}")

                if (
                    posted_recipient != current_user.id
                    and posted_recipient not in visible_ids
                    and current_user.role != "admin"
                ):
                    flash("Not authorized to assign targets to that person.", "danger")
                    return _back(f"#{quarter}")

                if service_area:
                    existing = Target.query.filter_by(
                        year=year, quarter=quarter, service_area=service_area, user_id=posted_recipient
                    ).first()
                    if existing:
                        flash("That staff member already has a target for this Service Area/quarter.", "info")
                    else:
                        db.session.add(Target(
                            year=year, quarter=quarter, service_area=service_area,
                            user_id=posted_recipient, target_count=count or 0, target_etb=etb or 0,
                        ))
                        db.session.commit()
                        flash("Target added.", "success")
                return _back(f"#{quarter}")

            # 3) Bulk save
            last_quarter = None
            for key, value in form.items():
                if key.startswith("count_") or key.startswith("etb_"):
                    kind, target_id = key.split("_", 1)
                    t = Target.query.get(int(target_id))
                    allowed = t and (
                        current_user.role == "admin"
                        or t.user_id in visible_ids
                        or t.user_id == current_user.id
                    )
                    if allowed:
                        try:
                            num = float(value) if value not in ("", None) else 0
                        except ValueError:
                            num = 0
                        if kind == "count":
                            t.target_count = num
                        else:
                            t.target_etb = num
                        last_quarter = t.quarter
            db.session.commit()
            flash("Targets saved.", "success")
            return _back(f"#{last_quarter}" if last_quarter else "")

        # ---- GET ----
        if staff_id == 0:
            filter_ids = list(visible_ids) if visible_ids else [current_user.id]
        elif staff_id is None:
            filter_ids = [current_user.id]
        else:
            filter_ids = [staff_id]

        # Scope service areas to the selected manager/staff member, not just
        # the logged-in director — so picking a manager shows their branch.
        if staff_id and staff_id != 0 and staff_id in visible_ids:
            scope_user = User.query.get(staff_id)
        else:
            scope_user = current_user

        quarter_rows = {}
        remaining_areas = {}
        for quarter in config.QUARTERS:
            areas = _quarter_service_areas(year, quarter, for_user=scope_user)
            q = Target.query.filter(
                Target.year == year, Target.quarter == quarter, Target.user_id.in_(filter_ids)
            )
            quarter_rows[quarter] = q.order_by(Target.service_area).all()
            remaining_areas[quarter] = areas

        return render_template(
            "targets.html",
            year=year,
            quarters=config.QUARTERS,
            quarter_rows=quarter_rows,
            remaining_areas=remaining_areas,
            visible_staff=visible_staff,
            years=config.YEARS,
            staff_id=staff_id,
            can_add=(staff_id != 0),
        )
   
    @app.route("/notifications")
    @login_required
    def notifications_list():
        notes = Notification.query.filter_by(user_id=current_user.id) \
            .order_by(Notification.created_at.desc()).limit(20).all()
        return jsonify([{
            "id": n.id,
            "message": n.message,
            "link": n.link,
            "is_read": n.is_read,
            "created_at": n.created_at.strftime("%d %b %Y %H:%M")
        } for n in notes])


    @app.route("/notifications/unread_count")
    @login_required
    def notifications_unread_count():
        count = Notification.query.filter_by(user_id=current_user.id, is_read=False).count()
        return jsonify({"count": count})


    @app.route("/notifications/mark_read", methods=["POST"])
    @login_required
    def notifications_mark_read():
        Notification.query.filter_by(user_id=current_user.id, is_read=False) \
            .update({"is_read": True})
        db.session.commit()
        return jsonify({"ok": True})

    # ------------------------------------------------------------------
    # Annual Dashboard (mirrors "Annual Dashboard" sheet)
    # ------------------------------------------------------------------
    @app.route("/annual")
    @login_required
    def annual_dashboard():
        year = request.args.get("year", type=int, default=calc_fiscal_year(date.today()))
        staff_id = request.args.get("staff_id", type=int)

        filter_ids, selected_staff, staff_groups = _resolve_view_scope(current_user, staff_id)

        base = Activity.query.filter(Activity.fiscal_year == year, Activity.user_id.in_(filter_ids))
        summary = dict(
            total=base.count(),
            completed=base.filter(Activity.status == "Completed").count(),
            ongoing=base.filter(Activity.status == "Ongoing").count(),
            delayed=base.filter(Activity.status == "Delayed").count(),
            total_etb=db.session.query(func.coalesce(func.sum(Activity.financial_result), 0))
                .filter(Activity.fiscal_year == year, Activity.user_id.in_(filter_ids)).scalar(),
        )

        active_areas = [a.name for a in _scoped_service_areas_query(current_user).all()]

        matrix = []
        for sa in active_areas:
            row = {"service_area": sa, "months": [], "total": 0}
            for m in config.FISCAL_MONTHS:
                c = Activity.query.filter(Activity.fiscal_year == year, Activity.service_area == sa,
                                        Activity.month == m, Activity.user_id.in_(filter_ids)).count()
                row["months"].append(c)
                row["total"] += c
            matrix.append(row)

        return render_template("annual.html", year=year, summary=summary, matrix=matrix,
                                fiscal_months=config.FISCAL_MONTHS, years=config.YEARS,
                                staff_groups=staff_groups, selected_staff=selected_staff, staff_id=staff_id)

    # ------------------------------------------------------------------
    # Manage Service Areas — Admin / Manager / Director / VP
    # ------------------------------------------------------------------

    @app.route("/admin/teams")
    @login_required
    def team_list():
        if current_user.role not in ("admin", "vp", "director"):
            flash("That page is restricted.", "info")
            return redirect(url_for("dashboard"))

        teams = Team.query.order_by(Team.name).all()
        managers = User.query.filter_by(role="manager", is_approved=True).order_by(User.full_name).all()
        return render_template("admin/teams.html", teams=teams, managers=managers)

    @app.route("/admin/teams/add", methods=["POST"])
    @login_required
    def team_add():
        if current_user.role not in ("admin", "vp", "director"):
            flash("Not authorized.", "danger")
            return redirect(url_for("team_list"))

        name = (request.form.get("name") or "").strip()
        if not name:
            flash("Team name is required.", "danger")
        elif Team.query.filter_by(name=name).first():
            flash("That team already exists.", "danger")
        else:
            db.session.add(Team(name=name, is_active=True))
            db.session.commit()
            flash(f"Team '{name}' created.", "success")
        return redirect(url_for("team_list"))

    @app.route("/admin/teams/assign", methods=["POST"])
    @login_required
    def team_assign():
        if current_user.role not in ("admin", "vp", "director"):
            flash("Not authorized.", "danger")
            return redirect(url_for("team_list"))

        manager_id = request.form.get("manager_id", type=int)
        team_id = request.form.get("team_id", type=int)
        manager = User.query.filter_by(id=manager_id, role="manager").first()
        if not manager:
            flash("Manager not found.", "danger")
            return redirect(url_for("team_list"))

        manager.team_id = team_id if team_id else None
        db.session.commit()
        flash(f"{manager.full_name} updated.", "success")
        return redirect(url_for("team_list"))
    

    @app.route("/admin/service-areas/<int:area_id>/rename", methods=["POST"])
    @login_required
    def service_area_rename(area_id):
        area = ServiceArea.query.get_or_404(area_id)
        if not can_manage_service_area(current_user, area):
            flash("Not authorized to rename this service area.", "danger")
            return redirect(url_for("service_area_list"))

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
        QuarterServiceArea.query.filter_by(service_area=old_name).update({"service_area": new_name})
        db.session.commit()
        flash(f"Renamed '{old_name}' to '{new_name}' (existing records updated too).", "success")
        return redirect(url_for("service_area_list"))
    
    @app.route("/admin/service-areas/add", methods=["POST"])
    @login_required
    def service_area_add():
        if current_user.role not in ("admin", "manager", "vp", "director"):
            flash("Not authorized.", "danger")
            return redirect(url_for("service_area_list"))

        name = (request.form.get("name") or "").strip()
        if not name:
            flash("Service area name is required.", "danger")
            return redirect(url_for("service_area_list"))
        if ServiceArea.query.filter_by(name=name).first():
            flash("A service area with that name already exists.", "danger")
            return redirect(url_for("service_area_list"))

        manager_id = request.form.get("manager_id", type=int)

        if current_user.role == "manager":
            creator_id = current_user.id
            assigner_id = current_user.id
        else:
            creator_id = manager_id if manager_id else current_user.id
            assigner_id = current_user.id

        area = ServiceArea(
            name=name,
            created_by_id=creator_id,
            assigned_by_id=assigner_id,
            is_active=True,
        )

        db.session.add(area)
        db.session.commit()
        _propagate_new_service_area_to_quarters(area.name)
        flash(f"Service area '{name}' created.", "success")
        return redirect(url_for("service_area_list"))

    @app.route("/admin/service-areas/<int:area_id>/toggle", methods=["POST"])
    @login_required
    def service_area_toggle(area_id):
        area = ServiceArea.query.get_or_404(area_id)
        if not can_manage_service_area(current_user, area):
            flash("Not authorized to change this service area.", "danger")
            return redirect(url_for("service_area_list"))
        area.is_active = not area.is_active
        db.session.commit()
        flash(f"'{area.name}' is now {'active' if area.is_active else 'inactive'}.", "info")
        return redirect(url_for("service_area_list"))
    


    @app.route("/admin/service-areas")
    @login_required
    def service_area_list():
        if current_user.role not in ("admin", "manager", "director", "vp"):
            flash("That page is restricted.", "info")
            return redirect(url_for("dashboard"))

        areas = _scoped_service_areas_query(current_user, only_active=False).all()
        managers = []
        if current_user.role in ("admin", "vp", "director"):
            managers = User.query.filter_by(role="manager").order_by(User.full_name).all()
        return render_template("admin/service_areas.html", areas=areas, managers=managers)

    @app.route("/admin/service-areas/<int:area_id>/delete", methods=["POST"])
    @login_required
    def service_area_delete(area_id):
        area = ServiceArea.query.get_or_404(area_id)
        if not can_manage_service_area(current_user, area):
            flash("Not authorized to delete this service area.", "danger")
            return redirect(url_for("service_area_list"))

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