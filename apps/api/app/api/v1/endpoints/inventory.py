from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, Response
from sqlalchemy.orm import Session

from ....db import get_db
from ...dependencies.auth import get_inventory_service, require_permission
from ....exceptions import SecurityError
from ....models import User
from ....schemas import (
    AssetCreate, AssetRead, AssetUpdate, NetworkCreate, NetworkRead, NetworkUpdate,
    SiteCreate, SiteRead, SiteUpdate, SSIDCreate, SSIDRead, SSIDUpdate,
    SubnetCreate, SubnetRead, SubnetUpdate, VLANCreate, VLANRead, VLANUpdate,
)
from ....services.inventory import InventoryService

# Only two permission namespaces are used: "assets" for the asset/device
# inventory resource and "networks" for every network topology resource
# (sites, networks, subnets, VLANs, SSIDs).
_PERMISSION_NAMESPACE = {
    "asset": "assets",
    "site": "networks",
    "network": "networks",
    "subnet": "networks",
    "vlan": "networks",
    "ssid": "networks",
}


def _not_found(kind: str) -> SecurityError:
    return SecurityError(f"{kind}_not_found", f"{kind.title()} not found", 404)


def _resource_router(
    *,
    kind: str,
    path: str,
    create_schema: type,
    update_schema: type,
    read_schema: type,
) -> APIRouter:
    router = APIRouter(prefix=path, tags=[kind])
    namespace = _PERMISSION_NAMESPACE[kind]
    read_permission = f"{namespace}:read"
    create_permission = f"{namespace}:create"
    manage_permission = f"{namespace}:manage"

    @router.get("", response_model=list[read_schema])
    def list_resources(
        user: User = Depends(require_permission(read_permission)),
        service: InventoryService = Depends(get_inventory_service),
        session: Session = Depends(get_db),
    ) -> list[Any]:
        return service.list(session, kind, user.organization_id)

    @router.post("", response_model=read_schema, status_code=201)
    def create_resource(
        payload: create_schema,
        user: User = Depends(require_permission(create_permission)),
        service: InventoryService = Depends(get_inventory_service),
        session: Session = Depends(get_db),
    ) -> Any:
        return service.create(session, kind, user, payload.model_dump(exclude_unset=True))

    @router.get("/{resource_id}", response_model=read_schema)
    def get_resource(
        resource_id: UUID,
        user: User = Depends(require_permission(read_permission)),
        service: InventoryService = Depends(get_inventory_service),
        session: Session = Depends(get_db),
    ) -> Any:
        resource = service.get(session, kind, resource_id, user.organization_id)
        if resource is None:
            raise _not_found(kind)
        return resource

    @router.patch("/{resource_id}", response_model=read_schema)
    def update_resource(
        resource_id: UUID,
        payload: update_schema,
        user: User = Depends(require_permission(manage_permission)),
        service: InventoryService = Depends(get_inventory_service),
        session: Session = Depends(get_db),
    ) -> Any:
        resource = service.get(session, kind, resource_id, user.organization_id)
        if resource is None:
            raise _not_found(kind)
        return service.update(session, kind, resource, user, payload.model_dump(exclude_unset=True))

    @router.delete("/{resource_id}", status_code=204)
    def delete_resource(
        resource_id: UUID,
        user: User = Depends(require_permission(manage_permission)),
        service: InventoryService = Depends(get_inventory_service),
        session: Session = Depends(get_db),
    ) -> Response:
        resource = service.get(session, kind, resource_id, user.organization_id)
        if resource is None:
            raise _not_found(kind)
        service.delete(session, kind, resource, user)
        return Response(status_code=204)

    return router


router = APIRouter()
router.include_router(_resource_router(
    kind="asset", path="/assets", create_schema=AssetCreate, update_schema=AssetUpdate, read_schema=AssetRead,
))
router.include_router(_resource_router(
    kind="site", path="/sites", create_schema=SiteCreate, update_schema=SiteUpdate, read_schema=SiteRead,
))
router.include_router(_resource_router(
    kind="network", path="/networks", create_schema=NetworkCreate, update_schema=NetworkUpdate, read_schema=NetworkRead,
))
router.include_router(_resource_router(
    kind="subnet", path="/subnets", create_schema=SubnetCreate, update_schema=SubnetUpdate, read_schema=SubnetRead,
))
router.include_router(_resource_router(
    kind="vlan", path="/vlans", create_schema=VLANCreate, update_schema=VLANUpdate, read_schema=VLANRead,
))
router.include_router(_resource_router(
    kind="ssid", path="/ssids", create_schema=SSIDCreate, update_schema=SSIDUpdate, read_schema=SSIDRead,
))
