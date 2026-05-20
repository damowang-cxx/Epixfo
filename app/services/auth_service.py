from datetime import timedelta

from app.core.platform_patch import patch_platform_wmi

patch_platform_wmi()

from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.exceptions import bad_request, unauthorized
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_signed_token,
    hash_token,
    verify_password,
)
from app.models import User, UserLoginLog, UserRefreshToken
from app.repositories.user_repository import UserRepository
from app.services.permission_service import PermissionService
from app.utils.datetime_utils import utc_now


class AuthService:
    def __init__(self, db: Session):
        self.db = db
        self.users = UserRepository(db)

    def login(self, username: str, password: str, ip_address: str | None, user_agent: str | None) -> tuple[str, str, User]:
        user = self.users.get_by_username(username)
        if user is None or not user.is_active or not verify_password(password, user.password_hash):
            raise unauthorized("Invalid username or password")
        roles = sorted(PermissionService.role_codes(user))
        access_token = create_access_token(user.id, roles)
        refresh_token = create_refresh_token(user.id)
        refresh_payload = decode_signed_token(refresh_token, "refresh")
        if refresh_payload is None:
            raise bad_request("Could not create refresh token")
        self.db.add(
            UserRefreshToken(
                user_id=user.id,
                token_hash=hash_token(refresh_token),
                expires_at=utc_now() + timedelta(days=settings.refresh_token_expire_days),
                ip_address=ip_address,
                user_agent=user_agent,
            )
        )
        user.last_login_at = utc_now()
        user.last_seen_at = utc_now()
        self.db.add(UserLoginLog(user_id=user.id, ip_address=ip_address, user_agent=user_agent))
        self.db.commit()
        self.db.refresh(user)
        return access_token, refresh_token, user

    def refresh(self, refresh_token: str) -> tuple[str, str, User]:
        payload = decode_signed_token(refresh_token, "refresh")
        if payload is None:
            raise unauthorized("Invalid refresh token")
        record = self.users.get_refresh_token_by_hash(hash_token(refresh_token))
        if record is None or record.revoked_at is not None or record.expires_at < utc_now():
            raise unauthorized("Invalid refresh token")
        user = self.users.get(int(payload["sub"]))
        if user is None or not user.is_active:
            raise unauthorized("User is disabled")
        record.revoked_at = utc_now()
        roles = sorted(PermissionService.role_codes(user))
        access_token = create_access_token(user.id, roles)
        new_refresh_token = create_refresh_token(user.id)
        self.db.add(
            UserRefreshToken(
                user_id=user.id,
                token_hash=hash_token(new_refresh_token),
                expires_at=utc_now() + timedelta(days=settings.refresh_token_expire_days),
            )
        )
        self.db.commit()
        return access_token, new_refresh_token, user

    def logout(self, refresh_token: str, user: User) -> None:
        record = self.users.get_refresh_token_by_hash(hash_token(refresh_token))
        if record is not None and record.user_id == user.id and record.revoked_at is None:
            record.revoked_at = utc_now()
        self.db.query(UserLoginLog).filter(
            UserLoginLog.user_id == user.id,
            UserLoginLog.logout_at.is_(None),
        ).update({"logout_at": utc_now()})
        self.db.commit()
