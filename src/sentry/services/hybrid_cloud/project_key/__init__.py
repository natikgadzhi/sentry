from dataclasses import dataclass
from enum import Enum
from typing import Any, Optional, cast

from sentry.services.hybrid_cloud.rpc import RpcService, rpc_method
from sentry.silo import SiloMode


class ProjectKeyRole(Enum):
    store = "store"
    api = "api"

    def as_orm_role(self) -> Any:
        from sentry.models import ProjectKey

        if self == ProjectKeyRole.store:
            return ProjectKey.roles.store
        elif self == ProjectKeyRole.api:
            return ProjectKey.roles.api
        else:
            raise ValueError("Unexpected project key role enum")


@dataclass
class RpcProjectKey:
    dsn_public: str = ""


class ProjectKeyService(RpcService):
    name = "project_key"
    local_mode = SiloMode.REGION

    @classmethod
    def get_local_implementation(cls) -> "RpcService":
        from sentry.services.hybrid_cloud.project_key.impl import DatabaseBackedProjectKeyService

        return DatabaseBackedProjectKeyService()

    @rpc_method
    def get_project_key(self, project_id: str, role: ProjectKeyRole) -> Optional[RpcProjectKey]:
        pass


project_key_service: ProjectKeyService = cast(
    ProjectKeyService, ProjectKeyService.resolve_to_delegation()
)
