from fastapi import APIRouter, Depends, Response

from app.core.platform_patch import patch_platform_wmi

patch_platform_wmi()

from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.database import get_db
from app.schemas.board import BoardCreate, BoardOut, BoardUpdate, BoardWaybillBindRequest
from app.schemas.common import PageResponse
from app.services.board_service import BoardService

router = APIRouter(prefix="/boards", tags=["boards"])


@router.get("", response_model=PageResponse[BoardOut])
def list_boards(
    page: int = 1,
    page_size: int = 20,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    items, total, page, page_size = BoardService(db).list(page=page, page_size=page_size, current_user=current_user)
    return PageResponse(items=items, total=total, page=page, page_size=page_size)


@router.post("", response_model=BoardOut)
def create_board(
    payload: BoardCreate,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return BoardService(db).create(payload, current_user)


@router.get("/{board_id}", response_model=BoardOut)
def get_board(
    board_id: int,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return BoardService(db).get(board_id, current_user)


@router.patch("/{board_id}", response_model=BoardOut)
def update_board(
    board_id: int,
    payload: BoardUpdate,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return BoardService(db).update(board_id, payload, current_user)


@router.post("/{board_id}/waybills", response_model=BoardOut)
def add_board_waybills(
    board_id: int,
    payload: BoardWaybillBindRequest,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return BoardService(db).add_waybills(board_id, payload.waybill_nos, current_user)


@router.delete("/{board_id}/waybills/{waybill_id}", status_code=204)
def remove_board_waybill(
    board_id: int,
    waybill_id: int,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    BoardService(db).remove_waybill(board_id, waybill_id, current_user)
    return Response(status_code=204)


@router.delete("/{board_id}", status_code=204)
def delete_board(
    board_id: int,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    BoardService(db).delete(board_id, current_user)
    return Response(status_code=204)
