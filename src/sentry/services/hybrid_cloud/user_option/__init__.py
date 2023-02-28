from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable, List, Optional, TypedDict, cast

from sentry.services.hybrid_cloud.filter_query import FilterQueryInterface
from sentry.services.hybrid_cloud.rpc import RpcService, rpc_method
from sentry.silo import SiloMode


@dataclass
class RpcUserOption:
    id: int = -1
    user_id: int = -1
    value: Any = None
    key: str = ""
    project_id: int | None = None
    organization_id: int | None = None


def get_option_from_list(
    options: List[RpcUserOption],
    *,
    key: str | None = None,
    user_id: int | None = None,
    default: Any = None,
) -> Any:
    for option in options:
        if key is not None and option.key != key:
            continue
        if user_id is not None and option.user_id != user_id:
            continue
        return option.value
    return default


class UserOptionFilterArgs(TypedDict, total=False):
    user_ids: Iterable[int]
    keys: List[str]
    key: str
    project_id: Optional[int]
    organization_id: Optional[int]


class UserOptionService(
    FilterQueryInterface[UserOptionFilterArgs, RpcUserOption, None], RpcService
):
    name = "user_option"
    local_mode = SiloMode.CONTROL

    @classmethod
    def get_local_implementation(cls) -> RpcService:
        from sentry.services.hybrid_cloud.user_option.impl import DatabaseBackedUserOptionService

        return DatabaseBackedUserOptionService()

    @rpc_method
    def delete_options(self, *, option_ids: List[int]) -> None:
        pass

    @rpc_method
    def set_option(
        self,
        *,
        user_id: int,
        value: Any,
        key: str,
        project_id: int | None = None,
        organization_id: int | None = None,
    ) -> None:
        pass


user_option_service: UserOptionService = cast(
    UserOptionService, UserOptionService.resolve_to_delegation()
)
