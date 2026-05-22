from __future__ import annotations

import secrets
import string
from decimal import Decimal

from fastapi import HTTPException, status

from app.core.platform_patch import patch_platform_wmi

patch_platform_wmi()

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.core.exceptions import bad_request, not_found
from app.models import AirWaybill, User, WaybillBoard
from app.models.enums import WaybillLifecycleStatus
from app.schemas.board import BoardBindError, BoardCreate, BoardUpdate
from app.services.permission_service import PermissionService
from app.utils.pagination import normalize_pagination
from app.utils.waybill_utils import normalize_waybill_no, validate_waybill_no


ALLOWED_BOARD_LIFECYCLE_STATUSES = {
    WaybillLifecycleStatus.CREATED,
    WaybillLifecycleStatus.WAITING_MONITOR,
    WaybillLifecycleStatus.MONITORING,
    WaybillLifecycleStatus.WAREHOUSE_RECEIVED,
    WaybillLifecycleStatus.LOADED,
    WaybillLifecycleStatus.DEPARTED,
    WaybillLifecycleStatus.ARRIVED,
    WaybillLifecycleStatus.PICKUP_NOTIFIED,
}

BOARD_RANDOM_ALPHABET = string.ascii_letters + string.digits


class BoardService:
    def __init__(self, db: Session):
        self.db = db

    def list(self, *, page: int, page_size: int, current_user: User) -> tuple[list[WaybillBoard], int, int, int]:
        PermissionService.assert_waybill_write(current_user)
        pagination = normalize_pagination(page, page_size)
        query = (
            select(WaybillBoard)
            .options(selectinload(WaybillBoard.waybills))
            .order_by(WaybillBoard.created_at.desc(), WaybillBoard.id.desc())
        )
        total = int(self.db.scalar(select(func.count()).select_from(query.order_by(None).subquery())) or 0)
        items = list(self.db.scalars(query.offset(pagination.offset).limit(pagination.page_size)))
        return items, total, pagination.page, pagination.page_size

    def get(self, board_id: int, current_user: User) -> WaybillBoard:
        PermissionService.assert_waybill_write(current_user)
        board = self._get(board_id)
        if board is None:
            raise not_found("board_not_found")
        return board

    def create(self, payload: BoardCreate, current_user: User) -> WaybillBoard:
        PermissionService.assert_waybill_write(current_user)
        waybills, errors = self._load_bind_candidates(payload.waybill_nos)
        errors.extend(self._collect_bind_errors(waybills, target_board=None))
        if errors:
            self._raise_bind_errors(errors)

        board_no = self._generate_unique_board_no()
        first_waybill = waybills[0]
        board = WaybillBoard(
            board_no=board_no,
            actual_board_no=self._clean_optional_text(payload.actual_board_no),
            consignee_contact_id=first_waybill.consignee_contact_id,
            consignee_text=(first_waybill.consignee or "")[:255] or None,
            created_by=current_user.id,
            updated_by=current_user.id,
        )
        self.db.add(board)
        self.db.flush()
        for waybill in waybills:
            waybill.board_id = board.id
        self.db.commit()
        return self._get(board.id) or board

    def update(self, board_id: int, payload: BoardUpdate, current_user: User) -> WaybillBoard:
        PermissionService.assert_waybill_write(current_user)
        board = self._get(board_id)
        if board is None:
            raise not_found("board_not_found")
        board.actual_board_no = self._clean_optional_text(payload.actual_board_no)
        board.updated_by = current_user.id
        self.db.commit()
        return self._get(board.id) or board

    def add_waybills(self, board_id: int, waybill_nos: list[str], current_user: User) -> WaybillBoard:
        PermissionService.assert_waybill_write(current_user)
        board = self._get(board_id)
        if board is None:
            raise not_found("board_not_found")
        waybills, errors = self._load_bind_candidates(waybill_nos)
        errors.extend(self._collect_bind_errors(waybills, target_board=board))
        if errors:
            self._raise_bind_errors(errors)

        if board.consignee_contact_id is None and not board.waybills and waybills:
            board.consignee_contact_id = waybills[0].consignee_contact_id
            board.consignee_text = (waybills[0].consignee or "")[:255] or None
        for waybill in waybills:
            waybill.board_id = board.id
        board.updated_by = current_user.id
        self.db.commit()
        return self._get(board.id) or board

    def remove_waybill(self, board_id: int, waybill_id: int, current_user: User) -> None:
        PermissionService.assert_waybill_write(current_user)
        board = self._get(board_id)
        if board is None:
            raise not_found("board_not_found")
        waybill = self.db.scalar(select(AirWaybill).where(AirWaybill.id == waybill_id, AirWaybill.board_id == board.id))
        if waybill is None:
            raise not_found("board_waybill_not_found")
        waybill.board_id = None
        board.updated_by = current_user.id
        self.db.commit()

    def delete(self, board_id: int, current_user: User) -> None:
        PermissionService.assert_waybill_write(current_user)
        board = self._get(board_id)
        if board is None:
            raise not_found("board_not_found")
        if board.waybills:
            raise bad_request("board_not_empty")
        self.db.delete(board)
        self.db.commit()

    def _get(self, board_id: int) -> WaybillBoard | None:
        return self.db.scalar(
            select(WaybillBoard)
            .options(selectinload(WaybillBoard.waybills))
            .where(WaybillBoard.id == board_id)
        )

    def _load_bind_candidates(self, raw_waybill_nos: list[str]) -> tuple[list[AirWaybill], list[BoardBindError]]:
        waybill_nos, errors = self._normalize_waybill_nos(raw_waybill_nos)
        if not waybill_nos:
            return [], errors or [BoardBindError(waybill_no="", message="waybill_no_required")]

        rows = list(self.db.scalars(select(AirWaybill).where(AirWaybill.waybill_no.in_(waybill_nos))))
        by_no = {item.waybill_no: item for item in rows}
        candidates: list[AirWaybill] = []
        for waybill_no in waybill_nos:
            waybill = by_no.get(waybill_no)
            if waybill is None:
                errors.append(BoardBindError(waybill_no=waybill_no, message="waybill_not_found"))
            else:
                candidates.append(waybill)
        return candidates, errors

    def _collect_bind_errors(
        self,
        waybills: list[AirWaybill],
        *,
        target_board: WaybillBoard | None,
    ) -> list[BoardBindError]:
        if not waybills:
            return []
        if target_board is not None and (target_board.consignee_contact_id is not None or target_board.waybills):
            target_contact_id = target_board.consignee_contact_id
        else:
            target_contact_id = waybills[0].consignee_contact_id
        errors: list[BoardBindError] = []
        for waybill in waybills:
            if waybill.lifecycle_status not in ALLOWED_BOARD_LIFECYCLE_STATUSES:
                errors.append(BoardBindError(waybill_no=waybill.waybill_no, message="lifecycle_not_allowed"))
            if waybill.board_id is not None:
                if target_board is not None and waybill.board_id == target_board.id:
                    errors.append(BoardBindError(waybill_no=waybill.waybill_no, message="waybill_already_on_this_board"))
                else:
                    errors.append(BoardBindError(waybill_no=waybill.waybill_no, message="waybill_already_bound"))
            if waybill.consignee_contact_id != target_contact_id:
                errors.append(BoardBindError(waybill_no=waybill.waybill_no, message="consignee_mismatch"))
        return errors

    def _generate_unique_board_no(self) -> str:
        for _ in range(100):
            board_no = self._generate_board_no()
            exists = self.db.scalar(select(WaybillBoard.id).where(WaybillBoard.board_no == board_no))
            if not exists:
                return board_no
        raise bad_request("board_no_generation_failed")

    @staticmethod
    def _generate_board_no() -> str:
        suffix = "".join(secrets.choice(BOARD_RANDOM_ALPHABET) for _ in range(4))
        return f"BUP_{suffix}"

    @staticmethod
    def _normalize_waybill_nos(raw_waybill_nos: list[str]) -> tuple[list[str], list[BoardBindError]]:
        normalized: list[str] = []
        errors: list[BoardBindError] = []
        seen: set[str] = set()
        for raw in raw_waybill_nos:
            value = (raw or "").strip()
            if not value:
                continue
            waybill_no = normalize_waybill_no(value)
            if not validate_waybill_no(waybill_no):
                errors.append(BoardBindError(waybill_no=value, message="invalid_waybill_no"))
                continue
            if waybill_no not in seen:
                normalized.append(waybill_no)
                seen.add(waybill_no)
        return normalized, errors

    @staticmethod
    def _clean_optional_text(value: str | None) -> str | None:
        cleaned = (value or "").strip()
        return cleaned or None

    @staticmethod
    def _raise_bind_errors(errors: list[BoardBindError]) -> None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error_code": "board_waybill_bind_failed",
                "message": "部分提单无法绑定到板号",
                "errors": [item.model_dump() for item in errors],
            },
        )
