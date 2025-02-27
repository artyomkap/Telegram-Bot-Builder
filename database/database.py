from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import (create_async_engine, async_sessionmaker,
                                    AsyncSession)
from sqlalchemy.orm import sessionmaker
from sqlalchemy.ext.declarative import declarative_base
import config

# URL вашей базы данных (замените на актуальный)
SQLALCHEMY_DATABASE_URL = f"mysql+aiomysql://{config.DB_USER}:{config.DB_PASS}@{config.DB_HOST}:{config.DB_PORT}/{config.DB_NAME}"

# Создаем движок SQLAlchemy
async_engine = create_async_engine(SQLALCHEMY_DATABASE_URL)

# Создаем сессию
async_session = async_sessionmaker(async_engine, expire_on_commit=False)

# Базовый класс для декларативных моделей
Base = declarative_base()


# Функция для получения сессии
async def get_db() -> AsyncSession:
    async with async_session() as session:
        yield session


async def init_models():
    async with async_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def dispose_engine():
    await async_engine.dispose()