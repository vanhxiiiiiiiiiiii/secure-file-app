import base64
import hashlib
import io
from datetime import datetime
from pathlib import Path

from cryptography.exceptions import InvalidTag
from flask import (
    Blueprint,
    abort,
    current_app,
    flash,
    redirect,
    render_template,
    request,
    send_file,
    url_for,
)
from flask_login import current_user, login_required
from werkzeug.utils import secure_filename

from database import db
from models.file import File
from models.file_access import FileAccess
from models.user import User
from services.file_crypto import decrypt_file_data, encrypt_file_data, generate_dek
from services.kms_client import SKLMError


files_bp = Blueprint("files", __name__)


def _kms_client():
    return current_app.extensions["sklm_client"]


def _require_kms_configuration():
    client = _kms_client()
    kek_id = current_app.config.get("SKLM_KEK_ID")
    if not client.configured:
        raise SKLMError("SKLM service credentials are not configured")
    if not kek_id:
        raise SKLMError("SKLM_KEK_ID is not configured")
    return client, kek_id


@files_bp.route("/files")
@login_required
def files():
    user_files = (
        File.query.filter_by(owner_id=current_user.id)
        .order_by(File.created_at.desc())
        .all()
    )
    return render_template("files.html", files=user_files)


@files_bp.route("/upload", methods=["GET", "POST"])
@login_required
def upload():
    if request.method == "GET":
        return render_template("upload.html")

    uploaded_file = request.files.get("file")
    if uploaded_file is None:
        flash("Không nhận được file.", "error")
        return redirect(url_for("files.upload"))
    if not uploaded_file.filename:
        flash("Vui lòng chọn file.", "error")
        return redirect(url_for("files.upload"))

    original_filename = secure_filename(uploaded_file.filename)
    if not original_filename:
        flash("Tên file không hợp lệ.", "error")
        return redirect(url_for("files.upload"))

    try:
        plaintext = uploaded_file.read()
    except Exception:
        flash("Không thể đọc file.", "error")
        return redirect(url_for("files.upload"))

    if not plaintext:
        flash("File rỗng.", "error")
        return redirect(url_for("files.upload"))

    file_size = len(plaintext)
    if file_size > current_app.config["MAX_CONTENT_LENGTH"]:
        flash("File vượt quá giới hạn cho phép.", "error")
        return redirect(url_for("files.upload"))

    plaintext_sha256 = hashlib.sha256(plaintext).hexdigest()
    extension = Path(original_filename).suffix.lower()

    storage_dir = Path(current_app.config["FILE_STORAGE_PATH"])
    storage_dir.mkdir(parents=True, exist_ok=True)

    file_record = File(
        owner_id=str(current_user.id),
        original_filename=original_filename,
        stored_filename="pending.enc",
        storage_path="pending",
        file_size=file_size,
        mime_type=uploaded_file.mimetype or "application/octet-stream",
        file_extension=extension,
        sha256_hash=plaintext_sha256,
    )
    stored_filename = f"{file_record.id}.enc"
    save_path = storage_dir / stored_filename
    file_record.stored_filename = stored_filename
    file_record.storage_path = str(save_path)
    file_record.created_at = datetime.utcnow()

    dek = None
    try:
        client, kek_id = _require_kms_configuration()

        dek = generate_dek()
        ciphertext, nonce = encrypt_file_data(plaintext, dek)
        wrapped = client.wrap_key(kek_ref=kek_id, key_material=dek)

        save_path.write_bytes(ciphertext)

        file_record.encryption_status = "encrypted"
        file_record.encryption_algorithm = "AES-256-GCM"
        file_record.kms_key_id = wrapped["kek_id"]
        file_record.kms_key_version = str(wrapped["kek_version"])
        file_record.wrapped_dek = wrapped["wrapped_key_b64"]
        file_record.encryption_nonce = base64.b64encode(nonce).decode("ascii")
        file_record.key_wrap_algorithm = wrapped.get("scheme", "AES-KW-RFC3394")
        file_record.ciphertext_sha256 = hashlib.sha256(ciphertext).hexdigest()

        db.session.add(file_record)
        db.session.commit()

        flash("Upload và mã hóa file thành công.", "success")
        return redirect(url_for("files.files"))

    except SKLMError:
        db.session.rollback()
        if save_path.exists():
            save_path.unlink(missing_ok=True)
        flash("Không thể mã hóa file vì dịch vụ quản lý khóa chưa sẵn sàng.", "error")
        return redirect(url_for("files.upload"))
    except Exception:
        db.session.rollback()
        if save_path.exists():
            save_path.unlink(missing_ok=True)
        flash("Upload hoặc mã hóa file thất bại.", "error")
        return redirect(url_for("files.upload"))
    finally:
        dek = None
        plaintext = None


@files_bp.route("/files/<file_id>/download")
@login_required
def download_file(file_id):
    file = db.session.get(File, file_id)
    if file is None:
        abort(404)

    if str(file.owner_id) == str(current_user.id):
        allowed = True
    else:
        access = FileAccess.query.filter_by(
            file_id=file.id, user_id=current_user.id
        ).first()
        allowed = access is not None

    if not allowed:
        abort(403)

    file_path = Path(file.storage_path)
    if not file_path.exists():
        abort(404)

    if file.encryption_status != "encrypted":
        return send_file(
            file_path,
            as_attachment=True,
            download_name=file.original_filename,
            mimetype=file.mime_type,
        )

    if not all(
        [
            file.kms_key_id,
            file.kms_key_version,
            file.wrapped_dek,
            file.encryption_nonce,
        ]
    ):
        abort(500, description="Encrypted file metadata is incomplete")

    ciphertext = file_path.read_bytes()
    if file.ciphertext_sha256:
        actual_ciphertext_hash = hashlib.sha256(ciphertext).hexdigest()
        if actual_ciphertext_hash != file.ciphertext_sha256:
            abort(500, description="Encrypted file integrity check failed")

    try:
        dek = _kms_client().unwrap_key(
            kek_ref=file.kms_key_id,
            kek_version=int(file.kms_key_version),
            wrapped_key_b64=file.wrapped_dek,
        )
        nonce = base64.b64decode(file.encryption_nonce, validate=True)
        plaintext = decrypt_file_data(ciphertext, dek, nonce)
    except (SKLMError, ValueError, InvalidTag):
        abort(502, description="Unable to decrypt file")

    if file.sha256_hash and hashlib.sha256(plaintext).hexdigest() != file.sha256_hash:
        abort(500, description="Decrypted file integrity check failed")

    return send_file(
        io.BytesIO(plaintext),
        as_attachment=True,
        download_name=file.original_filename,
        mimetype=file.mime_type,
    )


@files_bp.route("/files/<file_id>/share", methods=["GET", "POST"])
@login_required
def share_file(file_id):
    file = db.session.get(File, file_id)
    if file is None:
        abort(404)

    if str(file.owner_id) != str(current_user.id):
        flash("Chỉ chủ file mới có quyền chia sẻ.", "error")
        return redirect(url_for("files.files"))

    if request.method == "GET":
        return render_template("share_file.html", file=file)

    username = request.form.get("username", "").strip()
    if not username:
        flash("Vui lòng nhập username.", "error")
        return redirect(url_for("files.share_file", file_id=file.id))

    user = User.query.filter_by(username=username).first()
    if user is None:
        flash("Không tìm thấy người dùng.", "error")
        return redirect(url_for("files.share_file", file_id=file.id))

    if str(user.id) == str(current_user.id):
        flash("Bạn không thể chia sẻ file cho chính mình.", "error")
        return redirect(url_for("files.share_file", file_id=file.id))

    existing = FileAccess.query.filter_by(file_id=file.id, user_id=user.id).first()
    if existing:
        flash("File đã được chia sẻ cho người dùng này.", "error")
        return redirect(url_for("files.share_file", file_id=file.id))

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
    except Exception:
        db.session.rollback()
        flash("Chia sẻ file thất bại.", "error")
        return redirect(url_for("files.share_file", file_id=file.id))

    flash("Chia sẻ file thành công.", "success")
    return redirect(url_for("files.files"))
