from __future__ import annotations

from core.repositories.category_owner_repository import CategoryOwnerRepository
from core.schemas.categories import CategoryOwnerCreateRequest, CategoryOwnerResponse


class CategoryOwnerService:
    def __init__(self, repo: CategoryOwnerRepository) -> None:
        self._repo = repo

    async def create_owner(self, req: CategoryOwnerCreateRequest) -> CategoryOwnerResponse:
        user = await self._repo.get_slack_user(slack_user_id=req.slack_user_id)
        if not user:
            raise RuntimeError("Slack user not found")

        display_name = user["display_name"] or user["real_name"] or req.slack_user_id
        real_name = user["real_name"] or user["display_name"] or display_name

        row = await self._repo.create_owner(
            category_id=str(req.category_id),
            slack_user_id=req.slack_user_id,
            display_name=display_name,
            real_name=real_name,
            email=user["email"],
            is_active=user["is_active"],
        )

        name = row["display_name"] or row["real_name"] or req.slack_user_id
        return CategoryOwnerResponse(
            category_id=row["category_id"],
            slack_user_id=row["slack_user_id"],
            name=name,
            email=row["email"],
            is_active=row["is_active"],
        )
