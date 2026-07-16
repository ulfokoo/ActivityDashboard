from flask_wtf import FlaskForm
from flask_wtf.file import FileField, FileAllowed
from wtforms import (
    StringField, TextAreaField, DateField, FloatField,
    SelectField, SubmitField, PasswordField, BooleanField,
)
from wtforms.validators import DataRequired, Optional, Length, Email, EqualTo

import config
from models import ServiceArea, visible_service_area_owner_ids, db
from datetime import date as _date
from models import ServiceArea, visible_service_area_owner_ids, db, calc_quarter, calc_fiscal_year
from flask_login import current_user
from sqlalchemy import or_


def _choices(options):
    return [(o, o) for o in options]
def _active_service_area_choices():
    q = ServiceArea.query.filter_by(is_active=True)
    if current_user.is_authenticated:
        owner_ids = visible_service_area_owner_ids(current_user)
        if owner_ids is not None:
            conds = []
            if None in owner_ids:
                conds.append(ServiceArea.created_by_id.is_(None))
            others = [o for o in owner_ids if o is not None]
            if others:
                conds.append(ServiceArea.created_by_id.in_(others))
            q = q.filter(or_(*conds)) if conds else q.filter(db.false())
    areas = q.order_by(ServiceArea.sort_order, ServiceArea.name).all()
    return [(a.name, a.name) for a in areas]


class RegisterForm(FlaskForm):
    full_name = StringField("Full Name", validators=[DataRequired(), Length(max=120)])
    email = StringField("Email", validators=[DataRequired(), Email(), Length(max=120)])
    contact_phone = StringField("Contact Phone", validators=[DataRequired(), Length(max=30)])
    id_no = StringField("ID No.", validators=[DataRequired(), Length(max=50)])
    segment = StringField("Segment", validators=[DataRequired(), Length(max=120)])
    position = StringField("Position", validators=[DataRequired(), Length(max=120)])
    code = StringField("Registration Code", validators=[DataRequired(), Length(max=20)])
    password = PasswordField("Password", validators=[DataRequired()])
    confirm_password = PasswordField(
        "Confirm Password",
        validators=[DataRequired(), EqualTo("password", message="Passwords must match.")],
    )
    submit = SubmitField("Create Account")


class LoginForm(FlaskForm):
    email = StringField("Email", validators=[DataRequired(), Email()])
    password = PasswordField("Password", validators=[DataRequired()])
    remember_me = BooleanField("Remember me")
    submit = SubmitField("Log In")


class ForgotPasswordForm(FlaskForm):
    email = StringField("Email", validators=[DataRequired(), Email()])
    submit = SubmitField("Request Password Reset")


class ResetPasswordForm(FlaskForm):
    password = PasswordField("New Password", validators=[DataRequired()])
    confirm_password = PasswordField(
        "Confirm New Password",
        validators=[DataRequired(), EqualTo("password", message="Passwords must match.")],
    )
    submit = SubmitField("Reset Password")


class ActivityForm(FlaskForm):
    date = DateField("Date", validators=[DataRequired()], default=_date.today)

    service_area = SelectField("Service Area", validators=[DataRequired()])

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        reference_date = self.date.data or _date.today()
        current_quarter = calc_quarter(reference_date)
        self.service_area.choices = _active_service_area_choices_for_quarter(current_quarter) + [("Other", "Other")]
        current = self.service_area.data
        if current and current not in dict(self.service_area.choices):
            self.service_area.choices.append((current, f"{current} (inactive)"))
    specific_activity = StringField("Specific Activity / Sub-task", validators=[Optional(), Length(max=255)])
    description = TextAreaField("Activity Description", validators=[Optional()])

    where_location = SelectField(
        "Where (Location / Platform)",
        choices=_choices(config.WHERE_OPTIONS),
        validators=[Optional()],
    )
    whom = StringField("Whom (Name & Organization)", validators=[Optional(), Length(max=255)])

    engagement_type = SelectField(
        "Engagement Type",
        choices=_choices(config.ENGAGEMENT_TYPES),
        validators=[Optional()],
    )
    document = FileField(
        "Attach Document",
        validators=[Optional(), FileAllowed(config.ALLOWED_DOCUMENT_EXTENSIONS, "Unsupported file type.")],
    )
    result_outcome = TextAreaField("Result / Outcome", validators=[Optional()])
    financial_result = FloatField("Financial Result (USD)", validators=[Optional()], default=0)
    future_plan = TextAreaField("Future Plan / Next Steps", validators=[Optional()])

    status = SelectField("Status", choices=_choices(config.STATUSES), validators=[DataRequired()])

    responsible_org = SelectField(
        "Responsible Organization",
        choices=_choices(config.RESPONSIBLE_ORGS),
        validators=[Optional()],
    )
    remarks = TextAreaField("Remarks", validators=[Optional()])

    submit = SubmitField("Save Activity")


class TargetForm(FlaskForm):
    year = SelectField("Year", choices=[(str(y), str(y)) for y in config.YEARS], validators=[DataRequired()])
    quarter = SelectField("Quarter", choices=_choices(config.QUARTERS), validators=[DataRequired()])
    service_area = SelectField("Service Area", validators=[DataRequired()])

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.service_area.choices = _active_service_area_choices()
    target_count = FloatField("Target (Count)", validators=[Optional()], default=0)
    target_etb = FloatField("Target (ETB)", validators=[Optional()], default=0)
    submit = SubmitField("Save Target")


class OTPForm(FlaskForm):
    otp_code = StringField("Verification Code", validators=[DataRequired(), Length(min=6, max=6)])
    submit = SubmitField("Verify")

class ProfilePhotoForm(FlaskForm):
    photo = FileField(
        "Profile Photo",
        validators=[Optional(), FileAllowed(["jpg", "jpeg", "png", "webp"], "Images only.")],
    )
    submit = SubmitField("Update Photo")
def _active_service_area_choices_for_quarter(quarter):
    from app import _quarter_service_areas  # lazy import, avoids circular import
    year = calc_fiscal_year(_date.today())
    names = _quarter_service_areas(
        year, quarter,
        for_user=current_user if current_user.is_authenticated else None,
    )
    return [(n, n) for n in names]