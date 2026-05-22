from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from app.models import ConsigneeNotifyParty
from app.schemas.consignee import ConsigneeContactCreate, ConsigneeNotifyPartyUpsert
from app.services.consignee_service import ConsigneeService


class FakeDb:
    def __init__(self) -> None:
        self.added = []
        self.committed = False
        self.refreshed = []

    def add(self, item):
        self.added.append(item)

    def commit(self):
        self.committed = True

    def refresh(self, item):
        self.refreshed.append(item)


class FakeRepo:
    def __init__(self, contact, notify_party=None) -> None:
        self.contact = contact
        self.notify_party = notify_party

    def get_contact(self, contact_id: int):
        return self.contact if self.contact and self.contact.id == contact_id else None

    def get_notify_party(self, contact_id: int):
        if self.notify_party and self.notify_party.consignee_contact_id == contact_id:
            return self.notify_party
        return None


def _make_service(contact, notify_party=None):
    service = ConsigneeService.__new__(ConsigneeService)
    service.db = FakeDb()
    service.repo = FakeRepo(contact, notify_party)
    return service


def test_consignee_contact_create_requires_name() -> None:
    with pytest.raises(ValidationError):
        ConsigneeContactCreate(consignee_id=1)


def test_consignee_contact_create_accepts_name() -> None:
    payload = ConsigneeContactCreate(consignee_id=1, name="Mission Freight AMS")

    assert payload.name == "Mission Freight AMS"


def test_upsert_notify_party_creates_first_record() -> None:
    service = _make_service(SimpleNamespace(id=7))
    payload = ConsigneeNotifyPartyUpsert(name="Notify BV", email="notify@example.com")

    result = service.upsert_notify_party(7, payload)

    assert isinstance(result, ConsigneeNotifyParty)
    assert result.consignee_contact_id == 7
    assert result.name == "Notify BV"
    assert result.email == "notify@example.com"
    assert service.db.committed is True
    assert service.db.added == [result]


def test_upsert_notify_party_defaults_to_consignee_contact_when_blank() -> None:
    contact = SimpleNamespace(
        id=7,
        name="Mission Freight AMS",
        address="Radarweg 1",
        email="ams@example.com",
        phone="+31 20 123456",
        tax_info="NL123",
    )
    service = _make_service(contact)
    payload = ConsigneeNotifyPartyUpsert()

    result = service.upsert_notify_party(7, payload)

    assert isinstance(result, ConsigneeNotifyParty)
    assert result.name == "Mission Freight AMS"
    assert result.address == "Radarweg 1"
    assert result.email == "ams@example.com"
    assert result.phone == "+31 20 123456"
    assert result.tax_info == "NL123"
    assert service.db.committed is True


def test_upsert_notify_party_updates_existing_record() -> None:
    existing = ConsigneeNotifyParty(consignee_contact_id=7, name="Old Notify", email="old@example.com")
    service = _make_service(SimpleNamespace(id=7), existing)
    payload = ConsigneeNotifyPartyUpsert(name="New Notify", phone="+31 20 123456")

    result = service.upsert_notify_party(7, payload)

    assert result is existing
    assert existing.name == "New Notify"
    assert existing.phone == "+31 20 123456"
    assert existing.email is None
    assert service.db.added == []
    assert service.db.committed is True


def test_upsert_notify_party_returns_none_when_contact_missing() -> None:
    service = _make_service(None)
    payload = ConsigneeNotifyPartyUpsert(name="Notify BV")

    result = service.upsert_notify_party(7, payload)

    assert result is None
    assert service.db.committed is False
