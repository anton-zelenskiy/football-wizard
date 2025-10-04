from typing import Generic, TypeVar

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
import structlog


logger = structlog.get_logger()

T = TypeVar('T')


class BaseRepository(Generic[T]):
    """Base repository class with common CRUD operations"""

    def __init__(self, session: AsyncSession, model_class: type[T]):
        self.session = session
        self.model_class = model_class

    async def get_by_id(self, id: int) -> T | None:
        """Get entity by ID"""
        try:
            result = await self.session.execute(
                select(self.model_class).where(self.model_class.id == id)
            )
            return result.scalar_one_or_none()
        except Exception as e:
            logger.error(f'Error getting {self.model_class.__name__} by ID {id}: {e}')
            raise

    async def get_all(self) -> list[T]:
        """Get all entities"""
        try:
            result = await self.session.execute(select(self.model_class))
            return result.scalars().all()
        except Exception as e:
            logger.error(f'Error getting all {self.model_class.__name__}: {e}')
            raise

    async def create(self, **kwargs) -> T:
        """Create new entity"""
        try:
            entity = self.model_class(**kwargs)
            self.session.add(entity)
            await self.session.commit()
            await self.session.refresh(entity)
            logger.info(f'Created {self.model_class.__name__}: {entity.id}')
            return entity
        except IntegrityError as e:
            await self.session.rollback()
            logger.error(f'Integrity error creating {self.model_class.__name__}: {e}')
            raise
        except Exception as e:
            await self.session.rollback()
            logger.error(f'Error creating {self.model_class.__name__}: {e}')
            raise

    async def update(self, entity: T) -> T:
        """Update existing entity"""
        try:
            await self.session.commit()
            await self.session.refresh(entity)
            logger.info(f'Updated {self.model_class.__name__}: {entity.id}')
            return entity
        except Exception as e:
            await self.session.rollback()
            logger.error(f'Error updating {self.model_class.__name__}: {e}')
            raise

    async def delete(self, id: int) -> bool:
        """Delete entity by ID"""
        try:
            entity = await self.get_by_id(id)
            if not entity:
                logger.warning(
                    f'{self.model_class.__name__} with ID {id} not found for deletion'
                )
                return False

            await self.session.delete(entity)
            await self.session.commit()
            logger.info(f'Deleted {self.model_class.__name__}: {id}')
            return True
        except Exception as e:
            await self.session.rollback()
            logger.error(f'Error deleting {self.model_class.__name__} {id}: {e}')
            raise
