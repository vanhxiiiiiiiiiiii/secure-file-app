from sqlalchemy import inspect, text

from app import create_app
from database import db


COLUMNS = {
    "wrapped_dek": "TEXT NULL",
    "encryption_nonce": "VARCHAR(64) NULL",
    "key_wrap_algorithm": "VARCHAR(50) NULL",
    "ciphertext_sha256": "VARCHAR(64) NULL",
}


def main():
    app = create_app()
    with app.app_context():
        inspector = inspect(db.engine)
        existing = {column["name"] for column in inspector.get_columns("files")}

        for name, ddl in COLUMNS.items():
            if name in existing:
                print(f"skip: files.{name} already exists")
                continue
            print(f"add: files.{name}")
            db.session.execute(text(f"ALTER TABLE files ADD COLUMN {name} {ddl}"))
            db.session.commit()

        print("Envelope-encryption migration complete.")


if __name__ == "__main__":
    main()
