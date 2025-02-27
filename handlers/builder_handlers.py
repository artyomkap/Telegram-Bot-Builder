import asyncio
import json
import logging
import os
import random
import signal
import string
import subprocess
import sys
import time
import uuid
from typing import Optional
from handlers import control_made_bot
import requests
from aiogram import types, Router, F, Bot
from aiogram.filters import StateFilter
from aiogram.filters.callback_data import CallbackData
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message, FSInputFile, InlineKeyboardMarkup, InlineKeyboardButton, BotCommand, \
    BotCommandScopeDefault
from aiogram.utils.keyboard import InlineKeyboardBuilder
from fastapi.responses import JSONResponse
from sqlalchemy import and_
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
import os
import sys
import subprocess
import logging


import utils
from database import crud
from database.models import User, Made_Bots, Mailing
from keyboards import main_keyboard, builder_keyboard
from middlewares.user_middleware import AuthorizeMiddleware
from states import states

bot_instances = {}
router = Router()  # Создаем роутер для обработчиков
router.message.middleware(AuthorizeMiddleware())
router.callback_query.middleware(AuthorizeMiddleware())
PHOTO_DIR = "photos"  # Папка для хранения фото
os.makedirs(PHOTO_DIR, exist_ok=True)



async def bot_start(new_bot):
    if new_bot.bot_id in bot_instances:
        logging.info(f"{new_bot.bot_name} уже запущен.")
        return

    bot_path = os.path.join("created_bots", str(new_bot.bot_id), "main.py")
    log_file = os.path.join("created_bots", str(new_bot.bot_id), "bot.log")

    env = os.environ.copy()
    env["PYTHONPATH"] = os.path.abspath(os.path.dirname(__file__))  # Добавляем корневую директорию проекта в PYTHONPATH

    with open(log_file, "w") as log:
        process = subprocess.Popen(
            [sys.executable, bot_path],
            stdout=log,
            stderr=log,
            start_new_session=True,  # Запускаем в новой сессии, чтобы избежать зомби-процесса
            env=env  # Передаем переменные окружения
        )

    logging.info(f"Бот {new_bot.bot_name} запущен с PID {process.pid}.")
    new_bot.process = str(process.pid)
    new_bot.is_working = True


async def stop_bot(new_bot):
    """Остановка бота."""
    pid = int(new_bot.process)  # Convert PID to integer
    os.kill(pid, signal.SIGTERM)  # Or signal.SIGKILL if needed
    new_bot.process = None  # Clear the PID in the database
    new_bot.is_working = False
    logging.info(f"Бот {new_bot.bot_name} остановлен.")


async def load_bot_page(session: AsyncSession, bot_id, bot: Bot, user: User):
    async with session:
        new_bot_query = await session.execute(select(Made_Bots).where(Made_Bots.id == bot_id))
        new_bot = new_bot_query.scalars().first()
        keyboard = await builder_keyboard.get_bot_settings_kb(new_bot)
        # domain_query = await session.execute(select(Domains).where(Domains.id == new_bot.domain_id))
        # domain = domain_query.scalars().first()
        buttons_text = ""
        if new_bot.buttons:
            try:
                buttons_data = json.loads(new_bot.buttons)
                for i, button in enumerate(buttons_data):
                    buttons_text += f"{button.get('text', 'Кнопка')} ({button.get('type', 'text')})\n"
            except json.JSONDecodeError:
                buttons_text = "Ошибка: Некорректный формат кнопок"
        else:
            buttons_text = "Кнопок нет"

        # Форматирование стартового текста
        start_text = new_bot.start_message or "Стартовый текст не установлен"

        text = (f'⚙️ Настройки бота: {new_bot.bot_id}\n\n'
                f'<b>🤖 Юзернейм:</b> @{new_bot.bot_name}\n'
                f'<b>🌐 Домен:</b> {new_bot.web_app_link}\n'
                f'<b>💬 Текст кнопки WebApp:</b> {new_bot.web_app_button}\n\n'
                f'<b>🖥 Кнопки:</b> <pre>{buttons_text}</pre>\n\n'
                f'<b>📝Стартовый текст:</b> <pre>{start_text}</pre>\n'
                f'После изменения настроек, нажимайте обновить!')

        await bot.send_message(user.tg_id, text, parse_mode="HTML", reply_markup=keyboard)


@router.message(F.text == '🤖 Конструктор ботов')
async def bots_constructor(message: Message, session: AsyncSession, user: User):
    kb = await builder_keyboard.get_bot_menu_kb(session, user)
    await message.answer('🤖 Выберите нужного бота или создайте нового', reply_markup=kb)


@router.callback_query(F.data == 'create_bot')
async def create_bot(call: CallbackQuery, session: AsyncSession, user: User, state: FSMContext):
    if call.data == 'create_bot':
        await call.message.edit_text('💁‍♂️ Введите домен для WebApp')
        await state.set_state(states.NewBotState.web_app_link)


@router.message(StateFilter(states.NewBotState.web_app_link))
async def create_bot_webapp(message: Message, state: FSMContext, session: AsyncSession, user: User):
    web_app_link = message.text
    await state.update_data(web_app_link=web_app_link)
    await message.answer('✏️ Введите токен для кастомного бота', reply_markup=builder_keyboard.back_to_bot)
    await state.set_state(states.NewBotState.bot_token)


@router.message(StateFilter(states.NewBotState.bot_token))
async def create_bot_token(message: Message, state: FSMContext, session: AsyncSession, user: User):
    bot_token = message.text
    await state.update_data(bot_token=bot_token)
    await message.answer(text='Ожидайте создания бота и инициализации (около 30 секунд).')
    async with session:
        max_bot_id_query = await session.execute(select(func.max(Made_Bots.id)))
        max_id = max_bot_id_query.scalar() or 0
        new_id = max_id + 1
        letters = string.ascii_lowercase
        name = ''.join(random.choice(letters) for i in range(5))
        new_bot = Made_Bots(
            bot_id="bot_" + name,
            bot_name='bot_' + name,  # Correct: Convert new_bot_id to string
            bot_token=bot_token,
            user_tg_id=user.tg_id,
        )

        data = await state.get_data()
        web_app_link = data.get('web_app_link')
        if web_app_link:
            new_bot.web_app_link = web_app_link

        session.add(new_bot)
        await session.commit()
        await session.refresh(new_bot)
        await asyncio.sleep(1)
        async with session:
            await utils.create_project_structure(new_bot.bot_id, new_bot.id, session)
            await bot_start(new_bot)
            await session.commit()
            time.sleep(25)
            await crud.copy_bot_data(new_bot.bot_id, new_bot.id)
            await stop_bot(new_bot)
            await session.commit()
            await message.answer(f"✅ Кастомный бот добавлен!\n"
                                 f"🆔 ID:{new_bot.bot_id}",
                                 reply_markup=await builder_keyboard.go_to_bot_setting(new_bot))


@router.callback_query(F.data.startswith('bot_settings|'))
async def bot_settings(call: CallbackQuery, session: AsyncSession, user: User, state: FSMContext):
    bot_id = call.data.split('|')[1]
    await state.update_data(bot_id=bot_id)
    async with session:
        new_bot_query = await session.execute(select(Made_Bots).where(Made_Bots.id == bot_id))
        new_bot = new_bot_query.scalars().first()
        keyboard = await builder_keyboard.get_bot_settings_kb(new_bot)
        buttons_text = ""
        if new_bot.buttons:
            try:
                buttons_data = json.loads(new_bot.buttons)
                for i, button in enumerate(buttons_data):
                    buttons_text += f"{button.get('text', 'Кнопка')} ({button.get('type', 'text')})\n"
            except json.JSONDecodeError:
                buttons_text = "Ошибка: Некорректный формат кнопок"
        else:
            buttons_text = "Кнопок нет"

        # Форматирование стартового текста
        start_text = new_bot.start_message or "Стартовый текст не установлен"

        text = (f'⚙️ Настройки бота: {new_bot.bot_id}\n\n'
                f'<b>🤖 Юзернейм:</b> @{new_bot.bot_name}\n'
                f'<b>🌐 Домен:</b> {new_bot.web_app_link}\n'
                f'<b>💬 Текст кнопки WebApp:</b> {new_bot.web_app_button}\n\n'
                f'<b>🖥 Кнопки:</b> <pre>{buttons_text}</pre>\n\n'
                f'<b>📝Стартовый текст:</b> <pre>{start_text}</pre>\n'
                f'После изменения настроек, нажимайте обновить!')

        await call.message.edit_text(text, parse_mode="HTML", reply_markup=keyboard)


@router.callback_query(F.data.startswith('bot_answers|'))
async def bot_answer_settings(call: CallbackQuery, session: AsyncSession, user: User, state: FSMContext):
    bot_id = call.data.split('|')[1]
    await state.update_data(bot_id=bot_id)
    await call.message.edit_text(text='💁‍♂️ Выберите действие:', reply_markup=builder_keyboard.bot_answers_setting)


@router.callback_query(F.data == 'change_message_bot')
async def change_message_bot(call: CallbackQuery, state: FSMContext):
    await call.message.edit_text(
        text='📝 Отправьте новый <b>стартовый</b> текст для вашего бота. '
             'Вы также можете прикрепить изображение.\n\n'
             '<i>(Поддерживается HTML-форматирование)</i>\n\n'
             '🔄 Базовые переменные:\n\n'
             '👤 Информация о пользователе: \n'
             ' └ {first_name} - имя\n'
             ' └ {last_name} - фамилия  \n'
             ' └ {username} - юзернейм без @\n'
             ' └ {@username} - юзернейм с @\n'
             ' └ {telegram_id} - ID пользователя\n\n'
             '🎲 Дополнительные функции:\n'
             ' └ {random(x,y)} - случайное число от x до y\n'
             ' └ {1: выражение} - сохранить результат в переменную 1\n'
             ' └ {2: ^1 * 2} - использовать значение переменной 1\n\n'
             '<i>*Пустые поля заменяются на пустую строку</i>',
        parse_mode='HTML',
        reply_markup=builder_keyboard.back_to_bot
    )
    await state.set_state(states.NewBotState.start_text)


@router.message(StateFilter(states.NewBotState.start_text))
async def change_message_bot_text(message: Message, session: AsyncSession, state: FSMContext):
    bot_id = int((await state.get_data()).get('bot_id'))
    text = message.caption if message.photo else message.text

    photo_path = None
    if message.photo:
        file_id = message.photo[-1].file_id
        file_info = await message.bot.get_file(file_id)
        file_ext = file_info.file_path.split('.')[-1]  # Получаем расширение файла
        unique_filename = f"{uuid.uuid4()}.{file_ext}"
        photo_path = os.path.join(PHOTO_DIR, unique_filename)

        await message.bot.download_file(file_info.file_path, photo_path)

    async with session:
        bot_query = await session.execute(select(Made_Bots).where(Made_Bots.id == bot_id))
        bot_made = bot_query.scalars().first()
        bot_made.start_message = text
        bot_made.start_photo = photo_path  # Сохраняем путь в БД
        await session.commit()
    await crud.copy_bot_data(bot_made.bot_id, bot_made.id)
    await message.answer("✅ Стартовый текст изменен!", reply_markup=main_keyboard.main_menu)
    await state.clear()


@router.callback_query(F.data == 'back_to_bot_choice')
async def back_to_bot_choice(call: CallbackQuery, user: User, state: FSMContext):
    if call.data == 'back_to_bot_choice':
        await call.message.edit_text(text='💁‍♂️ Выберите действие:', reply_markup=builder_keyboard.bot_answers_setting)


@router.callback_query(F.data == 'manage_buttons_bot')
async def manage_buttons_bot(call: CallbackQuery, session: AsyncSession, user: User, state: FSMContext):
    if call.data == 'manage_buttons_bot':
        bot_id = (await state.get_data()).get('bot_id')
        async with session:
            bot = await session.get(Made_Bots, bot_id)  # Получаем объект бота из базы данных
            kb = await builder_keyboard.get_manage_buttons_menu(bot)
            if bot and bot.buttons:  # Проверяем, есть ли у бота кнопки
                buttons_data = json.loads(bot.buttons)  # Загружаем JSON с данными о кнопках
                buttons_text = ""
                for i, button in enumerate(buttons_data):
                    if button['type'] == 'text':
                        buttons_text += f"{i + 1}. <code>{button['text']}</code>\n"  # Форматируем текст кнопки
                await call.message.edit_text(
                    text='<b> Управление кнопками:</b>\n'
                         ' └ Используйте кнопки ниже для настройки функциональности и внешнего вида\n\n'
                         '<b>⌨️ Типы кнопок:</b>\n'
                         ' └ 💬 Текст - отправляет новое сообщение\n'
                         ' └ ✏️ Редактирование - изменяет текущее сообщение\n'
                         ' └ 🔔 Уведомление - показывает всплывающее сообщение\n'
                         ' └ 🔗 Ссылка - переход по внешней ссылке\n'
                         ' └ 🌐 WebApp - веб-апп\n\n'
                         '<b>Текущие кнопки:</b>\n' + buttons_text,  # Добавляем список кнопок в сообщение
                    reply_markup=kb,
                    parse_mode='HTML'  # Указываем режим HTML для форматирования
                )
            else:
                await call.message.edit_text(
                    text='<b> Управление кнопками:</b>\n'
                         ' └ Используйте кнопки ниже для настройки функциональности и внешнего вида\n\n'
                         '<b>⌨️ Типы кнопок:</b>\n'
                         ' └ 💬 Текст - отправляет новое сообщение\n'
                         ' └ ✏️ Редактирование - изменяет текущее сообщение\n'
                         ' └ 🔔 Уведомление - показывает всплывающее сообщение\n'
                         ' └ 🔗 Ссылка - переход по внешней ссылке\n'
                         ' └ 🌐 WebApp - веб-апп\n\n'
                         '<b>У бота нет кнопок.</b>',  # Сообщение, если у бота нет кнопок
                    reply_markup=kb,
                    parse_mode="HTML"
                )


@router.callback_query(F.data.startswith('edit_button|'))
async def edit_chosen_button(call: CallbackQuery, session: AsyncSession, user: User, state: FSMContext):
    button_index = int(call.data.split('|')[1])  # Получаем индекс кнопки

    data = await state.get_data()
    bot_id = data.get('bot_id')

    bot_query = await session.execute(select(Made_Bots).where(Made_Bots.id == bot_id))
    bot_made = bot_query.scalars().first()

    if not bot_made:
        return await call.answer("Бот не найден!", show_alert=True)

    buttons_data = json.loads(bot_made.buttons)

    if button_index >= len(buttons_data):
        return await call.answer("Кнопка не найдена!", show_alert=True)

    button = buttons_data[button_index]

    await state.update_data(editing_button_index=button_index, buttons_data=buttons_data)
    if button.get('type') == '💬' or '✏️' or '🔔':
        text = f"🔧 Редактирование кнопки:\n\n" \
               f"Тип кнопки: {button.get('type')}\n" \
               f"📝 Текст: {button.get('text', 'Не задан')}\n" \
               f"💬 Ответ: {button.get('answer', 'Не задан')}\n" \
               f"Выберите, что изменить:"

        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="✏ Изменить текст", callback_data="edit_text")],
            [InlineKeyboardButton(text="💬 Изменить ответ", callback_data="edit_answer")] if "answer" in button else [],
            [InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_edit")]
        ])
        await call.message.edit_text(text, reply_markup=keyboard)
    elif button.get('type') == '🔗':
        text = f"🔧 Редактирование кнопки:\n\n" \
               f"Тип кнопки: {button.get('type')}\n" \
               f"📝 Текст: {button.get('text', 'Не задан')}\n" \
               f"🔗 Ссылка: {button.get('url', 'Не задан')}\n" \
               f"Выберите, что изменить:"
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="✏ Изменить текст", callback_data="edit_text")],
            [InlineKeyboardButton(text="🔗 Изменить ссылку", callback_data="edit_url")] if "url" in button else [],
            [InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_edit")]
        ])
        await call.message.edit_text(text, reply_markup=keyboard)
    elif button.get('type') == '🌐':
        text = f"🔧 Редактирование кнопки:\n\n" \
               f"Тип кнопки: {button.get('type')}\n" \
               f"📝 Текст: {button.get('text', 'Не задан')}\n" \
               f"Выберите, что изменить:"
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="✏ Изменить текст", callback_data="edit_text")],
            [InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_edit")]
        ])
        await call.message.edit_text(text, reply_markup=keyboard)


@router.callback_query(F.data == 'edit_text')
async def edit_text(call: CallbackQuery, state: FSMContext):
    await call.message.edit_text(text='📝 Введите новый текст для кнопки (максимум 25 символов):',
                                 reply_markup=builder_keyboard.back_to_bot)
    await state.set_state(states.NewBotState.change_button_text)


@router.callback_query(F.data == 'edit_answer')
async def edit_answer(call: CallbackQuery, state: FSMContext):
    await call.message.edit_text(text='💬 Введите новый ответ для кнопки\n'
                                      '(Поддерживает HTML форматирование и фотографии):',
                                 reply_markup=builder_keyboard.back_to_bot)
    await state.set_state(states.NewBotState.change_button_answer)


@router.callback_query(F.data == 'edit_url')
async def edit_url(call: CallbackQuery, state: FSMContext):
    await call.message.edit_text(text='🔗 Введите новую ссылку для кнопки:',
                                 reply_markup=builder_keyboard.back_to_bot)
    await state.set_state(states.NewBotState.change_button_url)


@router.callback_query(F.data == 'cancel_edit')
async def cancel_edit(call: CallbackQuery, state: FSMContext, session: AsyncSession):
    if call.data == 'cancel_edit':
        bot_id = (await state.get_data()).get('bot_id')
        async with session:
            bot = await session.get(Made_Bots, bot_id)  # Получаем объект бота из базы данных
            kb = await builder_keyboard.get_manage_buttons_menu(bot)
            if bot and bot.buttons:  # Проверяем, есть ли у бота кнопки
                buttons_data = json.loads(bot.buttons)  # Загружаем JSON с данными о кнопках
                buttons_text = ""
                for i, button in enumerate(buttons_data):
                    if button['type'] == 'text':
                        buttons_text += f"{i + 1}. <code>{button['text']}</code>\n"  # Форматируем текст кнопки
                await call.message.edit_text(
                    text='<b> Управление кнопками:</b>\n'
                         ' └ Используйте кнопки ниже для настройки функциональности и внешнего вида\n\n'
                         '<b>⌨️ Типы кнопок:</b>\n'
                         ' └ 💬 Текст - отправляет новое сообщение\n'
                         ' └ ✏️ Редактирование - изменяет текущее сообщение\n'
                         ' └ 🔔 Уведомление - показывает всплывающее сообщение\n'
                         ' └ 🔗 Ссылка - переход по внешней ссылке\n'
                         ' └ 🌐 WebApp - веб-апп\n\n'
                         '<b>Текущие кнопки:</b>\n' + buttons_text,  # Добавляем список кнопок в сообщение
                    reply_markup=kb,
                    parse_mode='HTML'  # Указываем режим HTML для форматирования
                )
            else:
                await call.message.edit_text(
                    text='<b> Управление кнопками:</b>\n'
                         ' └ Используйте кнопки ниже для настройки функциональности и внешнего вида\n\n'
                         '<b>⌨️ Типы кнопок:</b>\n'
                         ' └ 💬 Текст - отправляет новое сообщение\n'
                         ' └ ✏️ Редактирование - изменяет текущее сообщение\n'
                         ' └ 🔔 Уведомление - показывает всплывающее сообщение\n'
                         ' └ 🔗 Ссылка - переход по внешней ссылке\n'
                         ' └ 🌐 WebApp - веб-апп\n\n'
                         '<b>У бота нет кнопок.</b>',  # Сообщение, если у бота нет кнопок
                    reply_markup=kb,
                    parse_mode="HTML"
                )


@router.message(states.NewBotState.change_button_text)
async def save_button_text(message, session: AsyncSession, state: FSMContext):
    data = await state.get_data()
    bot_id = data.get('bot_id')
    button_index = data.get('editing_button_index')
    buttons_data = data.get('buttons_data')

    buttons_data[button_index]['text'] = message.text[:25]

    bot_query = await session.execute(select(Made_Bots).where(Made_Bots.id == bot_id))
    bot_made = bot_query.scalars().first()
    bot_made.buttons = json.dumps(buttons_data)
    await session.commit()
    await crud.copy_bot_data(bot_made.bot_id, bot_made.id)
    await message.answer("✅ Текст кнопки обновлен!")
    await state.clear()


@router.message(states.NewBotState.change_button_answer)
async def save_button_answer(message, session: AsyncSession, state: FSMContext):
    data = await state.get_data()
    bot_id = data.get('bot_id')
    button_index = data.get('editing_button_index')
    buttons_data = data.get('buttons_data')
    text = message.caption if message.photo else message.text

    photo_path = None
    if message.photo:
        file_id = message.photo[-1].file_id
        file_info = await message.bot.get_file(file_id)
        file_ext = file_info.file_path.split('.')[-1]  # Получаем расширение файла
        unique_filename = f"{uuid.uuid4()}.{file_ext}"
        photo_path = os.path.join(PHOTO_DIR, unique_filename)

        await message.bot.download_file(file_info.file_path, photo_path)
    buttons_data[button_index]['answer'] = text
    buttons_data[button_index]['photo'] = photo_path
    bot_query = await session.execute(select(Made_Bots).where(Made_Bots.id == bot_id))
    bot_made = bot_query.scalars().first()
    bot_made.buttons = json.dumps(buttons_data)
    await session.commit()
    await crud.copy_bot_data(bot_made.bot_id, bot_made.id)
    await message.answer("✅ Ответ кнопки обновлен!")
    await state.clear()


@router.message(states.NewBotState.change_button_url)
async def save_button_url(message, session: AsyncSession, state: FSMContext):
    data = await state.get_data()
    bot_id = data.get('bot_id')
    button_index = data.get('editing_button_index')
    buttons_data = data.get('buttons_data')

    buttons_data[button_index]['url'] = message.text

    bot_query = await session.execute(select(Made_Bots).where(Made_Bots.id == bot_id))
    bot_made = bot_query.scalars().first()
    bot_made.buttons = json.dumps(buttons_data)
    await session.commit()
    await crud.copy_bot_data(bot_made.bot_id, bot_made.id)
    await message.answer("✅ Ссылка кнопки обновлена!")
    await state.clear()


@router.callback_query(F.data == 'add_button')
async def add_button(call: CallbackQuery, session: AsyncSession, user: User, state: FSMContext):
    bot_id = (await state.get_data()).get('bot_id')
    await state.update_data(bot_id=bot_id)
    await call.message.edit_text(text='🔘 Выберите тип новой кнопки:', reply_markup=builder_keyboard.create_button_type)


@router.callback_query(F.data.startswith('choose_button_type|'))
async def choose_button_type(call: CallbackQuery, session: AsyncSession, user: User, state: FSMContext):
    button_type = call.data.split('|')[1]
    await state.update_data(button_type=button_type)
    await call.message.edit_text(text='✏️ Введите текст для кнопки (максимум 25 символов):',
                                 reply_markup=builder_keyboard.back_to_bot)
    await state.set_state(states.NewBotState.button_text)


@router.message(StateFilter(states.NewBotState.button_text))
async def button_text(message: Message, session: AsyncSession, user: User, state: FSMContext):
    button_text = message.text
    await state.update_data(button_text=button_text)
    data = await state.get_data()
    bot_id = data.get('bot_id')
    button_type = data.get('button_type')
    if button_type == '0' or button_type == '1':
        await message.answer('📝 Введите ответный текст для кнопки:'
                             '<i>(Поддерживает HTML и {user} форматирование</i>'
                             'Вы также можете прикрепить фото', reply_markup=builder_keyboard.back_to_bot, parse_mode='HTML')
        await state.set_state(states.NewBotState.button_answer)
    elif button_type == '2':
        await message.answer('📝 Введите ответный текст для кнопки:'
                             '<i>(Поддерживает HTML и {user} форматирование</i>', reply_markup=builder_keyboard.back_to_bot, parse_mode='HTML')
        await state.set_state(states.NewBotState.button_answer)
    elif button_type == '3':
        await message.answer('🔗 Введите URL:', reply_markup=builder_keyboard.back_to_bot)
        await state.set_state(states.NewBotState.button_url)
    elif button_type == '4':
        type = '🌐'
        async with session:
            bot = await session.get(Made_Bots, bot_id)
            buttons = json.loads(bot.buttons) if bot.buttons else []
            new_button = {
                'type': type,
                'text': button_text,
            }
            buttons.append(new_button)
            bot.buttons = json.dumps(buttons)
            await session.commit()
            await crud.copy_bot_data(bot.bot_id, bot.id)
            await message.answer('✅ Кнопка добавлена!', reply_markup=main_keyboard.main_menu)
            await state.clear()


@router.message(StateFilter(states.NewBotState.button_answer))
async def button_answer(message: Message, session: AsyncSession, user: User, state: FSMContext):
    type = None
    button_answer = message.caption if message.photo else message.text
    photo_path = None
    if message.photo:
        file_id = message.photo[-1].file_id
        file_info = await message.bot.get_file(file_id)
        file_ext = file_info.file_path.split('.')[-1]  # Получаем расширение файла
        unique_filename = f"{uuid.uuid4()}.{file_ext}"
        photo_path = os.path.join(PHOTO_DIR, unique_filename)

        await message.bot.download_file(file_info.file_path, photo_path)
    await state.update_data(button_answer=button_answer)
    data = await state.get_data()
    bot_id = data.get('bot_id')
    button_type = data.get('button_type')
    if button_type == '0':
        type = '💬'
    elif button_type == '1':
        type = '✏️'
    elif button_type == '2':
        type = '🔔'
    button_text = data.get('button_text')
    button_answer = data.get('button_answer')
    async with session:
        bot = await session.get(Made_Bots, bot_id)
        buttons = json.loads(bot.buttons) if bot.buttons else []
        new_button = {
            'type': type,
            'text': button_text,
            'answer': button_answer,
            'photo': photo_path
        }
        buttons.append(new_button)
        bot.buttons = json.dumps(buttons)
        await session.commit()
        await crud.copy_bot_data(bot.bot_id, bot.id)
        await message.answer('✅ Кнопка добавлена!', reply_markup=main_keyboard.main_menu)
        await state.clear()


@router.message(StateFilter(states.NewBotState.button_url))
async def button_url(message: Message, session: AsyncSession, user: User, state: FSMContext):
    type = '🔗'
    button_url = message.text
    await state.update_data(button_url=button_url)
    data = await state.get_data()
    bot_id = data.get('bot_id')
    button_type = data.get('button_type')
    if button_type == '3':
        type = '🔗'
    button_text = data.get('button_text')
    button_url = data.get('button_url')
    async with session:
        bot = await session.get(Made_Bots, bot_id)
        buttons = json.loads(bot.buttons) if bot.buttons else []
        new_button = {
            'type': type,
            'text': button_text,
            'url': button_url
        }
        buttons.append(new_button)
        bot.buttons = json.dumps(buttons)
        await session.commit()
        await crud.copy_bot_data(bot.bot_id, bot.id)
        await message.answer('✅ Кнопка добавлена!', reply_markup=main_keyboard.main_menu)
        await state.clear()


@router.callback_query(F.data == 'delete_all')
async def delete_all_buttons(call: CallbackQuery, session: AsyncSession, user: User, state: FSMContext):
    bot_id = (await state.get_data()).get('bot_id')
    await state.update_data(bot_id=bot_id)
    async with session:
        bot = await session.get(Made_Bots, bot_id)
        bot.buttons = None
        await session.commit()
        await crud.copy_bot_data(bot.bot_id, bot.id)
        await call.message.edit_text('✅ Все кнопки удалены!', reply_markup=main_keyboard.main_menu)
        await state.clear()


@router.callback_query(F.data == 'referral_program_bot')
async def referral_program_bot(call: CallbackQuery, session: AsyncSession, user: User, state: FSMContext):
    bot_id = (await state.get_data()).get('bot_id')
    async with session:
        bot_query = await session.execute(select(Made_Bots).where(Made_Bots.id == bot_id))
        bot_made = bot_query.scalars().first()
        if bot_made.is_referal:
            status = '✅ Включена'
        else:
            status = '❌ Выключена'
        kb = await builder_keyboard.get_referal_settings_kb(bot_made)
    await call.message.edit_text(text='👥 Настройки реферальной программы\n'
                                      ' └ Настройка сообщения и состояния, которое придет пользователю, когда новый пользователь перейдет по его реферальной ссылке\n\n'
                                      '⚙️\n'
                                      f' └ Статус: {status}',
                                 reply_markup=kb)


@router.callback_query(F.data.startswith('switch_referal|'))
async def switch_referal(call: CallbackQuery, session: AsyncSession, user: User, state: FSMContext):
    bot_id = (await state.get_data()).get('bot_id')
    await state.update_data(bot_id=bot_id)
    callback = call.data.split('|')[1]
    async with session:
        bot_query = await session.execute(select(Made_Bots).where(Made_Bots.id == bot_id))
        bot_made = bot_query.scalars().first()
        if callback == 'on':
            bot_made.is_referal = True
            await session.commit()
            await call.message.edit_text('✅ Реферальная программа включена!', reply_markup=main_keyboard.main_menu)
        elif callback == 'off':
            bot_made.is_referal = False
            await session.commit()
            await call.message.edit_text('❌ Реферальная программа выключена!', reply_markup=main_keyboard.main_menu)
        await crud.copy_bot_data(bot_made.bot_id, bot_made.id)
        await state.clear()


@router.callback_query(F.data.startswith('bot_run_mailing|'))
async def bot_start_mailin(call: CallbackQuery, session: AsyncSession, state: FSMContext):
    bot_id = call.data.split('|')[1]
    await state.update_data(bot_id=bot_id)
    await call.message.answer(text='📨 Отправьте сообщение для рассылки. Это может быть текст, фото, видео или GIF.'
                                   '<i>(Поддерживается HTML-форматирование)</i>\n\n'
                                   '🔄 Базовые переменные:\n\n'
                                   '👤 Информация о пользователе: \n'
                                   ' └ {first_name} - имя\n'
                                   ' └ {last_name} - фамилия  \n'
                                   ' └ {username} - юзернейм без @\n'
                                   ' └ {@username} - юзернейм с @\n'
                                   ' └ {telegram_id} - ID пользователя\n\n'
                                   '🎲 Дополнительные функции:\n'
                                   ' └ {random(x,y)} - случайное число от x до y\n'
                                   ' └ {1: выражение} - сохранить результат в переменную 1\n'
                                   ' └ {2: ^1 * 2} - использовать значение переменной 1\n\n'
                                   '📋 Пример использования:\n'
                                   "<code>You won {1: random(5,10)} TON (${2: ^1 * ton})! If price doubles tomorrow, you'll have ${3: ^2 * 2}! Want to try your luck again? You have {4: random(1,3)} attempts left. -> You won 8 TON ($46.04)! If price doubles tomorrow, you'll have $92.08! Want to try your luck again? You have 2 attempts left.</code>"
                                   "\n\n<i>*Пустые поля заменяются на пустую строку</i>", parse_mode='HTML')
    await state.set_state(states.BotMailing.mailing_text)


@router.message(StateFilter(states.BotMailing.mailing_text))
async def mailing_set_text(message: Message, state: FSMContext, session: AsyncSession):
    mailing_text = message.text
    await state.update_data(mailing_text=mailing_text)
    await message.answer(text='🔘 Контент для рассылки добавлен.'
                              'Отправьте кнопки для рассылки в формате [текст + URL] или [текст + <code>webapp</code>].'
                              'Или нажмите кнопку, чтобы пропустить этот шаг.\n'
                              '<i>P.S. Webapp автоматически заменится на вебапп с выбранным доменом</i>',
                         parse_mode='HTML', reply_markup=builder_keyboard.mailing_skip_buttons)
    await state.set_state(states.BotMailing.mailing_buttons)


@router.message(StateFilter(states.BotMailing.mailing_buttons))
async def mailing_set_buttons(message: Message, state: FSMContext, session: AsyncSession):
    mailing_buttons = message.text
    await state.update_data(mailing_buttons=mailing_buttons)
    data = await state.get_data()
    bot_id = data.get('bot_id')
    mailing_text = data.get('mailing_text')

    async with session:
        bot = await session.get(Made_Bots, bot_id)

        if bot:  # Check if bot exists
            mailing = Mailing(  # Create a new Mailing object
                mailing_text=mailing_text,
                mailing_buttons=mailing_buttons,
                bot_id=bot.id  # Associate with the Made_Bots object
            )

            session.add(mailing)  # Add the new Mailing object to the session
            await session.commit()
            await message.answer('✅ Рассылка добавлена! Подтвердите запуск:',
                                 reply_markup=builder_keyboard.mailing_confirm_launch)


@router.callback_query(F.data == 'mailing_skip_buttons')
async def mailing_skip_buttons(call: CallbackQuery, state: FSMContext, session: AsyncSession):
    if call.data == 'mailing_skip_buttons':
        data = await state.get_data()
        bot_id = data.get('bot_id')
        mailing_text = data.get('mailing_text')

        async with session:
            bot = await session.get(Made_Bots, bot_id)

            if bot:  # Check if bot exists
                mailing = Mailing(  # Create a new Mailing object
                    mailing_text=mailing_text,
                    mailing_buttons=None,
                    made_bots=bot  # Associate with the Made_Bots object
                )

                session.add(mailing)  # Add the new Mailing object to the session
                await session.commit()
                await call.message.answer('✅ Рассылка добавлена! Вы хотите запустить рассылку?',
                                          reply_markup=builder_keyboard.mailing_confirm_launch)
            else:
                await call.message.answer("Бот не найден!")  # Handle the case where the bot doesn't exis


@router.callback_query(F.data == 'mailing_confirm_launch' or 'mailing_confirm_cancel')
async def mailing_confirm_launch(call: CallbackQuery, state: FSMContext, session: AsyncSession):
    if call.data == 'mailing_confirm_launch':
        data = await state.get_data()
        bot_id = data.get('bot_id')
        bot_made = await session.get(Made_Bots, bot_id)
        mailing_text = data.get('mailing_text')
        mailing_buttons = data.get('mailing_buttons')
        mailing_interval = None
        is_mailing = True
        async with session:
            mailing = Mailing(mailing_text=mailing_text, mailing_buttons=mailing_buttons, made_bots=bot_made,
                              interval=mailing_interval, is_mailing=is_mailing)
            session.add(mailing)
            await session.commit()
            await session.refresh(mailing)
            bot_made = await session.get(Made_Bots, bot_id)
            if bot_made:
                if not bot_made.is_working:
                    await call.message.edit_text('❌ Бот не запущен! Запускаю рассылку')
                    await control_made_bot.send_mailing_to_other_bots(bot_made, mailing, session)
                    # await send_mailing_info(bot_made.bot_id, bot_made.bot_id, mailing_text, mailing_buttons, mailing_interval)
                    await call.message.answer('✅ Рассылка запущена!', reply_markup=main_keyboard.main_menu)
                    await state.clear()
                else:
                    await call.message.edit_text('✅ Бот запущен! Запускаю бота для рассылки')
                    await bot_start(bot_made)
                    await session.commit()
                    await asyncio.sleep(2)  # Wait for 5 seconds
                    await control_made_bot.send_mailing_to_other_bots(bot_made, mailing, session)
                    await call.message.answer('✅ Рассылка запущена!', reply_markup=main_keyboard.main_menu)
                    await state.clear()
            else:
                await call.message.answer("Бот не найден!")  # Handle the case where the bot doesn't exis
    elif call.data == 'mailing_confirm_cancel':
        await call.message.answer('❌ Рассылка не запущена!')
        await state.clear()


@router.callback_query(F.data.startswith('bot_start_stop|'))
async def bot_start_stop(call: CallbackQuery, session: AsyncSession, user: User, bot: Bot, state: FSMContext):
    bot_id = call.data.split('|')[1]
    await state.update_data(bot_id=bot_id)
    async with session:
        bot_query = await session.execute(select(Made_Bots).where(Made_Bots.id == bot_id))
        bot_made = bot_query.scalars().first()
        if bot_made.is_working and bot_made.process is not None:
            try:
                async with session:
                    await stop_bot(bot_made)
                    await session.commit()
                    await load_bot_page(session, bot_id, bot, user)
                    await call.message.answer('⏹️ Бот остановлен!')
            except Exception as e:  # Handle if process is already gone
                async with session:
                    bot_made = await session.get(Made_Bots, bot_id)  # Обновляем объект из БД
                    bot_made.is_working = False
                    bot_made.process = None
                    await session.commit()
                    await load_bot_page(session, bot_id, bot, user)
                await call.message.answer(f'Ошибка остановки бота: {e}! Бот был не запущен')
        else:
            await bot_start(bot_made)
            await session.commit()
            async with session:
                new_bot_query = await session.execute(select(Made_Bots).where(Made_Bots.id == bot_id))
                new_bot = new_bot_query.scalars().first()
                keyboard = await builder_keyboard.get_bot_settings_kb(new_bot)
                # domain_query = await session.execute(select(Domains).where(Domains.id == new_bot.domain_id))
                # domain = domain_query.scalars().first()
                buttons_text = ""
                if new_bot.buttons:
                    try:
                        buttons_data = json.loads(new_bot.buttons)
                        for i, button in enumerate(buttons_data):
                            buttons_text += f"{button.get('text', 'Кнопка')} ({button.get('type', 'text')})\n"
                    except json.JSONDecodeError:
                        buttons_text = "Ошибка: Некорректный формат кнопок"
                else:
                    buttons_text = "Кнопок нет"

                # Форматирование стартового текста
                start_text = new_bot.start_message or "Стартовый текст не установлен"

                text = (f'⚙️ Настройки бота: {new_bot.bot_id}\n\n'
                        f'<b>🤖 Юзернейм:</b> @{new_bot.bot_name}\n'
                        f'<b>🌐 Домен:</b> {new_bot.web_app_link}\n'
                        f'<b>💬 Текст кнопки WebApp:</b> {new_bot.web_app_button}\n\n'
                        f'<b>🖥 Кнопки:</b> <pre>{buttons_text}</pre>\n\n'
                        f'<b>📝Стартовый текст:</b> <pre>{start_text}</pre>\n'
                        f'После изменения настроек, нажимайте обновить!')

                await call.message.edit_text(text, parse_mode="HTML", reply_markup=keyboard)
            await call.message.answer('🚀 Бот запущен!')
        await state.clear()


@router.callback_query(F.data.startswith('bot_delete|'))
async def bot_delete(call: CallbackQuery, session: AsyncSession, user: User, state: FSMContext):
    bot_id = call.data.split('|')[1]
    await state.update_data(bot_id=bot_id)
    await call.message.answer(text='Вы уверены, что хотите удалить бота?',
                              reply_markup=builder_keyboard.delete_bot_choice)


@router.callback_query(F.data.startswith('delete_bot|'))
async def delete_bot(call: CallbackQuery, session: AsyncSession, user: User, state: FSMContext):
    choice = call.data.split('|')[1]
    bot_id = (await state.get_data()).get('bot_id')
    if choice == 'yes':
        async with session:
            bot_query = await session.execute(select(Made_Bots).where(Made_Bots.id == bot_id))
            bot_made = bot_query.scalars().first()
            await session.delete(bot_made)
            await session.commit()
            await call.message.edit_text('✅ Бот удален!')
            await state.clear()
    elif choice == 'no':
        async with session:
            new_bot_query = await session.execute(select(Made_Bots).where(Made_Bots.id == bot_id))
            new_bot = new_bot_query.scalars().first()
            keyboard = await builder_keyboard.get_bot_settings_kb(new_bot)
            # domain_query = await session.execute(select(Domains).where(Domains.id == new_bot.domain_id))
            # domain = domain_query.scalars().first()
            buttons_text = ""
            if new_bot.buttons:
                try:
                    buttons_data = json.loads(new_bot.buttons)
                    for i, button in enumerate(buttons_data):
                        buttons_text += f"{button.get('text', 'Кнопка')} ({button.get('type', 'text')})\n"
                except json.JSONDecodeError:
                    buttons_text = "Ошибка: Некорректный формат кнопок"
            else:
                buttons_text = "Кнопок нет"

            # Форматирование стартового текста
            start_text = new_bot.start_message or "Стартовый текст не установлен"

            text = (f'⚙️ Настройки бота: {new_bot.bot_id}\n\n'
                    f'<b>🤖 Юзернейм:</b> @{new_bot.bot_name}\n'
                    f'<b>🌐 Домен:</b> {new_bot.web_app_link}\n'
                    f'<b>💬 Текст кнопки WebApp:</b> {new_bot.web_app_button}\n\n'
                    f'<b>🖥 Кнопки:</b> <pre>{buttons_text}</pre>\n\n'
                    f'<b>📝Стартовый текст:</b> <pre>{start_text}</pre>\n'
                    f'После изменения настроек, нажимайте обновить!')

            await call.message.edit_text(text, parse_mode="HTML", reply_markup=keyboard)


async def update_bot_menu(bot: Bot, add_webapp: bool):
    """
    Обновляет меню бота: добавляет или удаляет кнопку WebApp.

    :param bot: объект бота
    :param add_webapp: если True — добавляет WebApp, иначе убирает
    """
    commands = []

    if add_webapp:
        commands.append(
            BotCommand(command="webapp", description="Открыть WebApp")
        )

    await bot.set_my_commands(commands, scope=BotCommandScopeDefault())


@router.callback_query(F.data.startswith('bot_web_app_position|'))
async def bot_web_app_position(call: CallbackQuery, session: AsyncSession, user: User, state: FSMContext, bot: Bot):
    bot_id = call.data.split('|')[1]
    await state.update_data(bot_id=bot_id)
    async with session:
        bot_query = await session.execute(select(Made_Bots).where(Made_Bots.id == bot_id))
        bot_made = bot_query.scalars().first()
        if bot_made.web_app_position:
            bot_made.web_app_position = False
            await session.commit()
            if bot_made.is_working and bot_made.process is not None:
                await crud.copy_bot_data(bot_made.bot_id, bot_made.id)
                await control_made_bot.switch_off_webapp(bot_made.bot_id, bot_made.web_app_button,
                                                         bot_made.web_app_link,
                                                         call.from_user.id, session)
                await load_bot_page(session, bot_id, bot, user)
            else:
                await bot_start(bot_made)
                await session.commit()
                await asyncio.sleep(3)
                await crud.copy_bot_data(bot_made.bot_id, bot_made.id)
                await control_made_bot.switch_off_webapp(bot_made.bot_id, bot_made.web_app_button,
                                                         bot_made.web_app_link,
                                                         call.from_user.id, session)
                await load_bot_page(session, bot_id, bot, user)
                await stop_bot(bot_made)
                await session.commit()
            await call.message.answer('❌ WebApp в углу выключен!', reply_markup=main_keyboard.main_menu)
        else:
            bot_made.web_app_position = True
            await session.commit()
            if bot_made.is_working and bot_made.process is not None:
                await crud.copy_bot_data(bot_made.bot_id, bot_made.id)
                await control_made_bot.switch_on_webapp(bot_made.bot_id, bot_made.web_app_button,
                                                        bot_made.web_app_link,
                                                        call.from_user.id, session)
                await load_bot_page(session, bot_id, bot, user)
            else:
                await bot_start(bot_made)
                await session.commit()
                await asyncio.sleep(3)
                await crud.copy_bot_data(bot_made.bot_id, bot_made.id)
                await control_made_bot.switch_on_webapp(bot_made.bot_id, bot_made.web_app_button,
                                                        bot_made.web_app_link,
                                                        call.from_user.id, session)
                await load_bot_page(session, bot_id, bot, user)
                await stop_bot(bot_made)
                await session.commit()
            await call.message.answer('✅ WebApp в углу включен!', reply_markup=main_keyboard.main_menu)
        await state.clear()


@router.callback_query(F.data.startswith('bot_web_app_text|'))
async def bot_web_app_text(call: CallbackQuery, session: AsyncSession, user: User, state: FSMContext):
    bot_id = call.data.split('|')[1]
    await state.update_data(bot_id=bot_id)
    kb = await builder_keyboard.get_back_to_bot_settings(bot_id)
    await call.message.answer('📝 Введите текст для кнопки WebApp (до 25 символов):',
                              reply_markup=kb)
    await state.set_state(states.NewBotState.web_app_text)


@router.message(StateFilter(states.NewBotState.web_app_text))
async def web_app_text(message: Message, session: AsyncSession, user: User, state: FSMContext):
    web_app_text = message.text
    await state.update_data(web_app_text=web_app_text)
    data = await state.get_data()
    bot_id = data.get('bot_id')
    await message.answer('Меняю текст кнопки WebApp', reply_markup=main_keyboard.main_menu)
    async with session:
        bot_query = await session.execute(select(Made_Bots).where(Made_Bots.id == bot_id))
        bot_made = bot_query.scalars().first()
        bot_made.web_app_button = web_app_text
        await session.commit()
        await session.refresh(bot_made)  # Перезагружаем объект из БД
        print(f"Updated web_app_button: {bot_made.web_app_button}")
        if bot_made.is_working and bot_made.process is not None:
            await crud.copy_bot_data(bot_made.bot_id, bot_made.id)
            await control_made_bot.switch_on_webapp(bot_made.bot_id, bot_made.web_app_button, bot_made.web_app_link,
                                                    message.from_user.id, session)
            await message.answer('✅ Текст для кнопки WebApp изменен!', reply_markup=main_keyboard.main_menu)
            await state.clear()
        else:
            await crud.copy_bot_data(bot_made.bot_id, bot_made.id)
            await bot_start(bot_made)
            await session.commit()
            await asyncio.sleep(3)
            await control_made_bot.switch_on_webapp(bot_made.bot_id, bot_made.web_app_button, bot_made.web_app_link,
                                                    message.from_user.id, session)
            await stop_bot(bot_made)
            await session.commit()
            await message.answer('✅ Текст для кнопки WebApp изменен!', reply_markup=main_keyboard.main_menu)
            await state.clear()


@router.callback_query(F.data.startswith('bot_change_domain|'))
async def bot_change_domain(call: CallbackQuery, session: AsyncSession, user: User, state: FSMContext):
    bot_id = call.data.split('|')[1]
    await state.update_data(bot_id=bot_id)
    await call.message.edit_text('📝 Введите новую ссылку для WebApp')
    await state.set_state(states.NewBotState.change_web_app_link)


@router.message(StateFilter(states.NewBotState.change_web_app_link))
async def change_web_app_link(message: Message, session: AsyncSession, user: User, state: FSMContext):
    web_app_link = message.text
    await state.update_data(web_app_link=web_app_link)
    data = await state.get_data()
    bot_id = data.get('bot_id')
    async with session:
        bot_query = await session.execute(select(Made_Bots).where(Made_Bots.id == bot_id))
        bot_made = bot_query.scalars().first()
        bot_made.web_app_link = web_app_link
        await session.commit()
        await session.refresh(bot_made)  # Перезагружаем объект из БД
        print(f"Updated web_app_button: {bot_made.web_app_link}")
        if bot_made.is_working and bot_made.process is not None:
            await crud.copy_bot_data(bot_made.bot_id, bot_made.id)
            await control_made_bot.switch_on_webapp(bot_made.bot_id, bot_made.web_app_button, bot_made.web_app_link,
                                                    message.from_user.id, session)
            await message.answer('✅ Ссылка для WebApp изменена!', reply_markup=main_keyboard.main_menu)
            await crud.copy_bot_data(bot_made.bot_id, bot_made.id)
            await state.clear()
        else:
            await crud.copy_bot_data(bot_made.bot_id, bot_made.id)
            await bot_start(bot_made)
            await session.commit()
            await asyncio.sleep(3)
            await control_made_bot.switch_on_webapp(bot_made.bot_id, bot_made.web_app_button, bot_made.web_app_link,
                                                    message.from_user.id, session)
            await message.answer('✅ Ссылка для WebApp изменена!', reply_markup=main_keyboard.main_menu)
            await crud.copy_bot_data(bot_made.bot_id, bot_made.id)
            await stop_bot(bot_made)
            await session.commit()
            await state.clear()


@router.callback_query(F.data == 'back_to_bot_menu')
async def back_to_bot_menu(call: CallbackQuery, session: AsyncSession, user: User, state: FSMContext):
    data = await state.get_data()
    bot_id = data.get('bot_id')
    async with session:
        new_bot_query = await session.execute(select(Made_Bots).where(Made_Bots.id == bot_id))
        new_bot = new_bot_query.scalars().first()
        keyboard = await builder_keyboard.get_bot_settings_kb(new_bot)
        # domain_query = await session.execute(select(Domains).where(Domains.id == new_bot.domain_id))
        # domain = domain_query.scalars().first()
        buttons_text = ""
        if new_bot.buttons:
            try:
                buttons_data = json.loads(new_bot.buttons)
                for i, button in enumerate(buttons_data):
                    buttons_text += f"{button.get('text', 'Кнопка')} ({button.get('type', 'text')})\n"
            except json.JSONDecodeError:
                buttons_text = "Ошибка: Некорректный формат кнопок"
        else:
            buttons_text = "Кнопок нет"

        # Форматирование стартового текста
        start_text = new_bot.start_message or "Стартовый текст не установлен"

        text = (f'⚙️ Настройки бота: {new_bot.bot_id}\n\n'
                f'<b>🤖 Юзернейм:</b> @{new_bot.bot_name}\n'
                f'<b>🌐 Домен:</b> {new_bot.web_app_link}\n'
                f'<b>💬 Текст кнопки WebApp:</b> {new_bot.web_app_button}\n\n'
                f'<b>🖥 Кнопки:</b> <pre>{buttons_text}</pre>\n\n'
                f'<b>📝Стартовый текст:</b> <pre>{start_text}</pre>\n'
                f'После изменения настроек, нажимайте обновить!')

        await call.message.edit_text(text, parse_mode="HTML", reply_markup=keyboard)


@router.callback_query(F.data.startswith('bot_update|'))
async def bot_update(call: CallbackQuery, session: AsyncSession, user: User, state: FSMContext):
    bot_id = call.data.split('|')[1]
    await state.update_data(bot_id=bot_id)

    async with session:
        bot_query = await session.execute(select(Made_Bots).where(Made_Bots.id == bot_id))
        bot_made = bot_query.scalars().first()
        await crud.copy_bot_data(bot_made.bot_id, bot_made.id)

        await call.message.answer('Обновлено!')


@router.callback_query(F.data.startswith('bot_statistics|'))
async def bot_statistics(call: CallbackQuery, session: AsyncSession, user: User, state: FSMContext):
    bot_id = call.data.split('|')[1]
    await state.update_data(bot_id=bot_id)

    async with session:
        bot_query = await session.execute(select(Made_Bots).where(Made_Bots.id == bot_id))
        bot_made = bot_query.scalars().first()

        if not bot_made:
            await call.message.edit_text("Бот не найден.")
            return

        stats = await crud.get_user_statistics(bot_made.bot_name, bot_id)

        if stats:
            message = (
                "<b>📊 Статистика пользователей:</b>\n"
                f"└ 👥 Всего: <code>{stats.get('total', 0)}</code>\n"
                f"└ 📅 Месяц: <code>{stats.get('month', 0)}</code>\n"
                f"└ 📆 Неделя: <code>{stats.get('week', 0)}</code>\n"
                f"└ 🗓 День: <code>{stats.get('day', 0)}</code>\n"
                f"└ 🕐 Час: <code>{stats.get('hour', 0)}</code>\n"
                f"└ ⏱️ 15 мин: <code>{stats.get('fifteen_min', 0)}</code>"
            )
        else:
            message = (
                "<b>📊 Статистика пользователей:</b>\n"
                "└ 👥 Всего: <code>0</code>\n"
                "└ 📅 Месяц: <code>0</code>\n"
                "└ 📆 Неделя: <code>0</code>\n"
                "└ 🗓 День: <code>0</code>n"
                "└ 🕐 Час: <code>0</code>\n"
                "└ ⏱️ 15 мин: <code>0</code>"
            )
        kb = await builder_keyboard.get_back_to_bot_settings(bot_id)
        await call.message.edit_text(message, parse_mode="HTML", reply_markup=kb)
        await state.clear()


@router.callback_query(F.data.startswith('back_to_bot_settings|'))
async def back_to_bot_settings(call: CallbackQuery, session: AsyncSession, user: User, state: FSMContext):
    bot_id = call.data.split('|')[1]
    async with session:
        new_bot_query = await session.execute(select(Made_Bots).where(Made_Bots.id == bot_id))
        new_bot = new_bot_query.scalars().first()
        keyboard = await builder_keyboard.get_bot_settings_kb(new_bot)
        # domain_query = await session.execute(select(Domains).where(Domains.id == new_bot.domain_id))
        # domain = domain_query.scalars().first()
        buttons_text = ""
        if new_bot.buttons:
            try:
                buttons_data = json.loads(new_bot.buttons)
                for i, button in enumerate(buttons_data):
                    buttons_text += f"{button.get('text', 'Кнопка')} ({button.get('type', 'text')})\n"
            except json.JSONDecodeError:
                buttons_text = "Ошибка: Некорректный формат кнопок"
        else:
            buttons_text = "Кнопок нет"

        # Форматирование стартового текста
        start_text = new_bot.start_message or "Стартовый текст не установлен"

        text = (f'⚙️ Настройки бота: {new_bot.bot_id}\n\n'
                f'<b>🤖 Юзернейм:</b> @{new_bot.bot_name}\n'
                f'<b>🌐 Домен:</b> {new_bot.web_app_link}\n'
                f'<b>💬 Текст кнопки WebApp:</b> {new_bot.web_app_button}\n\n'
                f'<b>🖥 Кнопки:</b> <pre>{buttons_text}</pre>\n\n'
                f'<b>📝Стартовый текст:</b> <pre>{start_text}</pre>\n'
                f'После изменения настроек, нажимайте обновить!')

        await call.message.edit_text(text, parse_mode="HTML", reply_markup=keyboard)


@router.callback_query(F.data.startswith('bot_export_db|'))
async def bot_export_db(call: CallbackQuery, session: AsyncSession, user: User, state: FSMContext):
    bot_id = call.data.split('|')[1]
    await state.update_data(bot_id=bot_id)

    async with session:
        bot_query = await session.execute(select(Made_Bots).where(Made_Bots.id == bot_id))
        bot_made = bot_query.scalars().first()

        if not bot_made:
            await call.message.edit_text("Бот не найден.")
            return

        bot_name = bot_made.bot_name
        db_path = f"bot_database_{bot_name}.db"

        try:
            db_file = FSInputFile(db_path)  # Подготавливаем файл для отправки
            await call.message.answer_document(db_file, caption=f"📂 База данных {bot_name}")
        except Exception as e:
            await call.message.edit_text(f"Ошибка при отправке базы данных: {e}")

    await state.clear()


@router.callback_query(F.data.startswith('bot_change_name|'))
async def bot_change_name_callback(call: CallbackQuery, state: FSMContext):
    bot_id = call.data.split('|')[1]
    await state.update_data(bot_id=bot_id)

    await call.message.edit_text("✏️ Введите новое имя для бота:")
    await state.set_state(states.NewBotState.new_bot_name)


@router.message(states.NewBotState.new_bot_name)
async def bot_change_name_message(message: Message, session: AsyncSession, state: FSMContext, bot: Bot, user: User):
    data = await state.get_data()
    bot_id = data.get("bot_id")
    new_name = message.text.strip()

    async with session.begin():
        bot_query = await session.execute(select(Made_Bots).where(Made_Bots.id == bot_id))
        bot_made = bot_query.scalars().first()

        if not bot_made:
            await message.answer("⚠️ Бот не найден.")
            await state.clear()
            return

        bot_made.bot_name = new_name
        await session.commit()

    await message.answer(f"✅ Имя бота изменено на <b>{new_name}</b>", parse_mode="HTML")
    await crud.copy_bot_data(bot_made.bot_id, bot_made.id)
    await load_bot_page(session, bot_id, bot, user)
    await state.clear()


@router.callback_query(F.data.startswith('bot_transfer_settings|'))
async def choose_source_bot(call: CallbackQuery, session: AsyncSession, user: User, state: FSMContext):
    bot_id = call.data.split('|')[1]
    await state.update_data(bot_id=bot_id)
    async with session:
        bots_query = await session.execute(
            select(Made_Bots).where(Made_Bots.user_tg_id == user.tg_id, Made_Bots.id != bot_id)
        )
        bots = bots_query.scalars().all()

    if not bots:
        await call.answer("У вас нет других ботов для переноса!", show_alert=True)
        return

    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=bot.bot_name, callback_data=f"confirm_transfer|{bot_id}|{bot.id}")]
            for bot in bots
        ]
    )

    await call.message.edit_text("Выберите бота, в которого перенести данные:", reply_markup=keyboard)


@router.callback_query(F.data.startswith('confirm_transfer|'))
async def transfer_data(call: CallbackQuery, session: AsyncSession, bot: Bot, user: User):
    """Перенос данных из одного бота в другой"""
    _, source_bot_id, target_bot_id = call.data.split('|')

    async with session:
        source_bot = await session.get(Made_Bots, source_bot_id)
        target_bot = await session.get(Made_Bots, target_bot_id)
        if not source_bot or not target_bot:
            await call.answer("Ошибка! Бот не найден.", show_alert=True)
            return

        # Копирование данных
        target_bot.start_message = source_bot.start_message
        target_bot.buttons = source_bot.buttons
        target_bot.web_app_button = source_bot.web_app_button
        target_bot.web_app_position = source_bot.web_app_position
        target_bot.process = source_bot.process
        target_bot.web_app_link = source_bot.web_app_link
        target_bot.web_app_html = source_bot.web_app_html
        target_bot.is_referal = source_bot.is_referal

        # Перенос рассылок
        mailings_query = await session.execute(select(Mailing).where(Mailing.bot_id == source_bot_id))
        mailings = mailings_query.scalars().all()

        for mailing in mailings:
            new_mailing = Mailing(
                name=mailing.name,
                mailing_text=mailing.mailing_text,
                mailing_buttons=mailing.mailing_buttons,
                interval=mailing.interval,
                bot_id=target_bot.id
            )
            session.add(new_mailing)

        await session.commit()

    await call.message.edit_text("✅ Данные успешно перенесены!")
    await load_bot_page(session, source_bot_id, bot, user)


class MailingTypeCallback(CallbackData, prefix="mailing"):
    type: str
    bot_id: str
    template_id: Optional[int] = None


def get_mailing_keyboard(current_type: str, bot_id: str, templates: list):
    builder = InlineKeyboardBuilder()

    if templates:  # Добавляем кнопки только если есть шаблоны
        for template in templates:
            if template.name:
                builder.button(
                    text=template.name,
                    callback_data=MailingTypeCallback(type="mailing", bot_id=bot_id, template_id=template.id).pack()
                )

    builder.button(text="➕ Создать новый шаблон", callback_data=f"create_mailing|{bot_id}")

    if current_type == "one_time":
        builder.button(
            text="🔄 Шаблоны интервальной рассылки",
            callback_data=MailingTypeCallback(type="interval", bot_id=bot_id).pack()
        )
    else:
        builder.button(
            text="🔄 Шаблоны разовой рассылки",
            callback_data=MailingTypeCallback(type="one_time", bot_id=bot_id).pack()
        )

    builder.button(text="🔙 Назад", callback_data=f"back_to_bot_settings|{bot_id}")
    builder.adjust(1)
    return builder.as_markup()


async def get_mailing_templates_text(session: AsyncSession, bot_id: str, mailing_type: str):
    """Получает текст для сообщения о шаблонах рассылки."""

    if mailing_type == "one_time":
        mailing_type_text = "разовой"
        templates_query = await session.execute(
            select(Mailing).where(and_(Mailing.bot_id == bot_id, Mailing.interval.is_(None)))
        )
    elif mailing_type == "interval":
        mailing_type_text = "интервальной"
        templates_query = await session.execute(
            select(Mailing).where(and_(Mailing.bot_id == bot_id, Mailing.interval.is_not(None)))
        )
    else:
        return "Некорректный тип рассылки"

    templates = templates_query.scalars().all()
    templates_count = len(templates)
    total_templates = 8  # Максимальное количество шаблонов

    return f" Шаблоны {mailing_type_text} рассылки\n" \
           f"Всего шаблонов: {templates_count}/{total_templates}\n\n" \
           f"Выберите шаблон для управления или создайте новый:"


@router.callback_query(F.data.startswith('bot_mailing_templates|'))
async def bot_mailing_templates(call: types.CallbackQuery, session: AsyncSession, user, state):
    bot_id = call.data.split('|')[1]
    await state.update_data(bot_id=bot_id)

    templates_one_time_query = await session.execute(
        select(Mailing).where(and_(Mailing.bot_id == bot_id, Mailing.interval.is_(None)))
    )
    templates_one_time = templates_one_time_query.scalars().all()

    text = await get_mailing_templates_text(session, bot_id, "one_time")
    await call.message.edit_text(text, reply_markup=get_mailing_keyboard("one_time", bot_id, templates_one_time))
    await call.answer()


@router.callback_query(MailingTypeCallback.filter(F.type == "one_time"))
async def show_one_time_mailing(callback: types.CallbackQuery, callback_data: MailingTypeCallback,
                                session: AsyncSession):
    templates_one_time_query = await session.execute(
        select(Mailing).where(and_(Mailing.bot_id == callback_data.bot_id, Mailing.interval.is_(None)))
    )
    templates_one_time = templates_one_time_query.scalars().all()

    text = await get_mailing_templates_text(session, callback_data.bot_id, "one_time")
    await callback.message.edit_text(text, reply_markup=get_mailing_keyboard("one_time", callback_data.bot_id,
                                                                             templates_one_time))
    await callback.answer()


@router.callback_query(MailingTypeCallback.filter(F.type == "interval"))
async def show_interval_mailing(callback: types.CallbackQuery, callback_data: MailingTypeCallback,
                                session: AsyncSession):
    templates_interval_query = await session.execute(
        select(Mailing).where(and_(Mailing.bot_id == callback_data.bot_id, Mailing.interval.is_not(None)))
    )
    templates_interval = templates_interval_query.scalars().all()

    text = await get_mailing_templates_text(session, callback_data.bot_id, "interval")
    await callback.message.edit_text(text, reply_markup=get_mailing_keyboard("interval", callback_data.bot_id,
                                                                             templates_interval))
    await callback.answer()


@router.callback_query(F.data.startswith('create_mailing|'))
async def create_mailing_template(call: types.CallbackQuery, state: FSMContext):
    bot_id = call.data.split('|')[1]
    await state.update_data(bot_id=bot_id)
    await call.message.answer(text='📝 Введите название шаблона (до 50 символов):\n\n'
                                   '<i>Название поможет вам легко находить нужный шаблон</i>', parse_mode='HTML')
    await state.set_state(states.BotMailing.new_mailing_name)


@router.message(StateFilter(states.BotMailing.new_mailing_name))
async def process_mailing_name(message: types.Message, state: FSMContext, session: AsyncSession):
    mailing_name = message.text
    await state.update_data(new_mailing_name=mailing_name)
    data = await state.get_data()
    bot_id = data.get("bot_id")
    async with session:
        query = await session.execute(select(Made_Bots).where(Made_Bots.id == bot_id))
        made_bot = query.scalars().first()
    kb = await builder_keyboard.get_bot_settings_kb(made_bot)
    await message.answer('📨 Отправьте сообщение для рассылки. Это может быть текст, фото, видео или GIF.'
                         '<i>(Поддерживается HTML-форматирование)</i>\n\n'
                         '🔄 Базовые переменные:\n\n'
                         '👤 Информация о пользователе: \n'
                         ' └ {first_name} - имя\n'
                         ' └ {last_name} - фамилия  \n'
                         ' └ {username} - юзернейм без @\n'
                         ' └ {@username} - юзернейм с @\n'
                         ' └ {telegram_id} - ID пользователя\n\n'
                         '🎲 Дополнительные функции:\n'
                         ' └ {random(x,y)} - случайное число от x до y\n'
                         ' └ {1: выражение} - сохранить результат в переменную 1\n'
                         ' └ {2: ^1 * 2} - использовать значение переменной 1\n\n'
                         '📋 Пример использования:\n'
                         "<code>You won {1: random(5,10)} TON (${2: ^1 * ton})! If price doubles tomorrow, you'll have ${3: ^2 * 2}! Want to try your luck again? You have {4: random(1,3)} attempts left. -> You won 8 TON ($46.04)! If price doubles tomorrow, you'll have $92.08! Want to try your luck again? You have 2 attempts left.</code>"
                         "\n\n<i>*Пустые поля заменяются на пустую строку</i>", parse_mode='HTML')
    await state.set_state(states.BotMailing.new_mailing_text)


@router.message(StateFilter(states.BotMailing.new_mailing_text))
async def process_mailing_text(message: types.Message, state: FSMContext):
    mailing_text = message.text
    await state.update_data(new_mailing_text=mailing_text)

    await message.answer('🔘 Контент для рассылки добавлен.'
                         'Отправьте кнопки для рассылки в формате [текст + URL] или [текст + <code>webapp</code>].'
                         'Или нажмите кнопку, чтобы пропустить этот шаг.\n'
                         '<i>P.S. Webapp автоматически заменится на вебапп с выбранным доменом</i>', parse_mode='HTML')
    await state.set_state(states.BotMailing.new_mailing_buttons)


@router.message(StateFilter(states.BotMailing.new_mailing_buttons))
async def process_mailing_buttons(message: types.Message, state: FSMContext):
    mailing_buttons = message.text
    await state.update_data(new_mailing_buttons=mailing_buttons)

    await message.answer('⏱️ Введите интервал рассылки в минутах (от 60 до 2880): если не нужен интервал, поставьте 0.')
    await state.set_state(states.BotMailing.new_mailing_interval)


@router.message(StateFilter(states.BotMailing.new_mailing_interval))
async def process_mailing_interval(message: types.Message, state: FSMContext, session: AsyncSession):
    try:
        interval = int(message.text)
        if interval == 0:
            interval = None
        elif interval < 60 or interval > 2880:
            await message.answer('❗ Интервал должен быть в пределах от 60 до 2880 минут.')
            return
    except ValueError:
        await message.answer('❗ Введите число для интервала.')
        return

    await state.update_data(new_mailing_interval=interval)

    # Здесь сохраняем рассылку в базу данных
    user_data = await state.get_data()
    mailing_name = user_data.get('new_mailing_name')
    mailing_text = user_data.get('new_mailing_text')
    mailing_buttons = user_data.get('new_mailing_buttons')
    mailing_interval = user_data.get('new_mailing_interval')
    bot_id = user_data.get('bot_id')

    async with session:
        # Сохраняем данные в модель Mailing (предполагается, что модель уже существует)
        new_mailing = Mailing(name=mailing_name, mailing_text=mailing_text, mailing_buttons=mailing_buttons,
                              interval=mailing_interval,
                              bot_id=bot_id)
        session.add(new_mailing)
        await session.commit()  # или асинхронный commit с использованием async SQLAlchemy

        await message.answer('✅ Рассылка успешно сохранена.')
        await state.clear()


@router.callback_query(F.data.startswith("mailing"))
async def handle_template_callback(call: CallbackQuery, state: FSMContext, session: AsyncSession, bot: Bot, user: User):
    # Извлекаем данные из callback
    callback_data = call.data.split(":")

    if len(callback_data) != 4:
        await call.answer("Некорректные данные.")
        return

    action, _, bot_id, template_id = callback_data  # `_` — так как второй элемент всегда 'mailing'

    try:
        bot_id = int(bot_id)
        template_id = int(template_id)
    except ValueError:
        await call.answer("Некорректные данные.")
        return

    # Извлекаем шаблон из базы данных
    mailing_template_query = await session.execute(
        select(Mailing).where(Mailing.id == template_id)
    )
    mailing_template = mailing_template_query.scalars().first()

    if not mailing_template:
        await call.answer("Шаблон не найден.")
        return

    # Определяем, есть ли кнопки и интервал
    buttons_text = '🔘 Есть кнопки' if mailing_template.mailing_buttons else '🔘 Кнопок нет'
    interval_text = mailing_template.interval if mailing_template.interval else '🔘 Нет интервала'

    # Генерируем клавиатуру для управления шаблоном
    keyboard = await builder_keyboard.get_template_settings_kb(mailing_template, bot_id)

    # Формируем текст сообщения
    new_text = (
        f'📋 Управление шаблоном\n\n'
        f'📝 Название: {mailing_template.name}\n'
        f'{buttons_text}\n\n'
        f'Текст: {mailing_template.mailing_text}\n'
        f'Интервал: {interval_text}\n'
        f'Выберите действие:'
    )

    # Если текст или клавиатура изменились, отправляем новое сообщение
    if call.message.text != new_text or call.message.reply_markup != keyboard:
        await bot.send_message(call.from_user.id, text=new_text, reply_markup=keyboard)
    else:
        await call.answer("Никаких изменений не было.")


@router.callback_query(F.data.startswith("template_text|"))
async def template_change_text(call: CallbackQuery, state: FSMContext, session: AsyncSession):
    template_id = call.data.split("|")[1]
    await state.update_data(template_id=template_id)
    await call.message.answer("Введите новый текст для шаблона:")
    await state.set_state(states.BotMailing.change_mailing_text)


@router.message(StateFilter(states.BotMailing.change_mailing_text))
async def change_mailing_text(message: types.Message, state: FSMContext, session: AsyncSession):
    new_text = message.text
    user_data = await state.get_data()
    template_id = user_data.get('template_id')

    async with session:
        mailing_template_query = await session.execute(
            select(Mailing).where(Mailing.id == template_id)
        )
        mailing_template = mailing_template_query.scalars().first()

        if not mailing_template:
            await message.answer("Шаблон не найден.")
            return

        mailing_template.mailing_text = new_text
        await session.commit()

        await message.answer("Текст шаблона  успешно изменен.")
        await state.clear()


@router.callback_query(F.data.startswith("template_buttons|"))
async def template_change_buttons(call: CallbackQuery, state: FSMContext, session: AsyncSession):
    template_id = call.data.split("|")[1]
    await state.update_data(template_id=template_id)
    await call.message.answer('Отправьте кнопки для рассылки в формате [текст + URL] или [текст + <code>webapp</code>].'
                              'Или нажмите кнопку, чтобы пропустить этот шаг.\n'
                              '<i>P.S. Webapp автоматически заменится на вебапп с выбранным доменом</i>',
                              parse_mode='HTML')
    await state.set_state(states.BotMailing.change_mailing_buttons)


@router.message(StateFilter(states.BotMailing.change_mailing_buttons))
async def change_mailing_buttons(message: types.Message, state: FSMContext, session: AsyncSession):
    new_buttons = message.text
    user_data = await state.get_data()
    template_id = user_data.get('template_id')

    async with session:
        mailing_template_query = await session.execute(
            select(Mailing).where(Mailing.id == template_id)
        )
        mailing_template = mailing_template_query.scalars().first()

        if not mailing_template:
            await message.answer("Шаблон не найден.")
            return

        mailing_template.mailing_buttons = new_buttons
        await session.commit()

        await message.answer("Кнопки шаблона успешно изменены.")
        await state.clear()


@router.callback_query(F.data.startswith("template_interval|"))
async def template_change_interval(call: CallbackQuery, state: FSMContext, session: AsyncSession):
    template_id = call.data.split("|")[1]
    await state.update_data(template_id=template_id)
    await call.message.answer(
        '⏱️ Введите интервал рассылки в минутах (от 60 до 2880): если не нужен интервал, поставьте 0.')
    await state.set_state(states.BotMailing.change_mailing_interval)


@router.message(StateFilter(states.BotMailing.change_mailing_interval))
async def change_mailing_interval(message: types.Message, state: FSMContext, session: AsyncSession):
    try:
        new_interval = int(message.text)
        if new_interval == 0:
            interval = None
        elif new_interval < 60 or new_interval > 2880:
            await message.answer('❗ Интервал должен быть в пределах от 60 до 2880 минут.')
            return
    except ValueError:
        await message.answer('❗ Введите число для интервала.')
        return
    user_data = await state.get_data()
    template_id = user_data.get('template_id')

    async with session:
        mailing_template_query = await session.execute(
            select(Mailing).where(Mailing.id == template_id)
        )
        mailing_template = mailing_template_query.scalars().first()

        if not mailing_template:
            await message.answer("Шаблон не найден.")
            return

        mailing_template.interval = new_interval
        await session.commit()

        await message.answer("Интервал шаблона успешно изменен.")
        await state.clear()


@router.callback_query(F.data.startswith("template_name|"))
async def template_change_name(call: CallbackQuery, state: FSMContext, session: AsyncSession):
    template_id = call.data.split("|")[1]
    await state.update_data(template_id=template_id)
    await call.message.answer("Введите новое название шаблона:")
    await state.set_state(states.BotMailing.change_mailing_name)


@router.message(StateFilter(states.BotMailing.change_mailing_name))
async def change_mailing_name(message: types.Message, state: FSMContext, session: AsyncSession):
    new_name = message.text
    user_data = await state.get_data()
    template_id = user_data.get('template_id')

    async with session:
        mailing_template_query = await session.execute(
            select(Mailing).where(Mailing.id == template_id)
        )
        mailing_template = mailing_template_query.scalars().first()

        if not mailing_template:
            await message.answer("Шаблон не найден.")
            return

        mailing_template.name = new_name
        await session.commit()

        await message.answer("Название шаблона успешно изменено.")
        await state.clear()


@router.callback_query(F.data.startswith("template_start|"))
async def start_template_mailing(call: CallbackQuery, session: AsyncSession, state: FSMContext, user: User, bot: Bot):
    data = await state.get_data()
    bot_id = data.get('bot_id')
    template_id = call.data.split("|")[1]
    async with session:
        # Выполнение запроса и получение шаблона
        mailing_template_query = await session.execute(
            select(Mailing).where(Mailing.id == template_id)
        )
        mailing_template = mailing_template_query.scalars().first()

        if mailing_template:
            # Обновление is_mailing на True
            mailing_template.is_mailing = True
            await session.commit()  # Коммитим изменения в базу данных
            await session.refresh(mailing_template)  # Обновляем объект после коммита

            # Определяем, есть ли кнопки и интервал
            buttons_text = '🔘 Есть кнопки' if mailing_template.mailing_buttons else '🔘 Кнопок нет'
            interval_text = mailing_template.interval if mailing_template.interval else '🔘 Нет интервала'

            # Генерируем клавиатуру для управления шаблоном
            keyboard = await builder_keyboard.get_template_settings_kb(mailing_template, bot_id)

            # Формируем текст сообщения
            new_text = (
                f'📋 Управление шаблоном\n\n'
                f'📝 Название: {mailing_template.name}\n'
                f'{buttons_text}\n\n'
                f'Текст: {mailing_template.mailing_text}\n'
                f'Интервал: {interval_text}\n'
                f'Выберите действие:'
            )
        await call.message.edit_text(text=new_text, reply_markup=keyboard)
        async with session:
            bot_made = await session.get(Made_Bots, bot_id)
            if bot_made.is_working and bot_made.process is not None:
                await call.message.answer('✅ Бот запущен! Запускаю рассылку')
                response_task = asyncio.create_task(
                    control_made_bot.send_mailing_to_other_bots(bot_made, mailing_template, session))
                await state.update_data(mailing_task=response_task)
                await load_bot_page(session, bot_made.bot_id, bot, user)
                await call.message.answer('✅ Рассылка запущена!', reply_markup=main_keyboard.main_menu)
            else:
                await call.message.answer('❌ Бот не запущен! Запускаю бота для рассылкы')
                await bot_start(bot_made)
                await session.commit()
                await asyncio.sleep(3)  # Wait for 5 seconds
                response_task = asyncio.create_task(
                    control_made_bot.send_mailing_to_other_bots(bot_made, mailing_template, session))
                await state.update_data(mailing_task=response_task)
                await load_bot_page(session, bot_made.bot_id, bot, user)
                await call.message.answer('✅ Рассылка запущена!', reply_markup=main_keyboard.main_menu)
        await call.answer("Рассылка шаблона запущена.")


@router.callback_query(F.data.startswith("template_stop|"))
async def stop_template_mailing(call: CallbackQuery, session: AsyncSession, state: FSMContext):
    template_id = call.data.split("|")[1]
    mailing_template_query = await session.execute(
        select(Mailing).where(Mailing.id == template_id)
    )
    mailing_template = mailing_template_query.scalars().first()
    data = await state.get_data()
    bot_id = data.get('bot_id')
    if mailing_template:
        # Обновление is_mailing на False
        mailing_template.is_mailing = False
        await session.commit()  # Коммитим изменения в базу данных
        await session.refresh(mailing_template)
        # Определяем, есть ли кнопки и интервал
        buttons_text = '🔘 Есть кнопки' if mailing_template.mailing_buttons else '🔘 Кнопок нет'
        interval_text = mailing_template.interval if mailing_template.interval else '🔘 Нет интервала'

        # Генерируем клавиатуру для управления шаблоном
        keyboard = await builder_keyboard.get_template_settings_kb(mailing_template, bot_id)

        # Формируем текст сообщения
        new_text = (
            f'📋 Управление шаблоном\n\n'
            f'📝 Название: {mailing_template.name}\n'
            f'{buttons_text}\n\n'
            f'Текст: {mailing_template.mailing_text}\n'
            f'Интервал: {interval_text}\n'
            f'Выберите действие:'
        )
        await call.message.edit_text(text=new_text, reply_markup=keyboard)
    data = await state.get_data()
    bot_id = data.get('bot_id')
    try:
        data = await state.get_data()
        mailing_task = data.get("mailing_task")  # Получаем Task

        if mailing_task and not mailing_task.done():
            mailing_task.cancel()  # Останавливаем задачу
            await call.message.answer("❌ Рассылка остановлена!")
        else:
            await call.message.answer("🚫 Рассылка уже остановлена или не запущена.")
    except Exception as e:
        await call.message.answer(f"❌ Ошибка при остановке рассылки: {e}")
