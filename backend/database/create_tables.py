from database.database import engine, Base, SessionLocal
from models.users import User
from models.audit_trail import AuditTrail  # noqa: F401  (register table with Base.metadata)


def create_tables() -> None:
    Base.metadata.create_all(bind=engine)


def insert_admin_user() -> None:
    db = SessionLocal()

    try:
        existing_admin = (
            db.query(User)
            .filter(User.username == "admin")
            .first()
        )

        if existing_admin:
            print("Admin user already exists")
            return

        admin_user = User(
            username="admin",
            password="admin123",  # hash this in production
        )

        db.add(admin_user)
        db.commit()

        print("Admin user created")

    finally:
        db.close()


if __name__ == "__main__":
    create_tables()
    insert_admin_user()
    print("Tables created")
