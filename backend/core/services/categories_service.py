from __future__ import annotations

from core.repositories.categories_repository import CategoriesRepository
from core.schemas.categories import (
    CategoryListItem,
    CategoryListResponse,
    CategoryOption,
    CategoryOptionsResponse,
)


class CategoriesService:
    def __init__(self, repo: CategoriesRepository) -> None:
        self._repo = repo

    async def list_categories(
        self,
        *,
        project_id: str,
        page: int,
        page_size: int,
    ) -> CategoryListResponse:
        limit = page_size
        offset = (page - 1) * page_size
        rows, total = await self._repo.list_categories(
            project_id=project_id,
            limit=limit,
            offset=offset,
        )

        items: list[CategoryListItem] = []
        for idx, row in enumerate(rows):
            items.append(
                CategoryListItem(
                    idx=idx,
                    id=row["id"],
                    project_id=row["project_id"],
                    category=row["category"],
                    slack_user_id=row["slack_user_id"],
                    created_at=row["created_at"],
                    updated_at=row["updated_at"],
                    slack_display_name=row["slack_display_name"],
                    slack_real_name=row["slack_real_name"],
                )
            )

        return CategoryListResponse(
            items=items,
            total=total,
            page=page,
            page_size=page_size,
        )

    async def list_category_options(
        self,
        *,
        page: int,
        page_size: int,
    ) -> CategoryOptionsResponse:
        limit = page_size
        offset = (page - 1) * page_size
        rows, total = await self._repo.list_category_options(
            limit=limit,
            offset=offset,
        )

        items: list[CategoryOption] = []
        for row in rows:
            items.append(CategoryOption(id=row["id"], category=row["category"]))

        return CategoryOptionsResponse(
            items=items,
            total=total,
            page=page,
            page_size=page_size,
        )
