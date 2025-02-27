from aiogram import BaseMiddleware
from aiogram.types import Message
import logging
from database.models import User
from database.database import async_session
from sqlalchemy import select, update
from datetime import datetime


class AuthorizeMiddleware(BaseMiddleware):
    '''Inject AsyncSession and User objects'''
    async def __call__(self, handler, event: Message, data) -> bool:
        async with async_session() as session:
            uid = event.from_user.id if hasattr(event, 'from_user') else event.message.from_user.id
            query = select(User).where(User.tg_id == uid)
            user: User = (await session.execute(query)).scalar()
            if not user:
                user = User(tg_id=event.from_user.id,
                            first_name=event.from_user.first_name,
                            last_name=event.from_user.last_name,
                            username=event.from_user.username
                            )
                logger = logging.getLogger()
                logger.info(f'New user')
                session.add(user)
            await session.commit()
            data['user'] = user
            data['session'] = session
            result = await handler(event, data)
            await session.commit()
        return result
