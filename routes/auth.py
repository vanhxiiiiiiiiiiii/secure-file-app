from datetime import datetime

from flask import Blueprint, render_template, request, redirect, url_for, flash

from flask_login import login_user, logout_user, login_required, current_user

from werkzeug.security import generate_password_hash, check_password_hash

from database import db
from models.user import User


auth_bp = Blueprint("auth", __name__)


@auth_bp.route("/login", methods=["GET", "POST"])
def login():

    if current_user.is_authenticated:
        return redirect(url_for("files.files"))

    if request.method == "POST":
        username = request.form.get("username", "").strip()

        password = request.form.get("password", "")

        user = User.query.filter_by(username=username).first()

        if user is None:
            flash("Tên đăng nhập hoặc mật khẩu không đúng.", "error")

            return render_template("login.html")

        if not check_password_hash(user.password_hash, password):
            flash("Tên đăng nhập hoặc mật khẩu không đúng.", "error")

            return render_template("login.html")

        if user.status != "active":
            flash("Tài khoản không hoạt động.", "error")

            return render_template("login.html")

        user.last_login_at = datetime.utcnow()

        db.session.commit()

        login_user(user)

        return redirect(url_for("files.files"))

    return render_template("login.html")


@auth_bp.route("/register", methods=["GET", "POST"])
def register():

    if current_user.is_authenticated:
        return redirect(url_for("files.files"))

    if request.method == "POST":
        username = request.form.get("username", "").strip()

        email = request.form.get("email", "").strip()

        password = request.form.get("password", "")

        full_name = request.form.get("full_name", "").strip()

        if not username or not email or not password:
            flash("Vui lòng nhập đầy đủ thông tin.", "error")

            return render_template("register.html")

        existing_user = User.query.filter(
            (User.username == username) | (User.email == email)
        ).first()

        if existing_user:
            flash("Username hoặc email đã tồn tại.", "error")

            return render_template("register.html")

        password_hash = generate_password_hash(password)

        user = User(
            username=username,
            email=email,
            password_hash=password_hash,
            full_name=full_name,
        )

        now = datetime.utcnow()

        user.created_at = now
        user.updated_at = now
        user.password_changed_at = now

        db.session.add(user)

        try:
            db.session.commit()

        except Exception as e:
            db.session.rollback()

            print("REGISTER ERROR:", repr(e))

            flash("Không thể tạo tài khoản.", "error")

            return render_template("register.html")

        flash("Đăng ký thành công.", "success")

        return redirect(url_for("auth.login"))

    return render_template("register.html")


@auth_bp.route("/logout")
@login_required
def logout():

    logout_user()

    return redirect(url_for("auth.login"))
