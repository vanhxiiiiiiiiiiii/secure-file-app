from database import db


class FileAccess(db.Model):
    __tablename__ = "file_access"

    file_id = db.Column(db.String(36), db.ForeignKey("files.id"), primary_key=True)

    user_id = db.Column(db.String(36), db.ForeignKey("users.id"), primary_key=True)

    access_level = db.Column(db.String(20), nullable=False)

    granted_by = db.Column(db.String(36), db.ForeignKey("users.id"))

    granted_at = db.Column(db.DateTime)

    expires_at = db.Column(db.DateTime)
