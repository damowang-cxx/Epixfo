from fastapi import APIRouter, Depends, Request

from app.core.platform_patch import patch_platform_wmi

patch_platform_wmi()

from sqlalchemy.orm import Session

from app.api.deps import client_ip, get_current_user, user_agent
from app.core.database import get_db
from app.schemas.auth import LoginRequest, LogoutRequest, MeResponse, RefreshTokenRequest, TokenResponse
from app.services.auth_service import AuthService
from app.services.permission_service import PermissionService

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=TokenResponse)
def login(payload: LoginRequest, request: Request, db: Session = Depends(get_db)) -> TokenResponse:
    access_token, refresh_token, _user = AuthService(db).login(
        payload.username,
        payload.password,
        client_ip(request),
        user_agent(request),
    )
    return TokenResponse(access_token=access_token, refresh_token=refresh_token)


@router.post("/refresh", response_model=TokenResponse)
def refresh(payload: RefreshTokenRequest, db: Session = Depends(get_db)) -> TokenResponse:
    access_token, refresh_token, _user = AuthService(db).refresh(payload.refresh_token)
    return TokenResponse(access_token=access_token, refresh_token=refresh_token)


@router.post("/logout")
def logout(
    payload: LogoutRequest,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, str]:
    AuthService(db).logout(payload.refresh_token, current_user)
    return {"status": "ok"}


@router.get("/me", response_model=MeResponse)
def me(current_user=Depends(get_current_user)) -> MeResponse:
    return MeResponse(
        id=current_user.id,
        username=current_user.username,
        display_name=current_user.display_name,
        roles=sorted(PermissionService.role_codes(current_user)),
    )
