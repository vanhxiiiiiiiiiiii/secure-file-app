import uuid

from flask_login import UserMixin

from database import db


class User(UserMixin, db.Model):
    __tablename__ = "users"

    id = db.Column(db.String(36), primary_key=True)

    username = db.Column(db.String(50), nullable=False)

    email = db.Column(db.String(255), nullable=False)

    password_hash = db.Column(db.String(255), nullable=False)

    full_name = db.Column(db.String(100))

    status = db.Column(db.String(20), nullable=False)

    failed_login_attempts = db.Column(db.Integer, nullable=False)

    locked_until = db.Column(db.DateTime)

    last_login_at = db.Column(db.DateTime)

    last_login_ip = db.Column(db.String(45))

    password_changed_at = db.Column(db.DateTime)

    created_at = db.Column(db.DateTime, nullable=False)

    updated_at = db.Column(db.DateTime, nullable=False)

    def __init__(self, username, email, password_hash, full_name=None):

        self.id = str(uuid.uuid4())
        self.username = username
        self.email = email
        self.password_hash = password_hash
        self.full_name = full_name
        self.status = "active"
        self.failed_login_attempts = 0
