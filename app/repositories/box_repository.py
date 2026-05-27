from __future__ import annotations

from app.core.platform_patch import patch_platform_wmi

patch_platform_wmi()

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session, selectinload

from app.models import AirWaybill, Box, BoxDocument, BoxItem, WarehouseReceipt, WaybillPrebooking


class BoxRepository:
    def __init__(self, db: Session):
        self.db = db

    def list_by_waybill(self, waybill_id: int) -> list[Box]:
        return list(
            self.db.scalars(
                select(Box)
                .join(WarehouseReceipt, WarehouseReceipt.id == Box.warehouse_receipt_id)
                .options(selectinload(Box.document), selectinload(Box.warehouse_receipt), selectinload(Box.items))
                .where(WarehouseReceipt.waybill_id == waybill_id)
                .order_by(WarehouseReceipt.id, Box.source_row_number, Box.id)
            )
        )

    def list_by_prebooking(self, prebooking_id: int) -> list[Box]:
        return list(
            self.db.scalars(
                select(Box)
                .join(WarehouseReceipt, WarehouseReceipt.id == Box.warehouse_receipt_id)
                .options(selectinload(Box.document), selectinload(Box.warehouse_receipt), selectinload(Box.items))
                .where(WarehouseReceipt.prebooking_id == prebooking_id)
                .order_by(WarehouseReceipt.id, Box.source_row_number, Box.id)
            )
        )

    def get_by_waybill(self, waybill_id: int, box_id: int) -> Box | None:
        return self.db.scalar(
            select(Box)
            .join(WarehouseReceipt, WarehouseReceipt.id == Box.warehouse_receipt_id)
            .options(selectinload(Box.document), selectinload(Box.warehouse_receipt), selectinload(Box.items))
            .where(WarehouseReceipt.waybill_id == waybill_id, Box.id == box_id)
        )

    def get_by_prebooking(self, prebooking_id: int, box_id: int) -> Box | None:
        return self.db.scalar(
            select(Box)
            .join(WarehouseReceipt, WarehouseReceipt.id == Box.warehouse_receipt_id)
            .options(selectinload(Box.document), selectinload(Box.warehouse_receipt), selectinload(Box.items))
            .where(WarehouseReceipt.prebooking_id == prebooking_id, Box.id == box_id)
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

    def add_items(self, items: list[BoxItem]) -> None:
        self.db.add_all(items)

    def get_by_id(self, box_id: int) -> Box | None:
        return self.db.scalar(
            select(Box)
            .options(selectinload(Box.document), selectinload(Box.warehouse_receipt), selectinload(Box.items))
            .where(Box.id == box_id)
        )

    def list_by_ids(self, box_ids: list[int]) -> list[Box]:
        if not box_ids:
            return []
        return list(
            self.db.scalars(
                select(Box)
                .options(selectinload(Box.document), selectinload(Box.warehouse_receipt), selectinload(Box.items))
                .where(Box.id.in_(box_ids))
                .order_by(Box.box_no)
            )
        )

    def get_by_box_no(self, box_no: str) -> Box | None:
        return self.db.scalar(
            select(Box)
            .options(selectinload(Box.document), selectinload(Box.warehouse_receipt), selectinload(Box.items))
            .where(Box.box_no == box_no)
        )

    def list_by_box_nos(self, box_nos: list[str]) -> list[Box]:
        if not box_nos:
            return []
        return list(
            self.db.scalars(
                select(Box)
                .options(selectinload(Box.document), selectinload(Box.warehouse_receipt), selectinload(Box.items))
                .where(Box.box_no.in_(box_nos))
            )
        )

    def list_unbound(self, *, page: int, page_size: int) -> tuple[list[Box], int]:
        query = select(Box).where(Box.warehouse_receipt_id.is_(None))
        total = self.db.scalar(select(func.count()).select_from(query.subquery())) or 0
        items = list(
            self.db.scalars(
                query.options(selectinload(Box.document), selectinload(Box.items))
                .order_by(Box.updated_at.desc(), Box.id.desc())
                .offset((page - 1) * page_size)
                .limit(page_size)
            )
        )
        return items, int(total)

    def list_receipts(
        self,
        *,
        page: int,
        page_size: int,
        unbound_only: bool = False,
    ) -> tuple[list[tuple[WarehouseReceipt, str | None, WaybillPrebooking | None, str | None, int]], int]:
        stmt = (
            select(
                WarehouseReceipt,
                AirWaybill.waybill_no,
                WaybillPrebooking,
                BoxDocument.file_name,
                func.count(Box.id).label("box_count"),
            )
            .outerjoin(AirWaybill, AirWaybill.id == WarehouseReceipt.waybill_id)
            .outerjoin(WaybillPrebooking, WaybillPrebooking.id == WarehouseReceipt.prebooking_id)
            .outerjoin(BoxDocument, BoxDocument.id == WarehouseReceipt.source_document_id)
            .outerjoin(Box, Box.warehouse_receipt_id == WarehouseReceipt.id)
            .group_by(WarehouseReceipt.id, AirWaybill.waybill_no, WaybillPrebooking.id, BoxDocument.file_name)
            .order_by(WarehouseReceipt.updated_at.desc(), WarehouseReceipt.id.desc())
        )
        if unbound_only:
            stmt = stmt.where(WarehouseReceipt.waybill_id.is_(None), WarehouseReceipt.prebooking_id.is_(None))
        total_stmt = select(func.count()).select_from(stmt.order_by(None).subquery())
        total = int(self.db.scalar(total_stmt) or 0)
        rows = self.db.execute(stmt.offset((page - 1) * page_size).limit(page_size)).all()
        return [(row[0], row[1], row[2], row[3], int(row[4] or 0)) for row in rows], total

    def list_by_receipt_id(self, receipt_id: int) -> list[Box]:
        return list(
            self.db.scalars(
                select(Box)
                .options(selectinload(Box.document), selectinload(Box.warehouse_receipt), selectinload(Box.items))
                .where(Box.warehouse_receipt_id == receipt_id)
                .order_by(Box.source_row_number, Box.id)
            )
        )

    def get_receipt_by_warehouse_no(self, warehouse_no: str) -> WarehouseReceipt | None:
        return self.db.scalar(select(WarehouseReceipt).where(WarehouseReceipt.warehouse_no == warehouse_no))

    def get_receipt_by_id(self, receipt_id: int) -> WarehouseReceipt | None:
        return self.db.scalar(select(WarehouseReceipt).where(WarehouseReceipt.id == receipt_id))

    def get_receipt_for_waybill(self, waybill_id: int) -> WarehouseReceipt | None:
        return self.db.scalar(select(WarehouseReceipt).where(WarehouseReceipt.waybill_id == waybill_id))

    def add_receipt(self, receipt: WarehouseReceipt) -> WarehouseReceipt:
        self.db.add(receipt)
        self.db.flush()
        return receipt

    def delete_receipt(self, receipt: WarehouseReceipt) -> None:
        self.db.delete(receipt)

    def delete_items_for_box(self, box_id: int) -> int:
        result = self.db.execute(delete(BoxItem).where(BoxItem.box_id == box_id))
        return int(result.rowcount or 0)

    def list_conflicting_boxes(self, box_nos: list[str], target_warehouse_no: str) -> list[tuple[Box, AirWaybill | None, WarehouseReceipt | None]]:
        if not box_nos:
            return []
        rows = self.db.execute(
            select(Box, AirWaybill, WarehouseReceipt)
            .join(WarehouseReceipt, WarehouseReceipt.id == Box.warehouse_receipt_id)
            .outerjoin(AirWaybill, AirWaybill.id == WarehouseReceipt.waybill_id)
            .where(Box.box_no.in_(box_nos), WarehouseReceipt.warehouse_no != target_warehouse_no)
        )
        return [(box, waybill, receipt) for box, waybill, receipt in rows]
