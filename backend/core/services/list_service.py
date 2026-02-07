from __future__ import annotations

from core.repositories.list_repo import ListRepo
from core.schemas.list import (
    DeviceListResponse,
    DeviceOption,
    NetworkListResponse,
    NetworkOption,
    ProjectListResponse,
    ProjectOption,
)


class ListService:
    def __init__(self, repo: ListRepo) -> None:
        self._repo = repo

    async def list_devices(self, *, page: int, page_size: int) -> DeviceListResponse:
        limit = page_size
        offset = (page - 1) * page_size
        rows, total = await self._repo.list_devices(limit=limit, offset=offset)
        items = [DeviceOption.model_validate(dict(row)) for row in rows]
        return DeviceListResponse(
            items=items,
            total=total,
            page=page,
            page_size=page_size,
        )

    async def list_networks(self, *, page: int, page_size: int) -> NetworkListResponse:
        limit = page_size
        offset = (page - 1) * page_size
        rows, total = await self._repo.list_networks(limit=limit, offset=offset)
        items = [NetworkOption.model_validate(dict(row)) for row in rows]
        return NetworkListResponse(
            items=items,
            total=total,
            page=page,
            page_size=page_size,
        )

    async def list_projects(self, *, page: int, page_size: int) -> ProjectListResponse:
        limit = page_size
        offset = (page - 1) * page_size
        rows, total = await self._repo.list_projects(limit=limit, offset=offset)
        items = [ProjectOption.model_validate(dict(row)) for row in rows]
        return ProjectListResponse(
            items=items,
            total=total,
            page=page,
            page_size=page_size,
        )
