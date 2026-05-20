from __future__ import annotations

from app.core.platform_patch import patch_platform_wmi

patch_platform_wmi()

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models import Role, User, UserRefreshToken, UserRole
from app.models.enums import UserRoleCode


class UserRepository:
    def __init__(self, db: Session):
        self.db = db

    def get(self, user_id: int) -> User | None:
        return self.db.scalar(select(User).options(selectinload(User.roles)).where(User.id == user_id))

    def get_by_username(self, username: str) -> User | None:
        return self.db.scalar(select(User).options(selectinload(User.roles)).where(User.username == username))

    def list(self, skip: int = 0, limit: int = 100) -> list[User]:
        return list(
            self.db.scalars(
                select(User).options(selectinload(User.roles)).order_by(User.id.desc()).offset(skip).limit(limit)
            )
        )

    def count(self) -> int:
        return len(list(self.db.scalars(select(User.id))))

    def get_roles(self, role_codes: list[UserRoleCode]) -> list[Role]:
        return list(self.db.scalars(select(Role).where(Role.code.in_(role_codes))))

    def set_roles(self, user: User, role_codes: list[UserRoleCode]) -> None:
        self.db.query(UserRole).filter(UserRole.user_id == user.id).delete(synchronize_session=False)
        self.db.flush()
        roles = self.get_roles(role_codes)
        for role in roles:
            self.db.add(UserRole(user_id=user.id, role_id=role.id))
        self.db.flush()

    def add_refresh_token(self, refresh_token: UserRefreshToken) -> UserRefreshToken:
        self.db.add(refresh_token)
        self.db.flush()
        return refresh_token

    def get_refresh_token_by_hash(self, token_hash: str) -> UserRefreshToken | None:
        return self.db.scalar(select(UserRefreshToken).where(UserRefreshToken.token_hash == token_hash))
