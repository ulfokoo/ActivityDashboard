"""
auth.py
-------
Handles user accounts:
  - Self-registration (new accounts are created but marked "pending" —
    they cannot log in until an admin approves them)
  - Login / logout
  - Forgot password -> admin approval -> user sets new password
  - An admin-only "Manage Users" screen to approve/reject pending accounts
    and promote/demote staff <-> admin.
"""
import os
import requests
import random
from datetime import datetime, timedelta

from flask_mail import Message
from extensions import mail
from functools import wraps

from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import (
    login_user, logout_user, login_required, current_user,
)

from models import db, User, notify_users
from forms import RegisterForm, LoginForm, OTPForm, ForgotPasswordForm, ResetPasswordForm

auth_bp = Blueprint("auth", __name__)

def _send_otp_email(user):
    """Generate a fresh 6-digit code, save it to the user, and email it."""
    code = f"{random.randint(0, 999999):06d}"
    user.otp_code = code
    user.otp_expires_at = datetime.utcnow() + timedelta(minutes=15)
    db.session.commit()

    return  # TODO: re-enable email sending once mail issue is fixed

    try:
        response = requests.post(
            "https://api.resend.com/emails",
            headers={
                "Authorization": f"Bearer {os.environ.get('RESEND_API_KEY')}",
                "Content-Type": "application/json",
            },
            json={
                "from": "onboarding@resend.dev",
                "to": [user.email],
                "subject": "Your verification code",
                "html": f"<p>Hi {user.full_name},</p><p>Your verification code is: <strong>{code}</strong></p><p>This code expires in 15 minutes.</p>",
            },
            timeout=10,
        )
        response.raise_for_status()
    except Exception as e:
        print(f"Failed to send OTP email to {user.email}: {e}")



def admin_required(view_func):
    """Restrict a route to logged-in users with the 'admin' role."""
    @wraps(view_func)
    def wrapped(*args, **kwargs):
        if not current_user.is_authenticated:
            return login_manager_unauthorized()
        if not current_user.is_admin:
            flash("That page is restricted to administrators.", "info")
            return redirect(url_for("dashboard"))
        return view_func(*args, **kwargs)
    return wrapped


def login_manager_unauthorized():
    flash("Please log in to continue.", "info")
    return redirect(url_for("auth.login"))


# ---------------------------------------------------------------------------
# Registration / Login / Logout
# ---------------------------------------------------------------------------
@auth_bp.route("/register", methods=["GET", "POST"])
def register():
    if current_user.is_authenticated:
        return redirect(url_for("dashboard"))

    form = RegisterForm()
    if form.validate_on_submit():
        existing = User.query.filter_by(email=form.email.data.lower().strip()).first()
        if existing:
            flash("An account with that email already exists.", "danger")
            return render_template("auth/register.html", form=form)

        user = User(
            full_name=form.full_name.data.strip(),
            email=form.email.data.lower().strip(),
            contact_phone=form.contact_phone.data.strip(),
            id_no=form.id_no.data.strip(),
            segment=form.segment.data.strip(),
            position=form.position.data.strip(),
            role="staff",       # self-registered accounts are always staff
            is_approved=False,  # must be approved by an admin before login
        )
        user.set_password(form.password.data)
        db.session.add(user)
        db.session.commit()

        # TEMP: skip OTP verification
        user.email_verified = True
        db.session.commit()

        flash("Account created! Waiting for admin approval.", "success")
        return redirect(url_for("auth.login"))

    return render_template("auth/register.html", form=form)

@auth_bp.route("/verify-email/<int:user_id>", methods=["GET", "POST"])
def verify_email(user_id):
    user = User.query.get_or_404(user_id)

    if user.email_verified:
        flash("Email already verified — you can log in once an admin approves your account.", "info")
        return redirect(url_for("auth.login"))

    form = OTPForm()
    if form.validate_on_submit():
        entered = form.otp_code.data.strip()

        if not user.otp_code or not user.otp_expires_at or datetime.utcnow() > user.otp_expires_at:
            flash("That code has expired. Click 'Resend code' below to get a new one.", "danger")
        elif entered != user.otp_code:
            flash("Incorrect code. Please try again.", "danger")
        else:
            user.email_verified = True
            user.otp_code = None
            user.otp_expires_at = None
            db.session.commit()
            flash("Email verified! An admin will review and approve your account before you can log in.", "success")
            return redirect(url_for("auth.login"))

    return render_template("auth/verify_email.html", user=user, form=form)


@auth_bp.route("/verify-email/<int:user_id>/resend")
def resend_otp(user_id):
    user = User.query.get_or_404(user_id)
    if user.email_verified:
        return redirect(url_for("auth.login"))
    _send_otp_email(user)
    flash("A new code has been sent to your email.", "info")
    return redirect(url_for("auth.verify_email", user_id=user.id))


# ---------------------------------------------------------------------------
# Forgot / Reset password — admin-approved flow
# ---------------------------------------------------------------------------
@auth_bp.route("/forgot-password", methods=["GET", "POST"])
def forgot_password():
    form = ForgotPasswordForm()
    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data.lower().strip()).first()
        if user:
            user.password_reset_requested = True
            user.password_reset_allowed = False
            db.session.commit()

            admin_ids = [u.id for u in User.query.filter_by(role="admin", is_approved=True).all()]
            notify_users(
                admin_ids,
                f"{user.full_name} has requested a password reset.",
                link=url_for("auth.manage_users"),
            )
            db.session.commit()

        flash("If that email is registered, your request has been sent to an admin for approval.", "info")
        return redirect(url_for("auth.login"))

    return render_template("auth/forgot_password.html", form=form)


@auth_bp.route("/reset-password/<int:user_id>", methods=["GET", "POST"])
def reset_password(user_id):
    user = User.query.get_or_404(user_id)

    if not user.password_reset_allowed:
        flash("Password reset has not been approved by an admin yet.", "info")
        return redirect(url_for("auth.login"))

    form = ResetPasswordForm()
    if form.validate_on_submit():
        user.set_password(form.password.data)
        user.password_reset_requested = False
        user.password_reset_allowed = False
        db.session.commit()
        flash("Your password has been reset. You can now log in.", "success")
        return redirect(url_for("auth.login"))

    return render_template("auth/reset_password.html", form=form, user_id=user_id)


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("dashboard"))

    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data.lower().strip()).first()

        if user is None or not user.check_password(form.password.data):
            flash("Incorrect email or password.", "danger")
        elif not user.email_verified:
            flash("Please verify your email before logging in.", "danger")
            return redirect(url_for("auth.verify_email", user_id=user.id))
        elif not user.is_approved:
            flash(
                "Your account is still pending admin approval. "
                "Please check back later.",
                "info",
            )
        else:
            login_user(user, remember=form.remember_me.data)
            flash(f"Welcome back, {user.full_name}.", "success")
            next_page = request.args.get("next")
            return redirect(next_page or url_for("dashboard"))

    return render_template("auth/login.html", form=form)


@auth_bp.route("/logout")
@login_required
def logout():
    logout_user()
    flash("You have been logged out.", "info")
    return redirect(url_for("auth.login"))


# ---------------------------------------------------------------------------
# Admin: manage users (approve / reject / change role)
# ---------------------------------------------------------------------------
@auth_bp.route("/admin/users")
@login_required
@admin_required
def manage_users():
        pending = User.query.filter_by(is_approved=False).order_by(User.created_at.desc()).all()
        approved = User.query.filter_by(is_approved=True).order_by(User.full_name).all()
        possible_managers = [u for u in approved if u.role != "staff"]
        reset_requests = User.query.filter_by(password_reset_requested=True).order_by(User.full_name).all()
        return render_template(
            "auth/manage_users.html",
            pending=pending,
            approved=approved,
            possible_managers=possible_managers,
            reset_requests=reset_requests,
        )


@auth_bp.route("/admin/users/<int:user_id>/approve", methods=["POST"])
@login_required
@admin_required
def approve_user(user_id):
    user = User.query.get_or_404(user_id)
    user.is_approved = True
    db.session.commit()
    flash(f"{user.full_name} has been approved and can now log in.", "success")
    return redirect(url_for("auth.manage_users"))
@auth_bp.route("/admin/users/<int:user_id>/update-role", methods=["POST"])
@login_required
@admin_required
def update_user_role(user_id):
        user = User.query.get_or_404(user_id)

        new_role = request.form.get("role")
        if new_role not in ("staff", "manager", "director", "vp", "admin"):
            flash("Invalid role.", "danger")
            return redirect(url_for("auth.manage_users"))

        manager_id = request.form.get("manager_id", type=int)
        if manager_id == user.id:
            flash("A user can't report to themselves.", "danger")
            return redirect(url_for("auth.manage_users"))

        user.role = new_role
        user.manager_id = manager_id if manager_id else None
        db.session.commit()
        flash(f"{user.full_name}'s role updated to {new_role}.", "success")
        return redirect(url_for("auth.manage_users"))


@auth_bp.route("/admin/users/<int:user_id>/reject", methods=["POST"])
@login_required
@admin_required
def reject_user(user_id):
    user = User.query.get_or_404(user_id)
    if user.id == current_user.id:
        flash("You can't reject your own account.", "danger")
        return redirect(url_for("auth.manage_users"))
    db.session.delete(user)
    db.session.commit()
    flash(f"{user.full_name}'s registration request has been rejected.", "info")
    return redirect(url_for("auth.manage_users"))


@auth_bp.route("/admin/users/<int:user_id>/role", methods=["POST"])
@login_required
@admin_required
def change_role(user_id):
    user = User.query.get_or_404(user_id)
    if user.id == current_user.id:
        flash("You can't change your own role.", "danger")
        return redirect(url_for("auth.manage_users"))

    new_role = request.form.get("role")
    if new_role not in ("admin", "staff"):
        flash("Invalid role.", "danger")
        return redirect(url_for("auth.manage_users"))

    user.role = new_role
    db.session.commit()
    flash(f"{user.full_name} is now {'an admin' if new_role == 'admin' else 'staff'}.", "success")
    return redirect(url_for("auth.manage_users"))


@auth_bp.route("/admin/users/<int:user_id>/remove", methods=["POST"])
@login_required
@admin_required
def remove_user(user_id):
    user = User.query.get_or_404(user_id)
    if user.id == current_user.id:
        flash("You can't remove your own account.", "danger")
        return redirect(url_for("auth.manage_users"))
    db.session.delete(user)
    db.session.commit()
    flash(f"{user.full_name}'s account has been removed.", "info")
    return redirect(url_for("auth.manage_users"))


@auth_bp.route("/admin/users/<int:user_id>/allow-reset", methods=["POST"])
@login_required
@admin_required
def allow_password_reset(user_id):
    user = User.query.get_or_404(user_id)
    user.password_reset_allowed = True
    user.password_reset_requested = False
    db.session.commit()

    notify_users(
        [user.id],
        "An admin has approved your password reset request.",
        link=url_for("auth.reset_password", user_id=user.id),
    )
    db.session.commit()

    flash(f"{user.full_name} can now reset their password.", "success")
    return redirect(url_for("auth.manage_users"))


@auth_bp.route("/admin/users/<int:user_id>/deny-reset", methods=["POST"])
@login_required
@admin_required
def deny_password_reset(user_id):
    user = User.query.get_or_404(user_id)
    user.password_reset_requested = False
    user.password_reset_allowed = False
    db.session.commit()
    flash(f"{user.full_name}'s reset request has been denied.", "info")
    return redirect(url_for("auth.manage_users"))