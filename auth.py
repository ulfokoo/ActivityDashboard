"""
auth.py
-------
Handles user accounts:
  - Self-registration (new accounts are created but marked "pending" —
    they cannot log in until an admin approves them)
  - Login / logout
  - An admin-only "Manage Users" screen to approve/reject pending accounts
    and promote/demote staff <-> admin.
"""
from functools import wraps

from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import (
    login_user, logout_user, login_required, current_user,
)

from models import db, User
from forms import RegisterForm, LoginForm

auth_bp = Blueprint("auth", __name__)


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
            role="staff",       # self-registered accounts are always staff
            is_approved=False,  # must be approved by an admin before login
        )
        user.set_password(form.password.data)
        db.session.add(user)
        db.session.commit()

        flash(
            "Account created. An administrator needs to approve your "
            "account before you can log in.",
            "success",
        )
        return redirect(url_for("auth.login"))

    return render_template("auth/register.html", form=form)


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("dashboard"))

    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data.lower().strip()).first()

        if user is None or not user.check_password(form.password.data):
            flash("Incorrect email or password.", "danger")
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
    return render_template("auth/manage_users.html", pending=pending, approved=approved)


@auth_bp.route("/admin/users/<int:user_id>/approve", methods=["POST"])
@login_required
@admin_required
def approve_user(user_id):
    user = User.query.get_or_404(user_id)
    user.is_approved = True
    db.session.commit()
    flash(f"{user.full_name} has been approved and can now log in.", "success")
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
