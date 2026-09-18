import hashlib
import uuid
from datetime import datetime
from pathlib import Path

from flask import (
    Blueprint,
    render_template,
    request,
    redirect,
    url_for,
    flash,
    abort,
    send_file,
    current_app,
)

from flask_login import login_required, current_user
from werkzeug.utils import secure_filename

from database import db
from models.file import File
from models.file_access import FileAccess
from models.user import User


files_bp = Blueprint("files", __name__)


# =========================================================
# MY FILES
# =========================================================


@files_bp.route("/files")
@login_required
def files():

    user_files = (
        File.query.filter_by(owner_id=current_user.id)
        .order_by(File.created_at.desc())
        .all()
    )

    return render_template("files.html", files=user_files)


# =========================================================
# UPLOAD
# =========================================================


@files_bp.route("/upload", methods=["GET", "POST"])
@login_required
def upload():

    # GET
    if request.method == "GET":
        return render_template("upload.html")

    # -----------------------------------------------------
    # 1. Kiểm tra file
    # -----------------------------------------------------

    uploaded_file = request.files.get("file")

    if uploaded_file is None:
        flash("Không nhận được file.", "error")

        return redirect(url_for("files.upload"))

    if not uploaded_file.filename:
        flash("Vui lòng chọn file.", "error")

        return redirect(url_for("files.upload"))

    # -----------------------------------------------------
    # 2. Làm sạch tên file
    # -----------------------------------------------------

    original_filename = secure_filename(uploaded_file.filename)

    if not original_filename:
        flash("Tên file không hợp lệ.", "error")

        return redirect(url_for("files.upload"))

    # -----------------------------------------------------
    # 3. Đọc dữ liệu
    # -----------------------------------------------------

    try:
        data = uploaded_file.read()

    except Exception as e:
        flash(f"Không thể đọc file: {e}", "error")

        return redirect(url_for("files.upload"))

    if not data:
        flash("File rỗng.", "error")

        return redirect(url_for("files.upload"))

    # -----------------------------------------------------
    # 4. Kiểm tra kích thước
    # -----------------------------------------------------

    file_size = len(data)

    max_size = 50 * 1024 * 1024

    if file_size > max_size:
        flash("File vượt quá giới hạn 50 MB.", "error")

        return redirect(url_for("files.upload"))

    # -----------------------------------------------------
    # 5. SHA-256
    # -----------------------------------------------------

    sha256_hash = hashlib.sha256(data).hexdigest()

    # -----------------------------------------------------
    # 6. Extension
    # -----------------------------------------------------

    extension = Path(original_filename).suffix.lower()

    # -----------------------------------------------------
    # 7. Tạo tên file lưu trên server
    # -----------------------------------------------------

    file_id = str(uuid.uuid4())

    stored_filename = file_id + extension

    # -----------------------------------------------------
    # 8. Storage
    # -----------------------------------------------------

    storage_dir = Path(current_app.config["FILE_STORAGE_PATH"])

    storage_dir.mkdir(parents=True, exist_ok=True)

    save_path = storage_dir / stored_filename

    # -----------------------------------------------------
    # 9. Lưu file + database
    # -----------------------------------------------------

    try:
        # Lưu file vật lý
        save_path.write_bytes(data)

        # Tạo record
        file_record = File(
            owner_id=str(current_user.id),
            original_filename=(original_filename),
            stored_filename=(stored_filename),
            storage_path=str(save_path),
            file_size=file_size,
            mime_type=(uploaded_file.mimetype or "application/octet-stream"),
            file_extension=extension,
            sha256_hash=sha256_hash,
        )

        # Thời gian tạo
        file_record.created_at = datetime.utcnow()

        # Thêm DB
        db.session.add(file_record)

        db.session.commit()

        flash("Upload file thành công.", "success")

        return redirect(url_for("files.files"))

    except Exception as e:
        # Rollback DB
        db.session.rollback()

        # Xóa file nếu DB INSERT thất bại
        if save_path.exists():
            try:
                save_path.unlink()
            except Exception:
                pass

        print()
        print("=" * 70)
        print("UPLOAD ERROR")
        print("=" * 70)
        print("Type:", type(e).__name__)
        print("Message:", str(e))
        print("=" * 70)
        print()

        flash(f"Upload lỗi: {str(e)}", "error")

        return redirect(url_for("files.upload"))


# =========================================================
# DOWNLOAD
# =========================================================


@files_bp.route("/files/<file_id>/download")
@login_required
def download_file(file_id):

    file = db.session.get(File, file_id)

    if file is None:
        abort(404)

    # -----------------------------------------------------
    # Owner
    # -----------------------------------------------------

    if str(file.owner_id) == str(current_user.id):
        allowed = True

    else:
        # -------------------------------------------------
        # Người được share
        # -------------------------------------------------

        access = FileAccess.query.filter_by(
            file_id=file.id, user_id=current_user.id
        ).first()

        allowed = access is not None

    if not allowed:
        abort(403)

    # -----------------------------------------------------
    # Kiểm tra storage
    # -----------------------------------------------------

    file_path = Path(file.storage_path)

    if not file_path.exists():
        abort(404)

    # -----------------------------------------------------
    # Download
    # -----------------------------------------------------

    return send_file(
        file_path,
        as_attachment=True,
        download_name=file.original_filename,
        mimetype=file.mime_type,
    )


# =========================================================
# SHARE FILE
# =========================================================


@files_bp.route("/files/<file_id>/share", methods=["GET", "POST"])
@login_required
def share_file(file_id):

    file = db.session.get(File, file_id)

    if file is None:
        abort(404)

    # -----------------------------------------------------
    # Chỉ owner được share
    # -----------------------------------------------------

    if str(file.owner_id) != str(current_user.id):
        flash("Chỉ chủ file mới có quyền chia sẻ.", "error")

        return redirect(url_for("files.files"))

    # -----------------------------------------------------
    # GET
    # -----------------------------------------------------

    if request.method == "GET":
        return render_template("share_file.html", file=file)

    # -----------------------------------------------------
    # POST
    # -----------------------------------------------------

    username = request.form.get("username", "").strip()

    if not username:
        flash("Vui lòng nhập username.", "error")

        return redirect(url_for("files.share_file", file_id=file.id))

    # -----------------------------------------------------
    # Tìm user
    # -----------------------------------------------------

    user = User.query.filter_by(username=username).first()

    if user is None:
        flash("Không tìm thấy người dùng.", "error")

        return redirect(url_for("files.share_file", file_id=file.id))

    # -----------------------------------------------------
    # Không share cho chính mình
    # -----------------------------------------------------

    if str(user.id) == str(current_user.id):
        flash("Bạn không thể chia sẻ file cho chính mình.", "error")

        return redirect(url_for("files.share_file", file_id=file.id))

    # -----------------------------------------------------
    # Kiểm tra đã share chưa
    # -----------------------------------------------------

    existing = FileAccess.query.filter_by(file_id=file.id, user_id=user.id).first()

    if existing:
        flash("File đã được chia sẻ cho người dùng này.", "error")

        return redirect(url_for("files.share_file", file_id=file.id))

    # -----------------------------------------------------
    # Tạo quyền truy cập
    # -----------------------------------------------------

    access = FileAccess(
        file_id=file.id,
        user_id=user.id,
        access_level="read",
        granted_by=current_user.id,
        granted_at=datetime.utcnow(),
    )

    try:
        db.session.add(access)

        db.session.commit()

    except Exception as e:
        db.session.rollback()

        print("SHARE ERROR:", type(e).__name__, str(e))

        flash(f"Chia sẻ lỗi: {str(e)}", "error")

        return redirect(url_for("files.share_file", file_id=file.id))

    flash("Chia sẻ file thành công.", "success")

    return redirect(url_for("files.files"))
