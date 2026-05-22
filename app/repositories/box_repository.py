from __future__ import annotations

from app.core.platform_patch import patch_platform_wmi

patch_platform_wmi()

from sqlalchemy import delete, select
from sqlalchemy.orm import Session, selectinload

from app.models import Box, BoxDocument


class BoxRepository:
    def __init__(self, db: Session):
        self.db = db

    def list_by_waybill(self, waybill_id: int) -> list[Box]:
        return list(
            self.db.scalars(
                select(Box)
                .options(selectinload(Box.document))
                .where(Box.current_waybill_id == waybill_id)
                .order_by(Box.source_row_number, Box.id)
            )
        )

    def delete_by_waybill(self, waybill_id: int) -> int:
        result = self.db.execute(delete(Box).where(Box.current_waybill_id == waybill_id))
        return int(result.rowcount or 0)

    def add_document(self, document: BoxDocument) -> BoxDocument:
        self.db.add(document)
        self.db.flush()
        return document

    def add_boxes(self, boxes: list[Box]) -> None:
        self.db.add_all(boxes)
