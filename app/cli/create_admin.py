from __future__ import annotations

import argparse

from app.core.database import SessionLocal
from app.models.enums import UserRoleCode
from app.schemas.user import UserCreate
from app.services.user_service import UserService


def main() -> None:
    parser = argparse.ArgumentParser(description="Create an administrator account.")
    parser.add_argument("--username", required=True)
    parser.add_argument("--password", required=True)
    parser.add_argument("--display-name", default="管理员")
    args = parser.parse_args()

    db = SessionLocal()
    try:
        user = UserService(db).create_user(
            UserCreate(
                username=args.username,
                password=args.password,
                display_name=args.display_name,
                role_codes=[UserRoleCode.ADMIN],
            ),
            current_user=None,
        )
        print(f"Created admin user: {user.username}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
