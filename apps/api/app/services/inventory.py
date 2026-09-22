from collections.abc import Mapping
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..exceptions import PersistenceError, SecurityError
from ..models import Device, Network, Site, Subnet, User, VLAN, WLAN
from .audit import record_security_event

_ACTION_PAST_TENSE = {"create": "created", "update": "updated", "delete": "deleted"}


class InventoryService:
    models = {
        "asset": Device,
        "site": Site,
        "network": Network,
        "subnet": Subnet,
        "vlan": VLAN,
        "ssid": WLAN,
    }

    def list(self, session: Session, kind: str, organization_id: UUID) -> list[Any]:
        model = self.models[kind]
        return list(session.scalars(select(model).where(model.organization_id == organization_id).order_by(model.created_at.desc())))

    def get(self, session: Session, kind: str, resource_id: UUID, organization_id: UUID) -> Any | None:
        model = self.models[kind]
        return session.scalar(select(model).where(model.id == resource_id, model.organization_id == organization_id))

    def create(self, session: Session, kind: str, actor: User, values: Mapping[str, Any]) -> Any:
        self._validate_parent_scope(session, kind, actor.organization_id, values)
        model = self.models[kind]
        resource = model(organization_id=actor.organization_id, **values)
        session.add(resource)
        self._audit(session, kind, resource, actor, "create")
        return self._commit(session, resource, "created")

    def update(self, session: Session, kind: str, resource: Any, actor: User, values: Mapping[str, Any]) -> Any:
        if resource.organization_id != actor.organization_id:
            raise SecurityError("permission_denied", "Permission denied", 403)
        self._validate_parent_scope(session, kind, actor.organization_id, values)
        for key, value in values.items():
            setattr(resource, key, value)
        self._audit(session, kind, resource, actor, "update")
        return self._commit(session, resource, "updated")

    def delete(self, session: Session, kind: str, resource: Any, actor: User) -> None:
        if resource.organization_id != actor.organization_id:
            raise SecurityError("permission_denied", "Permission denied", 403)
        self._audit(session, kind, resource, actor, "delete")
        session.delete(resource)
        try:
            session.commit()
        except IntegrityError as exc:
            session.rollback()
            raise PersistenceError("Resource could not be deleted") from exc

    def _validate_parent_scope(self, session: Session, kind: str, organization_id: UUID, values: Mapping[str, Any]) -> None:
        single_parent_fields = {
            "network": ("site_id", Site),
            "subnet": ("network_id", Network),
            "vlan": ("network_id", Network),
            "ssid": ("network_id", Network),
        }
        field_model = single_parent_fields.get(kind)
        if field_model is not None:
            field, model = field_model
            parent_id = values.get(field)
            if parent_id is not None and session.scalar(
                select(model.id).where(model.id == parent_id, model.organization_id == organization_id)
            ) is None:
                raise SecurityError("resource_not_found", "Related resource not found", 404)
            return
        if kind == "asset":
            for related_field, related_model in (
                ("site_id", Site), ("network_id", Network), ("subnet_id", Subnet),
                ("vlan_id", VLAN), ("wlan_id", WLAN),
            ):
                related_id = values.get(related_field)
                if related_id is not None and session.scalar(
                    select(related_model.id).where(
                        related_model.id == related_id, related_model.organization_id == organization_id
                    )
                ) is None:
                    raise SecurityError("resource_not_found", "Related resource not found", 404)
            assigned_user_id = values.get("assigned_user_id")
            if assigned_user_id is not None:
                from ..models import User as UserModel

                if session.scalar(
                    select(UserModel.id).where(
                        UserModel.id == assigned_user_id, UserModel.organization_id == organization_id
                    )
                ) is None:
                    raise SecurityError("resource_not_found", "Related resource not found", 404)

    def _audit(self, session: Session, kind: str, resource: Any, actor: User, action: str) -> None:
        record_security_event(
            session,
            event_type=f"{kind}_{_ACTION_PAST_TENSE[action]}",
            organization_id=resource.organization_id,
            actor_user_id=actor.id,
            action=action,
            result="success",
            metadata={f"target_{kind}_id": str(resource.id)},
            resource_type=kind,
            resource_id=str(resource.id),
        )

    @staticmethod
    def _commit(session: Session, resource: Any, action: str) -> Any:
        try:
            session.commit()
            session.refresh(resource)
            return resource
        except IntegrityError as exc:
            session.rollback()
            raise PersistenceError(f"Resource could not be {action}") from exc
