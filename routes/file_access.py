from flask import Blueprint, render_template

from flask_login import login_required, current_user

from database import db
from models.file import File
from models.file_access import FileAccess


file_access_bp = Blueprint("file_access", __name__)


@file_access_bp.route("/shared")
@login_required
def shared_files():

    accesses = FileAccess.query.filter_by(user_id=current_user.id).all()

    shared_files = []

    for access in accesses:
        file = db.session.get(File, access.file_id)

        if file is not None:
            shared_files.append({"file": file, "access": access})

    return render_template("shared.html", shared_files=shared_files)
