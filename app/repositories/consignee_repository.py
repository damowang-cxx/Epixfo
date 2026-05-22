from __future__ import annotations

from app.core.platform_patch import patch_platform_wmi

patch_platform_wmi()

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models import Consignee, ConsigneeContact, ConsigneeNotifyParty


class ConsigneeRepository:
    def __init__(self, db: Session):
        self.db = db

    # ---- Consignee ----

    def list_consignees(self) -> list[Consignee]:
        return list(self.db.scalars(select(Consignee).order_by(Consignee.name)))

    def get(self, consignee_id: int) -> Consignee | None:
        return self.db.get(Consignee, consignee_id)

    def get_by_name(self, name: str) -> Consignee | None:
        return self.db.scalar(select(Consignee).where(Consignee.name == name))

    # ---- ConsigneeContact ----

    def list_contacts(self, consignee_id: int | None = None) -> list[ConsigneeContact]:
        stmt = (
            select(ConsigneeContact)
            .options(selectinload(ConsigneeContact.consignee), selectinload(ConsigneeContact.notify_party))
            .order_by(ConsigneeContact.consignee_id, ConsigneeContact.id)
        )
        if consignee_id is not None:
            stmt = stmt.where(ConsigneeContact.consignee_id == consignee_id)
        return list(self.db.scalars(stmt))

    def get_contact(self, contact_id: int) -> ConsigneeContact | None:
        return self.db.scalar(
            select(ConsigneeContact)
            .options(selectinload(ConsigneeContact.consignee), selectinload(ConsigneeContact.notify_party))
            .where(ConsigneeContact.id == contact_id)
        )

    def get_notify_party(self, contact_id: int) -> ConsigneeNotifyParty | None:
        return self.db.scalar(
            select(ConsigneeNotifyParty).where(ConsigneeNotifyParty.consignee_contact_id == contact_id)
        )
