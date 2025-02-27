import asyncio
import logging
from aiogram import Bot
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo, BotCommand, MenuButtonWebApp, \
    BotCommandScopeDefault, MenuButtonDefault
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from database.models import Made_Bots, User, Mailing
import random
import re


async def start_mailing_loop(bot_made, bot, mailing: Mailing, user_ids: list, session: AsyncSession, interval_seconds: int):
    try:
        # Отправляем рассылку один раз
        await send_mailing(bot_made, bot, mailing, user_ids, session)

        # Если интервал не указан (None или ''), отправляем сообщение один раз и выходим
        if not mailing.interval or not str(mailing.interval).isdigit():
            logging.info("Интервал не указан, завершаем рассылку")
            return

        # Если интервал указан, выполняем рассылку с задержкой
        while mailing.is_mailing and interval_seconds > 0:
            await asyncio.sleep(interval_seconds)
            await send_mailing(bot_made, bot, mailing, user_ids, session)
            logging.info(f"Повторная отправка через {interval_seconds} секунд")

    except Exception as e:
        logging.error(f"Ошибка запуска рассылки: {str(e)}")


async def send_mailing(bot_made, bot, mailing: Mailing, user_ids: list, session: AsyncSession):
    mailing_text = await process_functions(mailing.mailing_text)  # Обрабатываем текст рассылки
    keyboard = await generate_buttons(bot_made, mailing.mailing_buttons, session)  # Генерируем кнопки

    for user_id in user_ids:
        try:
            destination_db_path = f"bot_database_{bot_made.bot_name}.db"  # Path to the new SQLite DB
            destination_engine = create_async_engine(
                f"sqlite+aiosqlite:///{destination_db_path}",
                connect_args={'check_same_thread': False}
            )
            async with destination_engine.begin() as dest_conn:
                DestinationSession = async_sessionmaker(bind=dest_conn, expire_on_commit=False)
                async with DestinationSession() as destination_session:
                    user_query = await destination_session.execute(select(User).where(User.tg_id == user_id))
                    user = user_query.scalars().first()
            user_info = {
                "first_name": user.first_name or "",
                "last_name": user.last_name or "",
                "username": user.username or "",
                "telegram_id": user.tg_id,
            }

            # Форматируем текст с данными пользователя
            user_text = mailing_text.format(**user_info)

            await bot.send_message(chat_id=user.tg_id, text=user_text, reply_markup=keyboard, parse_mode='HTML')

        except Exception as e:
            logging.error(f"Ошибка отправки сообщения {user_id}: {e}")


async def generate_buttons(bot_made, buttons_str: str, session) -> InlineKeyboardMarkup:
    if not buttons_str or buttons_str.lower() == "none":
        return None  # Если кнопок нет, отправляем просто текст
    bot_name = bot_made.bot_id
    made_bot_query = await session.execute(select(Made_Bots).where(Made_Bots.bot_id == bot_name))
    made_bot = made_bot_query.scalars().first()
    buttons = []
    for button_data in buttons_str.split(","):
        parts = button_data.strip().split(" + ")
        if len(parts) == 2:
            text, link = parts
            if link == 'webapp':
                web_app_link = bot_made.web_app_link
                button = InlineKeyboardButton(text=text, web_app=WebAppInfo(url=web_app_link))
            else:
                button = InlineKeyboardButton(text=text, url=link)
            buttons.append([button])

    return InlineKeyboardMarkup(inline_keyboard=buttons) if buttons else None


async def process_functions(message_text: str) -> str:
    # Обработка {random(x,y)}
    message_text = re.sub(r"{random\((\d+),(\d+)\)}",
                          lambda match: str(random.randint(int(match.group(1)), int(match.group(2)))), message_text)

    # Обработка {n: выражение} и {^n}
    variables = {}
    message_text = re.sub(r"{(\d+):(.*?)}", lambda match: variables.update(
        {int(match.group(1)): eval(match.group(2), {'__builtins__': None}, variables)}), message_text)

    message_text = re.sub(r"{\d+:.*?}", "", message_text)  # Удаляем определения переменных из текста
    message_text = re.sub(r"{\^(\d+)}", lambda match: str(variables.get(int(match.group(1)), "")), message_text)

    return message_text


async def send_mailing_to_other_bots(bot_made, mailing: Mailing, session: AsyncSession):
    try:
        bot = Bot(token=bot_made.bot_token)  # Создаем объект бота
        destination_db_path = f"bot_database_{bot_made.bot_name}.db"  # Path to the new SQLite DB
        destination_engine = create_async_engine(
            f"sqlite+aiosqlite:///{destination_db_path}",
            connect_args={'check_same_thread': False}
        )
        async with destination_engine.begin() as dest_conn:
            DestinationSession = async_sessionmaker(bind=dest_conn, expire_on_commit=False)
            async with DestinationSession() as destination_session:
                users_query = await destination_session.execute(select(User.tg_id))
                user_ids = [user[0] for user in users_query.fetchall()]

        # Вычисляем интервал (например, в минутах) для рассылки
        interval_seconds = int(mailing.interval) if mailing.interval and str(mailing.interval).isdigit() else 1

        # Запускаем процесс рассылки для каждого бота
        await start_mailing_loop(bot_made, bot, mailing, user_ids, session, interval_seconds)

    except Exception as e:
        logging.error(f"Ошибка при рассылке через другие боты: {str(e)}")


async def switch_on_webapp(bot_name, web_app_text, web_app_url, chat_id, session: AsyncSession):
    add_webapp = True
    made_bot_query = await session.execute(select(Made_Bots).where(Made_Bots.bot_id == bot_name))
    made_bot = made_bot_query.scalars().first()
    bot = Bot(token=made_bot.bot_token)
    try:
        if add_webapp:
            commands = [
                BotCommand(command="webapp", description=web_app_text),
                BotCommand(command="start", description="Запуск бота")
            ]
            button = MenuButtonWebApp(text=web_app_text, web_app=WebAppInfo(url=web_app_url))
            await bot.set_chat_menu_button(chat_id=chat_id, menu_button=button)
            print("WebApp button set")
        else:
            await bot.set_chat_menu_button(chat_id=chat_id, menu_button=MenuButtonDefault())
            await bot.delete_my_commands(scope=BotCommandScopeDefault())
            print("Default button set")
    except Exception as e:
        print(f"Error setting WebApp button: {e}")


async def switch_off_webapp(bot_name, web_app_text, web_app_url, chat_id, session: AsyncSession):
    add_webapp = False
    made_bot_query = await session.execute(select(Made_Bots).where(Made_Bots.bot_id == bot_name))
    made_bot = made_bot_query.scalars().first()
    bot = Bot(token=made_bot.bot_token)
    try:
        if add_webapp:
            commands = [
                BotCommand(command="webapp", description=web_app_text),
                BotCommand(command="start", description="Запуск бота")
            ]
            button = MenuButtonWebApp(text=web_app_text, web_app=WebAppInfo(url=web_app_url))
            await bot.set_chat_menu_button(chat_id=chat_id, menu_button=button)
        else:
            await bot.set_chat_menu_button(chat_id=chat_id, menu_button=MenuButtonDefault())
            await bot.delete_my_commands(scope=BotCommandScopeDefault())
    except Exception as e:
        print(f"Error setting WebApp button: {e}")