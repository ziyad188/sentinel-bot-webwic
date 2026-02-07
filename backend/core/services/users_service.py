from __future__ import annotations

from core.repositories.users_repository import UsersRepository
from core.schemas.users import (
    SlackUserListItem,
    SlackUserListResponse,
    SlackUserWithCategoriesItem,
    SlackUserWithCategoriesResponse,
    SlackUserCreateRequest,
    SlackUserCreateResponse,
)


class UsersService:
    def __init__(self, repo: UsersRepository) -> None:
        self._repo = repo

    async def list_users(self, *, page: int, page_size: int) -> SlackUserListResponse:
        limit = page_size
        offset = (page - 1) * page_size
        rows, total = await self._repo.list_users(limit=limit, offset=offset)

        items: list[SlackUserListItem] = []
        for idx, row in enumerate(rows):
            items.append(
                SlackUserListItem(
                    idx=idx,
                    id=row["id"],
                    slack_user_id=row["slack_user_id"],
                    display_name=row["display_name"],
                    real_name=row["real_name"],
                    email=row["email"],
                    avatar_url=row["avatar_url"],
                    is_active=row["is_active"],
                    created_at=row["created_at"],
                    updated_at=row["updated_at"],
                    uuid_id=row["uuid_id"],
                )
            )

        return SlackUserListResponse(
            items=items,
            total=total,
            page=page,
            page_size=page_size,
        )

    async def list_users_with_categories(
        self, *, page: int, page_size: int
    ) -> SlackUserWithCategoriesResponse:
        limit = page_size
        offset = (page - 1) * page_size
        rows, total = await self._repo.list_users_with_categories(limit=limit, offset=offset)

        items: list[SlackUserWithCategoriesItem] = []
        for idx, row in enumerate(rows):
            items.append(
                SlackUserWithCategoriesItem(
                    idx=idx,
                    id=row["id"],
                    slack_user_id=row["slack_user_id"],
                    display_name=row["display_name"],
                    real_name=row["real_name"],
                    email=row["email"],
                    avatar_url=row["avatar_url"],
                    is_active=row["is_active"],
                    created_at=row["created_at"],
                    updated_at=row["updated_at"],
                    categories=list(row["categories"] or []),
                )
            )

        return SlackUserWithCategoriesResponse(
            items=items,
            total=total,
            page=page,
            page_size=page_size,
        )

    async def create_user(
        self,
        *,
        req: SlackUserCreateRequest,
    ) -> SlackUserCreateResponse:
        categories = list(dict.fromkeys(req.categories or []))

        async with self._repo._pool.acquire() as conn:  # use same pool for txn
            async with conn.transaction():
                user = await self._repo.create_user(
                    conn=conn,
                    slack_user_id=req.slack_user_id,
                    display_name=req.name,
                    real_name=req.name,
                    email=req.email,
                    avatar_url=req.avatar_url,
                    is_active=req.is_active,
                )
                await self._repo.add_category_owners(
                    conn=conn,
                    project_id=str(req.project_id),
                    slack_user_id=req.slack_user_id,
                    categories=categories,
                )

        return SlackUserCreateResponse(
            id=user["id"],
            slack_user_id=user["slack_user_id"],
            name=user["display_name"],
            email=user["email"],
            is_active=user["is_active"],
            project_id=req.project_id,
            categories=categories,
        )
