from fastapi import APIRouter, Depends

from app.core.platform_patch import patch_platform_wmi

patch_platform_wmi()

from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.database import get_db
from app.core.exceptions import not_found
from app.models.enums import UserRoleCode
from app.schemas.consignee import (
    ConsigneeContactCreate,
    ConsigneeContactOut,
    ConsigneeContactUpdate,
    ConsigneeNotifyPartyOut,
    ConsigneeNotifyPartyUpsert,
    ConsigneeCreate,
    ConsigneeOut,
    ConsigneeUpdate,
)
from app.services.consignee_service import ConsigneeService
from app.services.permission_service import PermissionService

router = APIRouter(tags=["consignees"])


# ---- Consignee（厂商）----

@router.get("/consignees", response_model=list[ConsigneeOut])
def list_consignees(current_user=Depends(get_current_user), db: Session = Depends(get_db)):
    return ConsigneeService(db).list_consignees()


@router.post("/consignees", response_model=ConsigneeOut)
def create_consignee(
    payload: ConsigneeCreate,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    PermissionService.require_any(current_user, {UserRoleCode.ADMIN, UserRoleCode.ROUTE_STAFF})
    return ConsigneeService(db).create_consignee(payload)


@router.patch("/consignees/{consignee_id}", response_model=ConsigneeOut)
def update_consignee(
    consignee_id: int,
    payload: ConsigneeUpdate,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    PermissionService.require_any(current_user, {UserRoleCode.ADMIN, UserRoleCode.ROUTE_STAFF})
    consignee = ConsigneeService(db).update_consignee(consignee_id, payload)
    if consignee is None:
        raise not_found("Consignee not found")
    return consignee


# ---- ConsigneeContact（收件人记录）----

@router.get("/consignee-contacts", response_model=list[ConsigneeContactOut])
def list_consignee_contacts(
    consignee_id: int | None = None,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return ConsigneeService(db).list_contacts(consignee_id)


@router.post("/consignee-contacts", response_model=ConsigneeContactOut)
def create_consignee_contact(
    payload: ConsigneeContactCreate,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    PermissionService.require_any(current_user, {UserRoleCode.ADMIN, UserRoleCode.ROUTE_STAFF})
    return ConsigneeService(db).create_contact(payload)


@router.patch("/consignee-contacts/{contact_id}", response_model=ConsigneeContactOut)
def update_consignee_contact(
    contact_id: int,
    payload: ConsigneeContactUpdate,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    PermissionService.require_any(current_user, {UserRoleCode.ADMIN, UserRoleCode.ROUTE_STAFF})
    contact = ConsigneeService(db).update_contact(contact_id, payload)
    if contact is None:
        raise not_found("Consignee contact not found")
    return contact


@router.get("/consignee-contacts/{contact_id}/notify-party", response_model=ConsigneeNotifyPartyOut | None)
def get_consignee_notify_party(
    contact_id: int,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    service = ConsigneeService(db)
    if service.get_contact(contact_id) is None:
        raise not_found("Consignee contact not found")
    return service.get_notify_party(contact_id)


@router.put("/consignee-contacts/{contact_id}/notify-party", response_model=ConsigneeNotifyPartyOut)
def upsert_consignee_notify_party(
    contact_id: int,
    payload: ConsigneeNotifyPartyUpsert,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    PermissionService.require_any(current_user, {UserRoleCode.ADMIN, UserRoleCode.ROUTE_STAFF})
    notify_party = ConsigneeService(db).upsert_notify_party(contact_id, payload)
    if notify_party is None:
        raise not_found("Consignee contact not found")
    return notify_party
