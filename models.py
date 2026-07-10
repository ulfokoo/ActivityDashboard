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

    # "admin" or "staff"
    role = db.Column(db.String(20), nullable=False, default="staff")

    # Self-registered accounts start unapproved and can't log in until an
    # admin approves them.
    is_approved = db.Column(db.Boolean, nullable=False, default=False)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def set_password(self, raw_password: str):
        self.password_hash = generate_password_hash(raw_password)

    def check_password(self, raw_password: str) -> bool:
        return check_password_hash(self.password_hash, raw_password)

    @property
    def is_admin(self) -> bool:
        return self.role == "admin"


# ---------------------------------------------------------------------------
# These three helpers reproduce, cell-for-cell, the formulas that used to
# live in columns C, D, E, F, G, U of the "Activity Log" sheet:
#   Day      =TEXT(date,"dddd")
#   Week     ="W"&MIN(4,ROUNDUP(DAY(date)/7,0))
#   Month    =TEXT(date,"mmmm")
#   Quarter  ="Q"&(INT(MOD(MONTH(date)-7,12)/3)+1)      -> fiscal Q1=Jul-Sep
#   Year     =YEAR(date)
#   FiscalYr =YEAR(date)-IF(MONTH(date)<7,1,0)
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
    doc_link = db.Column(db.String(500))
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
