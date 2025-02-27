import asyncio
import logging
import os
import time
from pathlib import Path
from datetime import datetime
import uuid
from pyrogram import Client as PyroClient
from pyrogram.raw.functions.chatlists import CheckChatlistInvite
import aiofiles
from aiogram import types, Router, F, Bot
from aiogram.filters import CommandStart, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from aiogram.types import CallbackQuery, Message, InlineKeyboardMarkup, InlineKeyboardButton, FSInputFile
from pyrogram.raw.types import PeerChannel, PeerChat, PeerUser
from sqlalchemy.ext.asyncio import AsyncSession
from telethon.tl.functions.channels import GetChannelsRequest
from telethon.tl.types import MessageEntityCustomEmoji
from telethon.tl.types import Chat, Channel
from telethon.types import ExportedChatlistInvite
from telethon import TelegramClient, functions
from telethon.errors import ChannelPrivateError, ChatGuestSendForbiddenError, SlowModeWaitError, PeerIdInvalidError, \
    ChatWriteForbiddenError, FloodWaitError, SessionPasswordNeededError, RPCError
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
task_storage_spam = {}
PHOTO_DIR = "photos"  # Папка для хранения фото
NAMES_FILE = Path("services/parser/names.txt")
ENDINGS_FILE = Path("services/parser/endings.txt")
active_clients = {}


class SpammerState(StatesGroup):
    waiting_for_message = State()
    waiting_for_delay = State()
    waiting_for_cycle_delay = State()


class AddSessionState(StatesGroup):
    api_id = State()
    api_hash = State()
    phone = State()
    code_callback = State()
    password = State()
    phone_for_delete = State()

    texts = {
        "AuthUser:api_id": "Введите ваш api_id:",
        "AuthUser:api_hash": "Введите ваш api_hash:",
        "AuthUser:phone": "Введите ваш номер телефона:",
        "AuthUser:code_callback": "Введите код, который вы получили:",
        "AuthUser:password": "Введите ваш пароль: ",
    }


class StartSpamStates(StatesGroup):
    message_type = State()
    message_edit = State()
    chat_type = State()
    chats_from_link = State()
    phone_for_chats = State()


@router.message(F.text == "📝 Спам-рассылка")
async def spammer_callback(message: Message, session: AsyncSession):
    result = await session.execute(select(Spammer).where(Spammer.user_tg_id == message.from_user.id))
    spammer = result.scalars().first()

    if not spammer:
        spammer = Spammer(user_tg_id=message.from_user.id)
        session.add(spammer)
        await session.commit()
    await message.answer("Вы в спам меню\n"
                         "Выберите действие:", reply_markup=kb.spammer_menu)


@router.callback_query(F.data == "spammer_delay")
async def spammer_delay_callback(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    async with session:
        spammer_query = await session.execute(select(Spammer).where(Spammer.user_tg_id == callback.from_user.id))
        spammer = spammer_query.scalars().first()
    await callback.message.edit_text(f"Задержка между сообщениями: <code>{spammer.message_delay} сек</code>\n"
                                     f"Задержка между циклами: <code>{spammer.cycle_delay} сек</code>\n\n"
                                     "Введите задержку между сообщениями в секундах:",
                                     reply_markup=kb.back_to_spam_menu)
    await state.set_state(SpammerState.waiting_for_delay)


@router.message(SpammerState.waiting_for_delay)
async def process_new_spammer_delay(message: Message, state: FSMContext, session: AsyncSession):
    new_delay = message.text

    # Проверка, что введено число
    if not new_delay.isdigit():
        await message.answer("Пожалуйста, введите корректное число.")
        return

    new_delay = int(new_delay)
    # Обновление задержки в базе данных
    async with session:
        spammer_query = await session.execute(select(Spammer).where(Spammer.user_tg_id == message.from_user.id))
        spammer = spammer_query.scalars().first()

        if spammer:
            spammer.message_delay = new_delay
            await session.commit()

    await message.answer(f"Задержка между сообщениями была обновлена на {new_delay} секунд.")
    await message.answer(f"Введите задержку между циклами в секундах:")
    await state.set_state(SpammerState.waiting_for_cycle_delay)


@router.message(SpammerState.waiting_for_cycle_delay)
async def process_new_spammer_delay(message: Message, state: FSMContext, session: AsyncSession):
    new_delay = message.text

    # Проверка, что введено число
    if not new_delay.isdigit():
        await message.answer("Пожалуйста, введите корректное число.")
        return

    new_delay = int(new_delay)
    # Обновление задержки в базе данных
    async with session:
        spammer_query = await session.execute(select(Spammer).where(Spammer.user_tg_id == message.from_user.id))
        spammer = spammer_query.scalars().first()

        if spammer:
            spammer.cycle_delay = new_delay
            await session.commit()

    await message.answer(f"Задержка между циклами была обновлена на {new_delay} секунд.")
    await message.answer("Вы в спам меню\n"
                         "Выберите действие:", reply_markup=kb.spammer_menu)


@router.callback_query(F.data == 'add_session')
async def add_new_session(call: CallbackQuery, state: FSMContext):
    await call.message.edit_text('Авторизация для создания новой сессии', parse_mode='HTML')
    await call.message.answer("Отправьте ваш номер телефона")
    await state.set_state(AddSessionState.phone)


@router.message(StateFilter(AddSessionState.phone))
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
            await message.answer("Сессия не активна. Пожалуйста, авторизуйтесь заново, следуйте шагам ниже:")
            sent_code = await client.send_code_request(phone_number)
            await message.answer(AddSessionState.texts["AuthUser:code_callback"])
            active_clients[user_id] = client
            await state.update_data(phone_code_hash=sent_code.phone_code_hash)
            await state.set_state(AddSessionState.code_callback)
            return
        else:
            await state.update_data(phone_number=phone_number)
            await message.answer("На этот номер уже зарегестрирована сессия! Вы желаете её удалить?",
                                 reply_markup=kb.delete_session)
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
            await message.answer(AddSessionState.texts["AuthUser:code_callback"])
            active_clients[user_id] = client
            await state.update_data(phone_code_hash=sent_code.phone_code_hash)
            await state.set_state(AddSessionState.code_callback)
            return
    except FloodWaitError as e:
        logger.error(f"FloodWaitError: необходимо подождать {e.seconds} секунд.")
        await message.answer(f"Пожалуйста, подождите {e.seconds} секунд перед повторной попыткой.")
    except Exception as e:
        logger.error(f"Ошибка при отправке кода: {user_id}: {e}")
        await message.answer(f"Ошибка при отправке кода: {str(e)}. Попробуйте еще раз командой /auth.")
        await state.clear()


@router.message(AddSessionState.code_callback)
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

        new_message = await message.answer("Сессия была успешно сохранена!")
        await state.clear()
    except SessionPasswordNeededError:
        logger.info(f"[INFO] Требуется пароль двухфакторной аутентификации для user_id: {user_id}")
        await message.answer(AddSessionState.texts["AuthUser:password"])
        await state.set_state(AddSessionState.password)
    except Exception as e:
        if "The confirmation code has expired" in str(e):
            await message.answer("Код подтверждения истек")
        logger.error(f"Ошибка при входе: {user_id}: {e}")
        await message.answer(f"Ошибка при входе: {str(e)}")


@router.message(StateFilter(AddSessionState.password))
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
        logger.info(f"[INFO] user_id: {user_id} успешно вошел в систему с паролем. ")

        # Сохраняем строку сессии в базе данных
        session_string = client.session.save()
        async with session:
            new_session = SessionData(phone=phone_number, session_string=session_string)
            session.add(new_session)
            await session.commit()
        await message.answer("Вы успешно вошли в систему! Ваша сессия сохранена")
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


@router.callback_query(F.data == 'delete_session')
async def delete_session(call: CallbackQuery, state: FSMContext, session: AsyncSession):
    await call.message.answer("Отправьте ваш номер телефона чтобы найти сессию")
    await state.set_state(AddSessionState.phone_for_delete)


@router.message(StateFilter(AddSessionState.phone_for_delete))
async def process_phone_number(message: types.Message, state: FSMContext, session: AsyncSession):
    phone_number = message.text.strip()
    if not phone_number.startswith("+") or not phone_number[1:].isdigit():
        await message.answer("Неверный формат номера. Введите номер в формате +79991234567:")
        return
    async with session.begin():
        existing_session = await session.execute(
            select(SessionData).where(SessionData.phone == phone_number)
        )
        existing_session = existing_session.scalars().first()

        if existing_session:
            await state.update_data(phone_number=phone_number)
            await message.answer("Вы действительно хотите удалить сессию?", reply_markup=kb.delete_session)
        else:
            await message.answer("Сессия не найдена. Попробуйте еще раз или введите другой номер.")


@router.callback_query(F.data == 'session_delete_confirm')
async def delete_session_confirm(call: CallbackQuery, state: FSMContext, session: AsyncSession):
    data = await state.get_data()
    phone_number = data.get("phone_number")
    async with session.begin():
        existing_session = await session.execute(
            select(SessionData).where(SessionData.phone == phone_number)
        )
        existing_session = existing_session.scalars().first()

        if existing_session:
            await session.delete(existing_session)
            await session.commit()
            await call.message.answer("Сессия успешно удалена.")
        else:
            await call.message.answer("Сессия не найдена.")
    await state.clear()


@router.callback_query(F.data == "back_to_spam_menu")
async def back_to_spam_menu_callback(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.edit_text("Вы в спам меню\n"
                                     "Выберите действие:", reply_markup=kb.spammer_menu)


@router.callback_query(F.data == "start_spam")
async def start_spam_callback(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    await callback.message.answer("Выберите способ отправки текста для рассылки", reply_markup=kb.start_spammer_menu)


@router.callback_query(F.data == 'manual_message')
async def manual_message_callback(call: CallbackQuery, state: FSMContext, session: AsyncSession, bot: Bot):
    await state.update_data(message_type='1')
    async with session:
        spammer_query = await session.execute(select(Spammer).where(Spammer.user_tg_id == call.from_user.id))
        spammer = spammer_query.scalars().first()
        if spammer:
            if spammer.message_photo:
                await bot.send_photo(call.from_user.id, FSInputFile(spammer.message_photo),
                                     caption=f"Текущее сообщение: {spammer.message_text}", parse_mode='HTML')
            else:
                await bot.send_message(call.from_user.id, f"Текущее сообщение: {spammer.message_text}",
                                       parse_mode='HTML')
        await call.message.answer("Введите новое сообщение (вместе с фото, если хотите) :")
        await state.set_state(StartSpamStates.message_edit)


@router.message(StateFilter(StartSpamStates.message_edit))
async def change_message(message: Message, state: StartSpamStates.message_edit, session: AsyncSession, bot: Bot):
    answer = message.caption if message.photo else message.text
    photo_path = None
    if message.photo:
        file_id = message.photo[-1].file_id
        file_info = await message.bot.get_file(file_id)
        file_ext = file_info.file_path.split('.')[-1]  # Получаем расширение файла
        unique_filename = f"{uuid.uuid4()}.{file_ext}"
        photo_path = os.path.join(PHOTO_DIR, unique_filename)
        await message.bot.download_file(file_info.file_path, photo_path)
    async with session:
        spammer_query = await session.execute(select(Spammer).where(Spammer.user_tg_id == message.from_user.id))
        spammer = spammer_query.scalars().first()
        spammer.message_text = answer
        spammer.message_photo = photo_path
        await session.commit()
        await message.answer("Выберите режим чатов для отправки сообщения:", reply_markup=kb.choose_chats)


@router.callback_query(F.data == 'saved_message')
async def saved_message_callback(call: CallbackQuery, state: FSMContext, session: AsyncSession, bot: Bot):
    await state.update_data(message_type="2")
    await call.message.answer("Выберите режим чатов для отправки сообщения:", reply_markup=kb.choose_chats)


@router.callback_query(F.data == 'back_to_start_menu')
async def back_to_start_menu(call: CallbackQuery):
    await call.message.answer("Выберите способ отправки текста для рассылки", reply_markup=kb.start_spammer_menu)


@router.callback_query(F.data.startswith('chats|'))
async def chats_from_parser_callback(call: CallbackQuery, state: FSMContext, session: AsyncSession):
    chat_type = call.data.split('|')[1]
    await state.update_data(chat_type=chat_type)
    data = await state.get_data()
    if chat_type == '1':
        with open("services/parser/output.txt", "r", encoding="utf-8") as file:
            chats = [line.strip() for line in file if line.strip()]
            await state.update_data(chats=chats)
            await call.message.answer("Отправьте номер телефона:")
            await state.set_state(StartSpamStates.phone_for_chats)
    elif chat_type == '2':
        await call.message.answer("Отправьте номер телефона:")
        await state.set_state(StartSpamStates.phone_for_chats)
        return
    elif chat_type == '3':
        await call.message.answer("Отправьте номер телефона:")
        await state.set_state(StartSpamStates.phone_for_chats)
        return


async def get_chats_from_folder(client, folder_link: str):
    """Получает список чатов и их ID из Telegram-папки по ссылке t.me/addlist/..."""
    folder_hash = folder_link.replace("https://t.me/addlist/", "").strip()
    chat_links = []
    chat_ids = []

    if not client.is_connected():
        await client.connect()

    try:
        # Отправляем запрос к Telegram API
        result = await client(functions.chatlists.CheckChatlistInviteRequest(slug=folder_hash))

        # Добавляем ID из missing_peers и already_peers
        if hasattr(result, "missing_peers"):
            chat_ids.extend([peer.channel_id for peer in result.missing_peers])

        if hasattr(result, "already_peers"):
            chat_ids.extend([peer.channel_id for peer in result.already_peers])

        # Добавляем ID из chats
        if hasattr(result, "chats"):
            chat_ids.extend([chat.id for chat in result.chats])

        for chat_id in set(chat_ids):  # Убираем дубликаты
            try:
                channel = await client.get_entity(chat_id)
                if channel.username:
                    chat_link = f"https://t.me/{channel.username}"
                    chat_links.append(chat_link)
                else:
                    continue
            except Exception as e:
                logger.info(f"Ошибка при получении ссылки для чата {chat_id}: {e}")
                continue

        return chat_links

    except Exception as e:
        logger.info(f"Ошибка при получении ID чатов из папки: {e}")
        return []


async def get_group_chat_links(client):
    if not client.is_connected():
        await client.connect()
        dialogs = await client.get_dialogs()

        chat_links = []
        for dialog in dialogs:
            entity = dialog.entity
            if isinstance(entity, Chat):  # Обычные группы
                link = f"https://t.me/c/{entity.id}"
            elif isinstance(entity, Channel) and entity.megagroup:  # Супергруппы
                link = f"https://t.me/{entity.username}" if entity.username else f"https://t.me/c/{entity.id}"
            else:
                continue  # Пропускаем другие типы чатов

            chat_links.append(link)

        return chat_links


@router.message(StateFilter(StartSpamStates.phone_for_chats))
async def get_phone_for_chats(message: Message, state: FSMContext, session: AsyncSession):
    phone_number = message.text
    if not phone_number.startswith("+") or not phone_number[1:].isdigit():
        await message.answer("Неверный формат номера. Введите номер в формате +9991234567:")
        return
    await state.update_data(phone_number=phone_number)
    async with session:
        existing_session = await session.execute(
            select(SessionData).where(SessionData.phone == phone_number)
        )
        existing_session = existing_session.scalars().first()
        if existing_session:
            data = await state.get_data()
            chat_type = data.get("chat_type")
            message_type = data.get('message_type')
            if chat_type == '1':
                chats = data.get("chats")
                print(chats)
                await message.answer(text=f'<b>Способ получения сообщения:</b> Сообщение вручную\n'
                                          f'<b>Способ получения чатов:</b> Сохраненные чаты\n'
                                          f'<b>Было найдено</b><code> {len(chats)} </code><b>чатов</b>',
                                     parse_mode='HTML', reply_markup=kb.confirm_start_spam)
            if chat_type == '2':
                await message.answer("Отправьте ссылку на папку в формате (https://t.me/addlist/):")
                await state.set_state(StartSpamStates.chats_from_link)
            elif chat_type == '3':
                client = TelegramClient(
                    StringSession(existing_session.session_string), config.api_id, config.api_hash,
                    device_model="GNU/Linux 6.8.0-36-generic x86_64",
                    system_version="Ubuntu 24.04 LTS",
                    app_version="1.38.1"
                )
                chats = await get_group_chat_links(client)
                await state.update_data(chats=chats)
                if message_type == '1':
                    message_type = 'Сообщение вручную'
                elif message_type == '2':
                    message_type = 'Сообщение из избранного'
                await message.answer(text=f'<b>Способ получения сообщения:</b> {message_type}\n'
                                          f'<b>Способ получения чатов:</b> Чаты пользователя\n'
                                          f'<b>Было найдено</b><code> {len(chats)} </code><b>чатов</b>',
                                     parse_mode='HTML', reply_markup=kb.confirm_start_spam)


@router.message(StateFilter(StartSpamStates.chats_from_link))
async def chats_from_link(message: Message, state: FSMContext, session: AsyncSession, bot: Bot):
    link = message.text
    if not link.startswith("https://t.me/addlist/"):
        await message.answer("Неверный формат ссылки. Попробуйте еще раз")
        return
    data = await state.get_data()
    phone_number = data.get("phone_number")
    message_type = data.get('message_type')
    async with session:
        existing_session = await session.execute(
            select(SessionData).where(SessionData.phone == phone_number)
        )
        existing_session = existing_session.scalars().first()
    client = TelegramClient(
        StringSession(existing_session.session_string), config.api_id, config.api_hash,
        device_model="GNU/Linux 6.8.0-36-generic x86_64",
        system_version="Ubuntu 24.04 LTS",
        app_version="1.38.1"
    )
    chats = await get_chats_from_folder(client, link)
    await state.update_data(chats=chats)
    chat_type = '2'
    await state.update_data(chat_type=chat_type)
    if message_type == '1':
        message_type = 'Сообщение вручную'
    elif message_type == '2':
        message_type = 'Сообщение из избранного'
    await message.answer(text=f'<b>Способ получения сообщения:</b> {message_type}\n'
                              f'<b>Способ получения чатов:</b> Чаты из папки\n'
                              f'<b>Было найдено</b><code> {len(chats)} </code><b>чатов</b>',
                         parse_mode='HTML', reply_markup=kb.confirm_start_spam)


@router.callback_query(F.data == 'start_spamming')
async def start_spamming(call: CallbackQuery, state: FSMContext, session: AsyncSession, bot: Bot):
    message_text = None
    message_photo = None
    data = await state.get_data()
    phone_number = data.get("phone_number")
    print("Номер телефона: ", phone_number)
    message_type = data.get('message_type')
    print("Тип сообщения: ", message_type)
    chats = data.get("chats")
    async with session:
        spammer_query = await session.execute(select(Spammer).where(Spammer.user_tg_id == call.from_user.id))
        spammer = spammer_query.scalars().first()
        existing_session = await session.execute(
            select(SessionData).where(SessionData.phone == phone_number)
        )
        existing_session = existing_session.scalars().first()

        # Убедитесь, что spammer и existing_session существуют
        if spammer and existing_session:
            client = TelegramClient(
                StringSession(existing_session.session_string), config.api_id, config.api_hash,
                device_model="GNU/Linux 6.8.0-36-generic x86_64",
                system_version="Ubuntu 24.04 LTS",
                app_version="1.38.1"
            )
        else:
            await call.message.answer('Не удалось найти сессию или спамера, попробуйте позже.')
            return  # Прерываем выполнение, если нет данных

        user_id = call.from_user.id
        message_delay = spammer.message_delay
        cycle_delay = spammer.cycle_delay
        await call.message.answer('Начинаю рассылку', reply_markup=kb.stop_spam)
        chat_id = call.message.message_id

    # Обработка сообщений в зависимости от типа
    if message_type == '1':
        message_text = spammer.message_text
        message_photo = spammer.message_photo if spammer.message_photo else None
    elif message_type == '2':
        message_text, message_photo = await get_last_saved_message(client)

    # Запуск задачи рассылки
    spamming_task = asyncio.create_task(
        send_messages(client, message_text, message_photo, chats, cycle_delay, message_delay, bot, user_id, chat_id)
    )
    task_storage_spam[user_id] = spamming_task
    await state.clear()


def log_message(status, chat, message):
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    logger.info(f"[{now}] [{status}] Чат: {chat} | Сообщение: {message}")
    print(f"[{now}] [{status}] Чат: {chat} | Сообщение: {message}")




async def get_last_saved_message(client):
    """Получает последнее сообщение из Избранного с премиум-эмодзи."""
    async with client:
        messages = await client.get_messages("me", limit=1)
        if messages:
            msg = messages[0]
            text = msg.text if msg.text else ""
            photo = msg.media if msg.media else None

            if msg.entities:
                for entity in msg.entities:
                    if isinstance(entity, MessageEntityCustomEmoji):
                        emoji_id = entity.document_id
                        text += f" [Premium Emoji: {emoji_id}]"

            return text, photo
        return None, None


async def send_telegram_message(bot: Bot, chat_id: int, message: str, edit_message_id: int = None):
    kb = [
        [InlineKeyboardButton(text='❌ Остановить рассылку', callback_data='stop_spam')]
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
                    await bot.send_message(chat_id=chat_id, text=message, disable_web_page_preview=True, reply_markup=keyboard)
                else:
                    raise e
        else:
            await bot.send_message(chat_id=chat_id, text=message, disable_web_page_preview=True, reply_markup=keyboard)
    except Exception as e:
        print(f"Error sending Telegram message: {e}")


async def send_messages(client, message_text, photo_path, chats, cycle_delay, message_delay, bot, user_id,
                        edit_message_id):
    if not client.is_connected():
        await client.connect()
        try:
            while True:
                for chat in chats:
                    try:
                        if message_text and photo_path:
                            await client.send_file(chat, photo_path, caption=message_text)
                            await send_telegram_message(bot, user_id, f"Сообщение с фото отправлено в чат {chat}",
                                                        edit_message_id)
                        elif message_text:
                            await client.send_message(chat, message_text)
                            await send_telegram_message(bot, user_id, f"Сообщение отправлено в чат {chat}",
                                                        edit_message_id)
                        await asyncio.sleep(message_delay)
                    except ChannelPrivateError:
                        log_message("ERROR", chat, "Чат закрыт")
                    except ChatGuestSendForbiddenError:
                        log_message("ERROR", chat, "Требуется вступить в группу перед отправкой сообщений")
                        continue
                    except ChatWriteForbiddenError:
                        log_message("ERROR", chat, "Нет прав на отправку сообщений")
                    except SlowModeWaitError:
                        log_message("SLOWMODE", chat, "Пропущено из-за slowmode")
                        continue
                    except PeerIdInvalidError:
                        log_message("ERROR", chat, "Чат недоступен")
                        continue
                    except RPCError as e:
                        if "TOPIC_CLOSED" in str(e):
                            log_message("ERROR", chat, "Чат закрыт (TOPIC_CLOSED)")
                            continue  # Пропустить этот чат
                        else:
                            continue  # Перехватить другие ошибки
                    except Exception as e:
                        log_message("ERROR", chat, f"Произошла ошибка: {e}")
                        continue
                print(f"[INFO] Цикл завершён. Ожидание {cycle_delay} секунд.")
                await asyncio.sleep(cycle_delay)
        except Exception as e:
            print(f"Произошла ошибка: {e}")


@router.callback_query(F.data == "stop_spam")
async def stop_spam_callback(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    try:
        user_id = callback.from_user.id
        spamming_task = task_storage_spam[user_id]
        if spamming_task:
            spamming_task.cancel()  # Останавливаем задачу
            await callback.message.answer("❌ Спам рассылка остановлена!")
        else:
            await callback.message.answer("🚫 Спам рассылка уже остановлена или не запущена.")
    except Exception as e:
        await callback.message.answer(f"❌ Ошибка при остановке спам рассылки: {e}")
