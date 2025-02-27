import asyncio
import logging
import os
import time
from pathlib import Path
from datetime import datetime
import uuid
import aiofiles
from aiogram import types, Router, F, Bot
from aiogram.filters import CommandStart, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from aiogram.types import CallbackQuery, Message, InlineKeyboardMarkup, InlineKeyboardButton, FSInputFile
from sqlalchemy.ext.asyncio import AsyncSession
from telethon import TelegramClient, functions
from telethon.errors import ChannelPrivateError, ChatGuestSendForbiddenError, SlowModeWaitError, PeerIdInvalidError, \
    ChatWriteForbiddenError, FloodWaitError, SessionPasswordNeededError
from telethon.sessions import StringSession
from states import states
import config
from sqlalchemy import select
from database.models import User, Spammer, SessionData
from middlewares.user_middleware import AuthorizeMiddleware
from keyboards import spammer_parser_keyboard as kb

router = Router()  # Создаем роутер для обработчиков
router.message.middleware(AuthorizeMiddleware())
router.callback_query.middleware(AuthorizeMiddleware())

logger = logging.getLogger(__name__)
SESSION_NAME = "tg_session"
task_storage = {}
PHOTO_DIR = "photos"  # Папка для хранения фото
NAMES_FILE = Path("services/parser/names.txt")
ENDINGS_FILE = Path("services/parser/endings.txt")
active_clients = {}


class AuthUser(StatesGroup):
    api_id = State()
    api_hash = State()
    phone = State()
    code_callback = State()
    password = State()

    texts = {
        "AuthUser:api_id": "Введите ваш api_id:",
        "AuthUser:api_hash": "Введите ваш api_hash:",
        "AuthUser:phone": "Введите ваш номер телефона:",
        "AuthUser:code_callback": "Введите код, который вы получили:",
        "AuthUser:password": "Введите ваш пароль: ",
    }


async def send_telegram_message(bot: Bot, chat_id: int, message: str, edit_message_id: int = None):
    kb = [
        [InlineKeyboardButton(text='Остановить парсинг', callback_data='stop_parsing')]
    ]
    keyboard = InlineKeyboardMarkup(inline_keyboard=kb)
    try:
        if edit_message_id:
            try:
                await bot.edit_message_text(chat_id=chat_id, message_id=edit_message_id, text=message,
                                            disable_web_page_preview=True, reply_markup=keyboard)
            except Exception as e:
                if "message can't be edited" in str(e):
                    # Отправляем новое сообщение вместо редактирования
                    await bot.send_message(chat_id, message, disable_web_page_preview=True, reply_markup=keyboard)
                else:
                    raise e
        else:
            await bot.send_message(chat_id, message, disable_web_page_preview=True, reply_markup=keyboard)
    except Exception as e:
        print(f"Error sending Telegram message: {e}")


import asyncio
import logging
from telethon import TelegramClient, functions


async def run_parser(bot, chat_id: int, message_id: int, client: TelegramClient):
    logging.info("Функция парсинга запущена")
    found_chats = set()
    output_message = "Найденные чаты:\n"
    update_counter = 0  # Счетчик для отправки обновлений боту

    try:
        if not client.is_connected():
            await client.connect()
            logging.info("Клиент подключен")

        # Очистка файла перед записью
        with open("services/parser/output.txt", "w", encoding="utf-8") as file:
            file.write("")

        try:
            with open("services/parser/names.txt", "r", encoding="utf-8") as file:
                names = file.read().splitlines()
            with open("services/parser/endings.txt", "r", encoding="utf-8") as file:
                ends = file.read().splitlines()
        except FileNotFoundError as e:
            logging.error(f"Ошибка при открытии файлов: {e}")
            return

        with open("services/parser/output.txt", "a", encoding="utf-8") as file:
            for title in names:
                for end in ends:
                    name = (title + end).strip()
                    if not name:
                        continue

                    # Проверка на отмену
                    if asyncio.current_task().cancelled():
                        logging.info("Парсинг остановлен.")
                        return

                    try:
                        request = await client(functions.contacts.SearchRequest(q=name, limit=10))
                        for channel in request.chats:
                            if channel.megagroup and channel.username:
                                username = channel.username.lower()

                                if username not in found_chats:
                                    found_chats.add(username)
                                    chat_link = f"t.me/{channel.username}"
                                    file.write(chat_link + "\n")
                                    file.flush()  # Запись в файл сразу

                                    output_message += chat_link + "\n"
                                    update_counter += 1

                                    # Отправляем сообщение боту раз в 5 найденных чатов
                                    if update_counter % 5 == 0:
                                        await send_telegram_message(bot, chat_id, output_message, message_id)

                                    # Пауза для обработки отмены
                                    await asyncio.sleep(0.1)

                    except Exception as e:
                        logging.warning(f"Ошибка при обработке запроса {name}: {e}")

        # Финальное обновление, если есть новые чаты
        if update_counter % 5 != 0:
            await send_telegram_message(bot, chat_id, output_message, message_id)

    except Exception as e:
        logging.error(f"Глобальная ошибка в run_parser: {e}")

    return list(found_chats), output_message


async def read_file(file_path: Path) -> str:
    """Читает содержимое файла и форматирует для отображения."""
    if file_path.exists():
        async with aiofiles.open(file_path, "r", encoding="utf-8") as file:
            content = await file.readlines()
        return ", ".join(line.strip() for line in content if line.strip())
    return "Нет данных"


@router.message(F.text == "📄 Парсинг чатов")
async def parser(message: Message, user: User):
    await message.answer(text='📄 Меню Парсера\n'
                              'Выберите действие:', reply_markup=kb.parser_menu)


@router.callback_query(F.data == 'back_to_spam_parse_menu')
async def back_to_spam_parse_menu(call: CallbackQuery, user: User):
    await call.message.edit_text(text='Выберите действие.', reply_markup=kb.spammer_parser_menu)


@router.callback_query(F.data == 'change_names')
async def change_names(call: CallbackQuery, user: User, state: FSMContext):
    names_list = await read_file(NAMES_FILE)
    await call.message.edit_text(
        text=f'Введите новые имена для парсинга через запятую.\n\n'
             f'Имена, имеющиеся сейчас: {names_list}'
    )
    await state.set_state(states.ParserStates.begin_text)


@router.message(StateFilter(states.ParserStates.begin_text))
async def begin_text(message: Message, user: User, state: FSMContext):
    begin_text = message.text.split(',')  # Разделяем текст по запятым

    file_path = Path("services/parser/names.txt")  # Путь к файлу

    async with aiofiles.open(file_path, "w", encoding="utf-8") as file:
        await file.writelines(f"{name.strip()}\n" for name in begin_text if name.strip())

    await message.answer("Список имен сохранен в файл.", reply_markup=kb.parser_menu)


@router.callback_query(F.data == 'change_endings')
async def change_endings(call: CallbackQuery, user: User, state: FSMContext):
    endings_list = await read_file(ENDINGS_FILE)
    await call.message.edit_text(
        text=f'Введите новые окончания для парсинга через запятую.\n\n'
             f'Окончания, имеющиеся сейчас: {endings_list}'
    )
    await state.set_state(states.ParserStates.end_text)


@router.message(StateFilter(states.ParserStates.end_text))
async def end_text(message: Message, user: User, state: FSMContext):
    end_text = message.text.split(',')  # Разделяем текст по запятым

    file_path = Path("services/parser/endings.txt")  # Путь к файлу

    async with aiofiles.open(file_path, "w", encoding="utf-8") as file:
        await file.writelines(f"{name.strip()}\n" for name in end_text if name.strip())

    await message.answer("Список окончаний сохранен в файл.", reply_markup=kb.parser_menu)


@router.callback_query(F.data == 'start_parsing')
async def start_parsing(call: CallbackQuery, state: FSMContext):
    await call.message.answer("Начинаю подключение к Telegram...")
    bot = call.bot
    chat_id = call.message.chat.id
    message_id = call.message.message_id
    await call.message.answer("Введите номер телефона для авторизации:")
    await state.set_state(AuthUser.phone)


@router.message(StateFilter(AuthUser.phone))
async def process_phone_number(message: types.Message, state: FSMContext, session: AsyncSession):
    phone_number = message.text.strip()
    user_id = message.from_user.id

    if not phone_number.startswith("+") or not phone_number[1:].isdigit():
        await message.answer("Неверный формат номера. Введите номер в формате +79991234567:")
        return

    await state.update_data(phone_number=phone_number)

    # Проверяем существующую сессию в БД
    existing_session = await session.execute(
        select(SessionData).where(SessionData.phone == phone_number)
    )
    existing_session = existing_session.scalars().first()

    if existing_session:
        client = TelegramClient(
            StringSession(existing_session.session_string),
            config.api_id, config.api_hash,
            device_model="GNU/Linux 6.8.0-36-generic x86_64",
            system_version="Ubuntu 24.04 LTS",
            app_version="1.38.1"
        )
        await client.connect()
        if not await client.is_user_authorized():
            sent_code = await client.send_code_request(phone_number)
            await message.answer(AuthUser.texts["AuthUser:code_callback"])
            active_clients[user_id] = client
            await state.update_data(phone_code_hash=sent_code.phone_code_hash)
            await state.set_state(AuthUser.code_callback)
        else:
            new_message = await message.answer("Начинаю парсинг")
            bot = message.bot
            chat_id = message.chat.id
            message_id = new_message.message_id
            parsing_task = asyncio.create_task(run_parser(bot, chat_id, message_id, client))
            task_storage[1] = parsing_task
            await state.clear()
            return

    # Если сессии нет, создаем новую
    client = TelegramClient(
        StringSession(), config.api_id, config.api_hash,
        device_model="GNU/Linux 6.8.0-36-generic x86_64",
        system_version="Ubuntu 24.04 LTS",
        app_version="1.38.1"
    )

    try:
        await client.connect()
        if not await client.is_user_authorized():
            sent_code = await client.send_code_request(phone_number)
            await message.answer(AuthUser.texts["AuthUser:code_callback"])
            active_clients[user_id] = client
            await state.update_data(phone_code_hash=sent_code.phone_code_hash)
            await state.set_state(AuthUser.code_callback)
            return

        # Сохраняем сессию в БД
        session_string = client.session.save()
        async with session.begin():
            existing_session = await session.execute(
                select(SessionData).where(SessionData.phone == phone_number)
            )
            existing_session = existing_session.scalars().first()

            if existing_session:
                existing_session.session_string = session_string
            else:
                phone_number = str(phone_number)
                new_session = SessionData(phone=phone_number, session_string=session_string)
                session.add(new_session)

        new_message = await message.answer("Начинаю парсинг")
        bot = message.bot
        chat_id = message.chat.id
        message_id = new_message.message_id
        parsing_task = asyncio.create_task(run_parser(bot, chat_id, message_id, client))
        task_storage[1] = parsing_task
        await state.clear()
    except FloodWaitError as e:
        logger.error(f"FloodWaitError: необходимо подождать {e.seconds} секунд.")
        await message.answer(f"Пожалуйста, подождите {e.seconds} секунд перед повторной попыткой.")
    except Exception as e:
        logger.error(f"Ошибка при отправке кода: {user_id}: {e}")
        await message.answer(f"Ошибка при отправке кода: {str(e)}. Попробуйте еще раз командой /auth.")
        await state.clear()


@router.message(AuthUser.code_callback)
async def process_code(message: types.Message, state: FSMContext, session: AsyncSession):
    user_id = message.from_user.id
    code = message.text.strip()
    data = await state.get_data()
    phone_code_hash = data.get("phone_code_hash")
    phone_number = data.get("phone_number")
    client = active_clients.get(user_id)
    if client is None:
        logger.info(f"[INFO] Клиент не инициализирован (user_id: {user_id})")
        await message.answer("Клиент не инициализирован. Пожалуйста, начните заново.")
        await state.clear()
        return
    try:
        # Пытаемся войти с кодом подтверждения
        await client.sign_in(phone=phone_number, code=code, phone_code_hash=phone_code_hash)
        logger.info(f"[INFO] user_id: {user_id} успешно вошел в систему.")

        # Сохраняем строку сессии в базе данных
        session_string = client.session.save()
        async with session.begin():
            existing_session = await session.execute(
                select(SessionData).where(SessionData.phone == phone_number)
            )
            existing_session = existing_session.scalars().first()

            if existing_session:
                existing_session.session_string = session_string
            else:
                phone_number = str(phone_number)
                new_session = SessionData(phone=phone_number, session_string=session_string)
                session.add(new_session)

            await session.commit()

        new_message = await message.answer("Начинаю парсинг")
        bot = message.bot
        chat_id = message.chat.id
        message_id = new_message.message_id
        parsing_task = asyncio.create_task(run_parser(bot, chat_id, message_id, client))  # Store the task
        task_storage[1] = parsing_task
        await state.clear()
    except SessionPasswordNeededError:
        logger.info(f"[INFO] Требуется пароль двухфакторной аутентификации для user_id: {user_id}")
        await message.answer(AuthUser.texts["AuthUser:password"])
        await state.set_state(AuthUser.password)
    except Exception as e:
        if "The confirmation code has expired" in str(e):
            await message.answer("Код подтверждения истек")
            del active_clients[user_id]
            await state.clear()
        logger.error(f"Ошибка при входе: {user_id}: {e}")
        await message.answer(f"Ошибка при входе: {str(e)}")
        del active_clients[user_id]
        await state.clear()


@router.message(StateFilter(AuthUser.password))
async def process_password(message: Message, state: FSMContext, session: AsyncSession):
    user_id = message.from_user.id
    password = message.text.strip()
    data = await state.get_data()
    phone_number = data.get("phone_number")

    # Получаем клиента из глобального хранилища
    client = active_clients.get(user_id)

    if client is None:
        logger.info(f"[INFO] Клиент не инициализирован (user_id: {user_id})")
        await message.answer("Клиент не инициализирован. Пожалуйста, начните заново.")
        del active_clients[user_id]
        await state.clear()
        return

    try:
        # Пытаемся войти с паролем
        await client.sign_in(password=password)
        logger.info(f"[INFO] user_id: {user_id} успешно вошел в систему с паролем.")

        # Сохраняем строку сессии в базе данных
        session_string = client.session.save()
        async with session:
            new_session = SessionData(phone=phone_number, session_string=session_string)
            session.add(new_session)
            await session.commit()
        await message.answer("Вы успешно вошли в систему!")
        new_message = await message.answer("Начинаю парсинг")
        bot = message.bot
        chat_id = message.chat.id
        message_id = new_message.message_id
        parsing_task = asyncio.create_task(run_parser(bot, chat_id, message_id, client))  # Store the task
        task_storage[1] = parsing_task
        await state.clear()
        await client.disconnect()
    except Exception as e:
        if "The confirmation code has expired" in str(e):
            await message.answer("Код подтверждения истек. Пожалуйста, начните заново")
        logger.error(f"Ошибка при входе с паролем: {user_id}: {e}")
        await message.answer(f"Ошибка при входе с паролем: {str(e)}. Попробуйте снова")
        await client.disconnect()
        # Удаляем клиента из глобального хранилища
        del active_clients[user_id]
        await state.clear()


@router.callback_query(F.data == 'chats')
async def chats(call: CallbackQuery, user: User):
    chats = await read_file(Path('services/parser/output.txt'))
    await call.message.answer(text=f'Список полученных чатов:\n\n{chats}', reply_markup=kb.chats_menu)


@router.callback_query(F.data == 'stop_parsing')
async def stop_parsing(call: CallbackQuery, state: FSMContext):
    task = task_storage.get(1)
    if task:
        task.cancel()
        await call.message.answer("Запрос на остановку парсинга отправлен...")
        del active_clients[call.from_user.id]
        await state.clear()
    else:
        await call.message.answer("Парсинг не запущен.")


@router.callback_query(F.data == 'download_tg_folder')
async def download_tg_folder_handler(call: CallbackQuery, state: FSMContext):
    file_path = "services/parser/output.txt"
    try:
        if not os.path.exists(file_path) or os.stat(file_path).st_size == 0:  # Check if file exists and is not empty
            await call.message.answer("Файл с чатами пуст или не существует. Сначала запустите парсинг.")
            return

        await call.message.answer_document(types.FSInputFile(file_path),
                                           caption="Файл с найденными чатами")  # Send the file
    except Exception as e:
        await call.message.answer(f"❌ Ошибка отправки файла: {e}")
