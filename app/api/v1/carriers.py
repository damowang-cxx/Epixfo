from fastapi import APIRouter, Depends

from app.core.platform_patch import patch_platform_wmi

patch_platform_wmi()

from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.database import get_db
from app.core.exceptions import not_found
from app.models.enums import UserRoleCode
from app.schemas.carrier import (
    CarrierAgentCreate,
    CarrierAgentOut,
    CarrierAgentUpdate,
    CarrierCreate,
    CarrierOut,
    CarrierUpdate,
    CarrierPrefixMappingCreate,
    CarrierPrefixMappingOut,
    CarrierPrefixMappingUpdate,
)
from app.services.carrier_service import CarrierService
from app.services.permission_service import PermissionService

router = APIRouter(tags=["carriers"])


@router.get("/carriers", response_model=list[CarrierOut])
def list_carriers(current_user=Depends(get_current_user), db: Session = Depends(get_db)):
    return CarrierService(db).list_carriers()


@router.post("/carriers", response_model=CarrierOut)
def create_carrier(payload: CarrierCreate, current_user=Depends(get_current_user), db: Session = Depends(get_db)):
    PermissionService.require_any(current_user, {UserRoleCode.ADMIN, UserRoleCode.ROUTE_STAFF})
    return CarrierService(db).create_carrier(payload)


@router.patch("/carriers/{carrier_code}", response_model=CarrierOut)
def update_carrier(
    carrier_code: str,
    payload: CarrierUpdate,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    PermissionService.require_any(current_user, {UserRoleCode.ADMIN, UserRoleCode.ROUTE_STAFF})
    carrier = CarrierService(db).update_carrier(carrier_code, payload)
    if carrier is None:
        raise not_found("Carrier not found")
    return carrier


@router.get("/carrier-prefix-mappings", response_model=list[CarrierPrefixMappingOut])
def list_mappings(current_user=Depends(get_current_user), db: Session = Depends(get_db)):
    return CarrierService(db).list_mappings()


@router.post("/carrier-prefix-mappings", response_model=CarrierPrefixMappingOut)
def create_mapping(
    payload: CarrierPrefixMappingCreate,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    PermissionService.require_any(current_user, {UserRoleCode.ADMIN, UserRoleCode.ROUTE_STAFF})
    return CarrierService(db).create_mapping(payload)


@router.patch("/carrier-prefix-mappings/{mapping_id}", response_model=CarrierPrefixMappingOut)
def update_mapping(
    mapping_id: int,
    payload: CarrierPrefixMappingUpdate,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    PermissionService.require_any(current_user, {UserRoleCode.ADMIN, UserRoleCode.ROUTE_STAFF})
    mapping = CarrierService(db).update_mapping(mapping_id, payload)
    if mapping is None:
        raise not_found("Carrier prefix mapping not found")
    return mapping


@router.get("/carrier-agents", response_model=list[CarrierAgentOut])
def list_agents(
    carrier_code: str | None = None,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return CarrierService(db).list_agents(carrier_code)


@router.post("/carrier-agents", response_model=CarrierAgentOut)
def create_agent(
    payload: CarrierAgentCreate,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    PermissionService.require_any(current_user, {UserRoleCode.ADMIN, UserRoleCode.ROUTE_STAFF})
    return CarrierService(db).create_agent(payload)


@router.patch("/carrier-agents/{agent_id}", response_model=CarrierAgentOut)
def update_agent(
    agent_id: int,
    payload: CarrierAgentUpdate,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    PermissionService.require_any(current_user, {UserRoleCode.ADMIN, UserRoleCode.ROUTE_STAFF})
    agent = CarrierService(db).update_agent(agent_id, payload)
    if agent is None:
        raise not_found("Carrier agent not found")
    return agent
