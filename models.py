import math
from datetime import date, datetime

from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash

db = SQLAlchemy()


class User(UserMixin, db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    full_name = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    team_id = db.Column(db.Integer, db.ForeignKey("teams.id"), nullable=True)
    team = db.relationship("Team", backref="members")

    # "admin", "vp", "director", "manager", or "staff"
    role = db.Column(db.String(20), nullable=False, default="staff")
    position = db.Column(db.String(120))
    department = db.Column(db.String(120))

    # ✅ NEW registration fields
    contact_phone = db.Column(db.String(30))
    id_no = db.Column(db.String(50))
    segment = db.Column(db.String(120))

    otp_code = db.Column(db.String(6))
    otp_expires_at = db.Column(db.DateTime)
    email_verified = db.Column(db.Boolean, default=False)

    # Self-registered accounts start unapproved and can't log in until an
    # admin approves them.
    is_approved = db.Column(db.Boolean, nullable=False, default=False)

    # Reporting hierarchy: who this user reports to (their manager/director/VP)
    manager_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    manager = db.relationship("User", remote_side=[id], backref="direct_reports")

    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def set_password(self, raw_password: str):
        self.password_hash = generate_password_hash(raw_password)

    def check_password(self, raw_password: str) -> bool:
        return check_password_hash(self.password_hash, raw_password)

    @property
    def is_admin(self) -> bool:
        return self.role == "admin"


def get_all_subordinates(user):
    """Every user reporting up to `user`, at any depth. Safe against cycles."""
    result = []
    seen_ids = {user.id}
    stack = list(user.direct_reports)
    while stack:
        person = stack.pop()
        if person.id in seen_ids:
            continue  # cycle detected — skip, don't loop forever
        seen_ids.add(person.id)
        result.append(person)
        stack.extend(person.direct_reports)
    return result

class Notification(db.Model):
    __tablename__ = "notifications"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    user = db.relationship("User", backref="notifications")

    message = db.Column(db.String(255), nullable=False)
    link = db.Column(db.String(255), nullable=True)
    is_read = db.Column(db.Boolean, nullable=False, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


def notify_users(user_ids, message, link=None):
    seen = set()
    for uid in user_ids:
        if not uid or uid in seen:
            continue
        seen.add(uid)
        db.session.add(Notification(user_id=uid, message=message, link=link))

class Team(db.Model):
    __tablename__ = "teams"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), unique=True, nullable=False)
    is_active = db.Column(db.Boolean, nullable=False, default=True)

# ---------------------------------------------------------------------------
# Role-based permission for Service Areas: each role can only rename/delete
# areas created by their own role or a role below them, never above.
ROLE_RANK = {"staff": 0, "manager": 1, "director": 2, "vp": 3, "admin": 4}

# Maps a user's role to the role whose targets they're allowed to manage.
# e.g. a manager sets targets for staff, a director sets targets for
# managers, etc. Adjust the mapping to match your actual hierarchy.
ASSIGNABLE_ROLE = {
    "admin": "vp",
    "vp": "director",
    "director": "manager",
    "manager": "staff",
}

def can_manage_service_area(user, area) -> bool:
    """True if `user` is allowed to rename/delete/toggle `area`."""
    if user.role == "admin":
        return True
    if user.role == "manager":
        return area.created_by_id == user.id
    # director/vp: can manage their own areas, or anything created by a
    # lower-ranked role (i.e. any manager's area), since they see everything.
    creator_rank = ROLE_RANK.get(area.created_by_role, 0)
    user_rank = ROLE_RANK.get(user.role, 0)
    return area.created_by_id == user.id or user_rank > creator_rank

# ---------------------------------------------------------------------------

def calc_day(d: date) -> str:
    return d.strftime("%A")


def calc_week(d: date) -> str:
    return "W" + str(min(4, math.ceil(d.day / 7)))


def calc_month(d: date) -> str:
    return d.strftime("%B")


def calc_quarter(d: date) -> str:
    return "Q" + str(((d.month - 7) % 12) // 3 + 1)


def calc_fiscal_year(d: date) -> int:
    return d.year - (1 if d.month < 7 else 0)


class Activity(db.Model):
    __tablename__ = "activities"

    id = db.Column(db.Integer, primary_key=True)

    date = db.Column(db.Date, nullable=False)

    # Auto-calculated columns (stored for fast filtering/dashboard queries,
    # recomputed automatically in __init__ / set_date whenever date changes)
    day = db.Column(db.String(20))
    week = db.Column(db.String(5))
    month = db.Column(db.String(20))
    quarter = db.Column(db.String(5))
    year = db.Column(db.Integer)
    fiscal_year = db.Column(db.Integer)

    service_area = db.Column(db.String(120), nullable=False)
    specific_activity = db.Column(db.String(255))
    description = db.Column(db.Text)
    where_location = db.Column(db.String(120))
    whom = db.Column(db.String(255))
    engagement_type = db.Column(db.String(80))
    doc_link = db.Column(db.String(500))  # kept for old records; no longer used by the form
    document_filename = db.Column(db.String(255))       # sanitized name stored on disk
    document_original_name = db.Column(db.String(255))  # original filename shown to users
    result_outcome = db.Column(db.Text)
    financial_result = db.Column(db.Float, default=0)
    future_plan = db.Column(db.Text)
    status = db.Column(db.String(30), default="Planned")
    responsible_org = db.Column(db.String(255))
    remarks = db.Column(db.Text)

    # link to user
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    user = db.relationship("User", backref="activities")

    def set_date(self, d: date):
        """Set the date and refresh every auto-calculated column, exactly
        like the Excel formulas used to do when you typed a new date."""
        self.date = d
        self.day = calc_day(d)
        self.week = calc_week(d)
        self.month = calc_month(d)
        self.quarter = calc_quarter(d)
        self.year = d.year
        self.fiscal_year = calc_fiscal_year(d)


class Target(db.Model):
    __tablename__ = "targets"

    id = db.Column(db.Integer, primary_key=True)
    year = db.Column(db.Integer, nullable=False)
    quarter = db.Column(db.String(5), nullable=False)
    service_area = db.Column(db.String(120), nullable=False)
    target_count = db.Column(db.Integer, default=0)
    target_etb = db.Column(db.Float, default=0)

    # link to user
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    user = db.relationship("User", backref="targets")

    __table_args__ = (
        db.UniqueConstraint(
            "year", "quarter", "service_area", "user_id",
            name="uq_target_row"
        ),
    )


class ServiceArea(db.Model):
    __tablename__ = "service_areas"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), unique=True, nullable=False)
    is_active = db.Column(db.Boolean, nullable=False, default=True)
    sort_order = db.Column(db.Integer, default=0)

    # Who created this Service Area, and what role they held at the time —
    # used to control who's allowed to rename/delete it later.
    created_by_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    created_by_role = db.Column(db.String(20), nullable=True)
    creator = db.relationship("User", foreign_keys=[created_by_id])

    assigned_by_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    assigned_by_role = db.Column(db.String(20), nullable=True)
    assigner = db.relationship("User", foreign_keys=[assigned_by_id])


class QuarterServiceArea(db.Model):
    """
    Tracks which Service Areas (from the master ServiceArea list) apply to
    a specific quarter of a specific year. This lets Q1 2026 have a
    different set of service areas than Q2 2026, instead of every quarter
    always showing the same fixed list.
    """
    __tablename__ = "quarter_service_areas"

    id = db.Column(db.Integer, primary_key=True)
    year = db.Column(db.Integer, nullable=False)
    quarter = db.Column(db.String(5), nullable=False)
    service_area = db.Column(db.String(120), nullable=False)

    __table_args__ = (
        db.UniqueConstraint(
            "year", "quarter", "service_area",
            name="uq_quarter_service_area"
        ),
    )

def get_wing_owner_id(user):
    """
    Returns the id of the manager who owns this user's Service Area 'wing'.
    - A manager owns their own wing.
    - Staff (or anyone below manager) walk up the manager_id chain until
      they hit a manager, and inherit that manager's wing.
    - Returns None if no manager is found in the chain (e.g. unassigned staff).
    """
    if user.role == "manager":
        return user.id
    node = user
    seen = {user.id}
    while node.manager_id:
        node = User.query.get(node.manager_id)
        if node is None or node.id in seen:
            break
        seen.add(node.id)
        if node.role == "manager":
            return node.id
    return None


def visible_service_area_owner_ids(user):
    """
    Returns the list of manager-ids (the 'wing owners') whose Service Areas
    `user` is allowed to see, or None if `user` should see all Service Areas
    (admin, vp, director — anyone above manager level).
    - A manager only sees their own wing.
    - Staff/anyone below manager sees the wing of the manager they report up to.
    """
    if user.role in ("admin", "vp", "director"):
        return None
    owner_id = get_wing_owner_id(user)
    return [owner_id]