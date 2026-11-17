from fastapi import APIRouter, Depends

from app.core.dependencies import DbSession, require_role
from app.repositories.developers import DeveloperRepository
from app.schemas.auth import DeveloperOut
from app.schemas.common import Page, Pagination

router = APIRouter(
    prefix="/api/v1/admin",
    tags=["admin"],
    dependencies=[Depends(require_role("admin"))],
)


@router.get("/developers", response_model=Page[DeveloperOut], summary="List all developers")
async def list_developers(db: DbSession, page: Pagination) -> Page[DeveloperOut]:
    developers, total = await DeveloperRepository(db).list_page(page.limit, page.offset)
    return Page(
        items=[DeveloperOut.model_validate(d) for d in developers],
        total=total,
        limit=page.limit,
        offset=page.offset,
    )
