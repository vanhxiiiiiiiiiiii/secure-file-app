from database import db
import uuid


class File(db.Model):
    __tablename__ = "files"

    id = db.Column(db.String(36), primary_key=True)

    owner_id = db.Column(db.String(36), nullable=False)

    original_filename = db.Column(db.String(255), nullable=False)

    stored_filename = db.Column(db.String(255), nullable=False)

    storage_path = db.Column(db.String(500), nullable=False)

    file_size = db.Column(db.BigInteger, nullable=False)

    mime_type = db.Column(db.String(100))

    file_extension = db.Column(db.String(20))

    sha256_hash = db.Column(db.String(64))

    status = db.Column(db.String(20), nullable=False, default="active")

    encryption_status = db.Column(db.String(20), nullable=False, default="pending")

    encryption_algorithm = db.Column(db.String(50))

    kms_key_id = db.Column(db.String(255))

    kms_key_version = db.Column(db.String(100))

    created_at = db.Column(db.DateTime, nullable=False)

    def __init__(
        self,
        owner_id,
        original_filename,
        stored_filename,
        storage_path,
        file_size,
        mime_type=None,
        file_extension=None,
        sha256_hash=None,
    ):

        self.id = str(uuid.uuid4())

        self.owner_id = owner_id

        self.original_filename = original_filename

        self.stored_filename = stored_filename

        self.storage_path = storage_path

        self.file_size = file_size

        self.mime_type = mime_type

        self.file_extension = file_extension

        self.sha256_hash = sha256_hash

        self.status = "active"

        self.encryption_status = "pending"

        self.encryption_algorithm = None

        self.kms_key_id = None

        self.kms_key_version = None
