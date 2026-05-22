from __future__ import annotations

from app.core.platform_patch import patch_platform_wmi

patch_platform_wmi()

from sqlalchemy.orm import Session

from app.models import Consignee, ConsigneeContact, ConsigneeNotifyParty
from app.repositories.consignee_repository import ConsigneeRepository
from app.schemas.consignee import (
    ConsigneeContactCreate,
    ConsigneeContactUpdate,
    ConsigneeNotifyPartyUpsert,
    ConsigneeCreate,
    ConsigneeUpdate,
)


class ConsigneeService:
    def __init__(self, db: Session):
        self.db = db
        self.repo = ConsigneeRepository(db)

    # ---- Consignee ----

    def list_consignees(self) -> list[Consignee]:
        return self.repo.list_consignees()

    def create_consignee(self, payload: ConsigneeCreate) -> Consignee:
        consignee = Consignee(**payload.model_dump())
        self.db.add(consignee)
        self.db.commit()
        self.db.refresh(consignee)
        return consignee

    def update_consignee(self, consignee_id: int, payload: ConsigneeUpdate) -> Consignee | None:
        consignee = self.repo.get(consignee_id)
        if consignee is None:
            return None
        for key, value in payload.model_dump(exclude_unset=True).items():
            setattr(consignee, key, value)
        self.db.commit()
        self.db.refresh(consignee)
        return consignee

    # ---- ConsigneeContact ----

    def list_contacts(self, consignee_id: int | None = None) -> list[ConsigneeContact]:
        return self.repo.list_contacts(consignee_id)

    def get_contact(self, contact_id: int) -> ConsigneeContact | None:
        return self.repo.get_contact(contact_id)

    def get_notify_party(self, contact_id: int) -> ConsigneeNotifyParty | None:
        return self.repo.get_notify_party(contact_id)

    def create_contact(self, payload: ConsigneeContactCreate) -> ConsigneeContact:
        contact = ConsigneeContact(**payload.model_dump())
        self.db.add(contact)
        self.db.commit()
        self.db.refresh(contact)
        return contact

    def upsert_notify_party(
        self,
        contact_id: int,
        payload: ConsigneeNotifyPartyUpsert,
    ) -> ConsigneeNotifyParty | None:
        contact = self.repo.get_contact(contact_id)
        if contact is None:
            return None

        data = payload.model_dump()
        data["name"] = data["name"] or contact.name
        data["address"] = data["address"] or getattr(contact, "address", None)
        data["email"] = data["email"] or getattr(contact, "email", None)
        data["phone"] = data["phone"] or getattr(contact, "phone", None)
        data["tax_info"] = data["tax_info"] or getattr(contact, "tax_info", None)
        notify_party = self.repo.get_notify_party(contact_id)
        if notify_party is None:
            notify_party = ConsigneeNotifyParty(consignee_contact_id=contact_id, **data)
            self.db.add(notify_party)
        else:
            for key, value in data.items():
                setattr(notify_party, key, value)
        self.db.commit()
        self.db.refresh(notify_party)
        return notify_party

    def update_contact(self, contact_id: int, payload: ConsigneeContactUpdate) -> ConsigneeContact | None:
        contact = self.repo.get_contact(contact_id)
        if contact is None:
            return None
        for key, value in payload.model_dump(exclude_unset=True).items():
            setattr(contact, key, value)
        self.db.commit()
        self.db.refresh(contact)
        return contact
