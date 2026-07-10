from flask_wtf import FlaskForm
from wtforms import (
    StringField, TextAreaField, DateField, FloatField,
    SelectField, SubmitField, PasswordField, BooleanField,
)
from wtforms.validators import DataRequired, Optional, Length, Email, EqualTo

import config
from models import ServiceArea


def _choices(options):
    return [(o, o) for o in options]
def _active_service_area_choices():
    areas = ServiceArea.query.filter_by(is_active=True).order_by(ServiceArea.sort_order, ServiceArea.name).all()
    return [(a.name, a.name) for a in areas]


class RegisterForm(FlaskForm):
    full_name = StringField("Full Name", validators=[DataRequired(), Length(max=120)])
    email = StringField("Email", validators=[DataRequired(), Email(), Length(max=120)])
    password = PasswordField("Password", validators=[DataRequired(), Length(min=8)])
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


class ActivityForm(FlaskForm):
    date = DateField("Date", validators=[DataRequired()])

    service_area = SelectField("Service Area", validators=[DataRequired()])

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.service_area.choices = _active_service_area_choices()
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
    doc_link = StringField("Document / Reference Link", validators=[Optional(), Length(max=500)])
    result_outcome = TextAreaField("Result / Outcome", validators=[Optional()])
    financial_result = FloatField("Financial Result (ETB)", validators=[Optional()], default=0)
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