import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Developer


class DeveloperRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get(self, developer_id: uuid.UUID) -> Developer | None:
        return await self.session.get(Developer, developer_id)

    async def get_by_email(self, email: str) -> Developer | None:
        result = await self.session.execute(select(Developer).where(Developer.email == email))
        return result.scalar_one_or_none()

    def add(self, developer: Developer) -> None:
        self.session.add(developer)

    async def list_page(self, limit: int, offset: int) -> tuple[list[Developer], int]:
        total = await self.session.scalar(select(func.count()).select_from(Developer))
        result = await self.session.execute(
            select(Developer)
            .order_by(Developer.created_at, Developer.id)
            .limit(limit)
            .offset(offset)
        )
        return list(result.scalars()), total or 0
