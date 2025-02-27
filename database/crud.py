import json
import os
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from sqlalchemy import select, delete, Integer
from database.database import SQLALCHEMY_DATABASE_URL
from database.models import Made_Bots, Domains, Manifest, Cloaking, Landing, Mailing, User
from datetime import datetime, timedelta
from sqlalchemy import select, func, cast

async def copy_bot_data(bot_name: str, bot_id: int):
    """Copies bot data asynchronously, handling empty mailing."""

    try:
        source_engine = create_async_engine(SQLALCHEMY_DATABASE_URL)  # Your source DB URL
        destination_db_path = f"bot_database_{bot_name}.db"  # Path to the new SQLite DB
        destination_engine = create_async_engine(
            f"sqlite+aiosqlite:///{destination_db_path}",
            connect_args={'check_same_thread': False}
        )

        async with source_engine.begin() as source_conn, destination_engine.begin() as dest_conn:
            SourceSession = async_sessionmaker(bind=source_conn, expire_on_commit=False)
            DestinationSession = async_sessionmaker(bind=dest_conn, expire_on_commit=False)

            async with SourceSession() as source_session, DestinationSession() as destination_session:
                # 0. Clear destination tables FIRST
                await destination_session.execute(delete(Made_Bots))
                await destination_session.execute(delete(Mailing))
                await destination_session.commit()

                # 1. Get bot data (Made_Bots)
                source_bot_query = await source_session.execute(select(Made_Bots).where(Made_Bots.id == bot_id))
                source_bot = source_bot_query.scalars().first()

                if not source_bot:
                    print(f"Bot with ID {bot_id} not found in source database.")
                    return False  # Return False if bot not found

                # 2. Copy data from Made_Bots
                destination_bot = Made_Bots(
                    bot_id=source_bot.bot_id,
                    bot_token=source_bot.bot_token,
                    web_app_button=source_bot.web_app_button,
                    web_app_position=source_bot.web_app_position,
                    start_photo=source_bot.start_photo,
                    start_message=source_bot.start_message,
                    buttons=json.dumps(source_bot.buttons) if source_bot.buttons else None,
                    is_working=source_bot.is_working,
                    is_referal=source_bot.is_referal,
                    web_app_link=source_bot.web_app_link,
                    web_app_html=source_bot.web_app_html,
                    user_tg_id=source_bot.user_tg_id,
                    process=source_bot.process
                )
                destination_session.add(destination_bot)
                await destination_session.flush()  # Flush to get bot ID

                # 3. Get mailing data (Mailing) - Check if exists
                source_mailing_query = await source_session.execute(select(Mailing).where(Mailing.bot_id == bot_id))
                source_mailing = source_mailing_query.scalars().first()

                # 4. Copy mailing data only if it exists
                if source_mailing:  # Only if source_mailing is not None
                    destination_mailing = Mailing(
                        name=source_mailing.name,
                        mailing_text=source_mailing.mailing_text,
                        mailing_buttons=source_mailing.mailing_buttons,
                        interval=source_mailing.interval,
                        bot_id=destination_bot.id  # Use the ID of the newly created bot
                    )
                    destination_session.add(destination_mailing)

                await destination_session.commit()  # Commit after adding both bot and mailing (if it exists)

        await source_engine.dispose()
        await destination_engine.dispose()
        return True

    except Exception as e:
        print(f"Error copying data: {e}")
        return False


async def get_user_statistics(bot_name: str, bot_id: int):
    """Retrieves user statistics from the destination database."""

    try:
        destination_db_path = f"bot_database_{bot_name}.db"
        destination_engine = create_async_engine(
            f"sqlite+aiosqlite:///{destination_db_path}",
            connect_args={'check_same_thread': False}
        )

        async with destination_engine.begin() as dest_conn:
            DestinationSession = async_sessionmaker(bind=dest_conn, expire_on_commit=False)

            async with DestinationSession() as destination_session:
                now = datetime.now()

                stats = await destination_session.execute(
                    select(
                        func.count().label("total"),  # Всего пользователей
                        func.sum(cast(User.registration_date >= now - timedelta(days=30), Integer)).label("month"),  # За месяц
                        func.sum(cast(User.registration_date >= now - timedelta(days=7), Integer)).label("week"),  # За неделю
                        func.sum(cast(User.registration_date >= now - timedelta(days=1), Integer)).label("day"),  # За день
                        func.sum(cast(User.registration_date >= now - timedelta(hours=1), Integer)).label("hour"),  # За час
                        func.sum(cast(User.registration_date >= now - timedelta(minutes=15), Integer)).label("fifteen_min")  # За 15 минут
                    ).select_from(User)
                )

                result = stats.fetchone()

                # Формируем словарь со статистикой
                return {
                    "total": result.total,  # Всего пользователей
                    "month": result.month or 0,  # За месяц (или 0, если нет пользователей)
                    "week": result.week or 0,  # За неделю (или 0, если нет пользователей)
                    "day": result.day or 0,  # За день (или 0, если нет пользователей)
                    "hour": result.hour or 0,  # За час (или 0, если нет пользователей)
                    "fifteen_min": result.fifteen_min or 0  # За 15 минут (или 0, если нет пользователей)
                }

        await destination_engine.dispose()

    except Exception as e:
        print(f"Error retrieving user statistics: {e}")
        return None