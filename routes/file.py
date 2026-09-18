import uuid

from database import db


class File(db.Model):
    __tablename__ = "files"

    id = db.Column(db.String(36), primary_key=True)

    owner_id = db.Column(db.String(36), db.ForeignKey("users.id"), nullable=False)

    original_filename = db.Column(db.String(255), nullable=False)

    stored_filename = db.Column(db.String(255), nullable=False)

    storage_path = db.Column(db.String(500), nullable=False)

    file_size = db.Column(db.BigInteger, nullable=False)

    mime_type = db.Column(db.String(100))

    file_extension = db.Column(db.String(20))

    sha256_hash = db.Column(db.String(64))

    status = db.Column(db.String(30), nullable=False)

    encryption_status = db.Column(db.String(30), nullable=False)

    encryption_algorithm = db.Column(db.String(50))

    kms_key_id = db.Column(db.String(255))

    kms_key_version = db.Column(db.String(100))

    created_at = db.Column(db.DateTime, nullable=False)

    owner = db.relationship("User", foreign_keys=[owner_id])
