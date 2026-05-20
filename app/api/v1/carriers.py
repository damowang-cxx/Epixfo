from fastapi import APIRouter, Depends

from app.core.platform_patch import patch_platform_wmi

patch_platform_wmi()

from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.database import get_db
from app.core.exceptions import not_found
from app.models.enums import UserRoleCode
from app.schemas.carrier import (
    CarrierCreate,
    CarrierOut,
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
