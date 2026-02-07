from __future__ import annotations

from core.repositories.project_repo import ProjectRepo
from core.schemas.projects import ProjectCreateRequest, ProjectCreateResponse


class ProjectService:
    def __init__(self, repo: ProjectRepo) -> None:
        self._repo = repo

    async def create_project(self, req: ProjectCreateRequest) -> ProjectCreateResponse:
        row = await self._repo.create_project(
            name=req.name,
            environment=req.environment,
            target_url=req.target_url,
        )
        return ProjectCreateResponse.model_validate(dict(row))
