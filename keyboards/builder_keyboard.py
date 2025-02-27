import json

from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from database.models import User, Domains, SubDomains, Landing, Made_Bots, Mailing


async def get_bot_menu_kb(session: AsyncSession, user: User):
    async with session:
        made_bots_query = await session.execute(select(Made_Bots).where(Made_Bots.user_tg_id == user.tg_id))
        made_bots = made_bots_query.scalars().all()

        bot_menu_kb = []

        for bot in made_bots:
            bot_text = f"{bot.bot_name}"
            bot_menu_kb.append([InlineKeyboardButton(text=bot_text, callback_data=f'bot_settings|{bot.id}')])

        bot_menu_kb.append([InlineKeyboardButton(text='🤖 Создать бота', callback_data=f'create_bot')])
        bot_menu = InlineKeyboardMarkup(row_width=1, inline_keyboard=bot_menu_kb)

        return bot_menu


#
# async def get_domains_create_kb(session: AsyncSession, user: User):
#     async with session:
#         domains_query = await session.execute(
#             select(Domains).where(Domains.user_tg_id == user.tg_id)
#         )
#         domains = domains_query.scalars().all()
#
#         domains_kb = []
#
#         for domain in domains:
#             domain_text = f'{domain.domain}'
#             domains_kb.append(
#                 [InlineKeyboardButton(text=f'🌐 {domain_text}', callback_data=f'domain_bot|{domain.id}')]
#             )
#
#         domains_kb.append([InlineKeyboardButton(text='🔙 Назад', callback_data='back_to_bot')])
#         kb = InlineKeyboardMarkup(row_width=1, inline_keyboard=domains_kb)
#
#         return kb


back_to_bot_kb = [
    [InlineKeyboardButton(text='🔙 Назад', callback_data='back_to_bot_choice')]
]

back_to_bot = InlineKeyboardMarkup(inline_keyboard=back_to_bot_kb)


async def go_to_bot_setting(new_bot: Made_Bots):
    kb = [
        [InlineKeyboardButton(text=f'🤖 К настройке {new_bot.bot_id}', callback_data=f'bot_settings|{new_bot.id}')]
    ]
    kb = InlineKeyboardMarkup(inline_keyboard=kb)
    return kb


async def get_bot_settings_kb(bot_instance: Made_Bots):
    kb = []

    # Row 1
    kb.append([
        InlineKeyboardButton(text='📝 Настройка кнопок', callback_data=f'bot_answers|{bot_instance.id}'),
        InlineKeyboardButton(text='📰 Запустить рассылку', callback_data=f'bot_run_mailing|{bot_instance.id}')
    ])

    # Row 2
    start_stop_text = "⏹️ Остановить" if bot_instance.is_working else "🚀 Запустить"
    start_stop_callback = f"bot_start_stop|{bot_instance.id}"
    kb.append([
        InlineKeyboardButton(text=start_stop_text, callback_data=start_stop_callback),
        InlineKeyboardButton(text='️🖐 Удалить бота', callback_data=f'bot_delete|{bot_instance.id}')
    ])

    # Row 3
    web_app_position_text = "❌ WebApp в углу" if not bot_instance.web_app_position else "✅ WebApp в углу"
    web_app_position_callback = f"bot_web_app_position|{bot_instance.id}"
    web_app_text_callback = f"bot_web_app_text|{bot_instance.id}"
    row3 = []
    row3.append(InlineKeyboardButton(text=web_app_position_text, callback_data=web_app_position_callback))
    row3.append(InlineKeyboardButton(text="⚙️ Настроить текст Web App", callback_data=web_app_text_callback))
    kb.append(row3)

    # Row 4
    kb.append([
        InlineKeyboardButton(text="🔄 Изменить ссылку на web_app", callback_data=f'bot_change_domain|{bot_instance.id}'),
        InlineKeyboardButton(text="📊 Cтатистика", callback_data=f'bot_statistics|{bot_instance.id}')
    ])

    # Row 5
    kb.append([
        InlineKeyboardButton(text='📥 Экспорт базы данных', callback_data=f'bot_export_db|{bot_instance.id}'),
        InlineKeyboardButton(text='🔁 Обновить', callback_data=f'bot_update|{bot_instance.id}')
    ])
    #
    # Row 6
    kb.append([
        InlineKeyboardButton(text='🔃 Изменить имя', callback_data=f'bot_change_name|{bot_instance.id}'),
        InlineKeyboardButton(text='⤵️ Перенести настройки', callback_data=f'bot_transfer_settings|{bot_instance.id}')
    ])

    # Row 7
    kb.append([
        InlineKeyboardButton(text='📦 Шаблоны рассылок', callback_data=f'bot_mailing_templates|{bot_instance.id}'),
        InlineKeyboardButton(text='✅ Сбор статистики', callback_data=f'bot_collect_statistics|{bot_instance.id}')
    ])

    kb.append([InlineKeyboardButton(text='🔙 Назад', callback_data='back_to_bot_chose')])

    kb = InlineKeyboardMarkup(inline_keyboard=kb)  # Corrected: Use InlineKeyboardMarkup
    return kb


bot_answers_setting_kb = [
    [
        InlineKeyboardButton(text='📝 Стартовое сообщение', callback_data='change_message_bot'),
        InlineKeyboardButton(text='⚙️ Управление кнопками', callback_data='manage_buttons_bot'),
    ],
    [
        InlineKeyboardButton(text='👥 Реферальная программа', callback_data='referral_program_bot'),
    ],
    [
        InlineKeyboardButton(text='⬅️ Назад', callback_data='back_to_bot_menu')
    ]
]

bot_answers_setting = InlineKeyboardMarkup(inline_keyboard=bot_answers_setting_kb)


async def get_manage_buttons_menu(new_bot: Made_Bots):
    buttons = new_bot.buttons
    keyboard = []

    if buttons:
        buttons_data = json.loads(new_bot.buttons)
        row = []  # Initialize an empty row

        for i, button in enumerate(buttons_data):
            button_id = button.get('id', str(i))  # Use button id or index if id is missing
            edit_callback_data = f"edit_button|{button_id}"  # Add delete callback

            row.append(
                InlineKeyboardButton(text=f"{button['type']} {button['text']}", callback_data=edit_callback_data))

            if (i + 1) % 2 == 0:  # If two buttons are in the row
                keyboard.append(row)  # Add the row to the keyboard
                row = []  # Reset the row

        if row:  # Add any remaining buttons if the number is odd
            keyboard.append(row)

    # Add "Add Button", "Delete All", and "Back" buttons
    keyboard.extend([
        [InlineKeyboardButton(text="➕ Добавить кнопку", callback_data="add_button"),
         InlineKeyboardButton(text="🗑 Удалить все", callback_data="delete_all")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_bot_choice")]
    ])

    keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard)
    return keyboard


create_button_types_kb = [
    [InlineKeyboardButton(text='💬 Новое сообщение', callback_data='choose_button_type|0'),
     InlineKeyboardButton(text='✏️ Изменить текущее', callback_data='choose_button_type|1')],
    [InlineKeyboardButton(text='🔔 Всплывающий ответ', callback_data='choose_button_type|2')],
    [InlineKeyboardButton(text='🔗 Внешняя ссылка', callback_data='choose_button_type|3'),
     InlineKeyboardButton(text='🌐 WebApp', callback_data='choose_button_type|4')],
    [InlineKeyboardButton(text='🔙 Назад', callback_data='back_to_bot_menu')]
]

create_button_type = InlineKeyboardMarkup(inline_keyboard=create_button_types_kb)


async def get_referal_settings_kb(bot_instance: Made_Bots):
    if bot_instance.is_referal:
        status = "❌ Отключить"
        callback = 'off'
    else:
        status = '✅ Включить'
        callback = 'on'
    referal_program_kb = [
        [InlineKeyboardButton(text=f'{status}', callback_data=f'switch_referal|{callback}')],
        [InlineKeyboardButton(text='🔙 Назад', callback_data='back_to_bot_choice')]
    ]
    kb = InlineKeyboardMarkup(inline_keyboard=referal_program_kb)
    return kb


delete_bot_choice_kb = [
    [InlineKeyboardButton(text='✅ Да', callback_data='delete_bot|yes')],
    [InlineKeyboardButton(text='❌ Нет', callback_data='delete_bot|no')]
]

delete_bot_choice = InlineKeyboardMarkup(inline_keyboard=delete_bot_choice_kb)


async def get_domains_kb(session: AsyncSession, user: User):
    domains_query = await session.execute(select(Domains).where(Domains.user_tg_id == user.tg_id))
    domains = domains_query.scalars().all()

    domain_kb = []

    for domain in domains:
        domain_text = f"{domain.domain}"  # Текст кнопки с доменом
        domain_kb.append([InlineKeyboardButton(text=domain_text, callback_data=f'domain_bot_change|{domain.id}')])

    domain_kb.append([InlineKeyboardButton(text='🔙 Назад', callback_data='back_to_bot_menu')])

    domain = InlineKeyboardMarkup(inline_keyboard=domain_kb)

    return domain


mailing_skip_buttons_kb = [
    [InlineKeyboardButton(text='Пропустить кнопки', callback_data='mailing_skip_buttons')]
]

mailing_skip_buttons = InlineKeyboardMarkup(inline_keyboard=mailing_skip_buttons_kb)

mailing_confirm_launch_kb = [
    [InlineKeyboardButton(text='✅ Запустить рассылку', callback_data='mailing_confirm_launch'),
     InlineKeyboardButton(text='❌ Отмена', callback_data='mailing_confirm_cancel')]
]

mailing_confirm_launch = InlineKeyboardMarkup(inline_keyboard=mailing_confirm_launch_kb)


async def get_back_to_bot_settings(bot_id):
    back_to_bot_settings_kb = [
        [InlineKeyboardButton(text='🔙 Назад', callback_data=f'back_to_bot_settings|{bot_id}')]
    ]

    back_to_bot_settings = InlineKeyboardMarkup(inline_keyboard=back_to_bot_settings_kb)
    return back_to_bot_settings


async def get_template_settings_kb(mailing_template: Mailing, bot_id):
    template_settings_kb = [
        [InlineKeyboardButton(text='📝 Изменить текст', callback_data=f'template_text|{mailing_template.id}'),
         InlineKeyboardButton(text='🔘 Изменить кнопки', callback_data=f'template_buttons|{mailing_template.id}')],
        [InlineKeyboardButton(text='🕒 Изменить интервал', callback_data=f'template_interval|{mailing_template.id}'),
         InlineKeyboardButton(text='✏️ Изменить имя', callback_data=f'template_name|{mailing_template.id}')]
    ]
    if mailing_template.is_mailing:
        template_settings_kb.append(
            [InlineKeyboardButton(text='⏹️ Остановить', callback_data=f'template_stop|{mailing_template.id}')])
    else:
        template_settings_kb.append(
            [InlineKeyboardButton(text='▶️ Запустить', callback_data=f'template_start|{mailing_template.id}')])

    template_settings_kb.append(
        [InlineKeyboardButton(text='🗑 Удалить шаблон', callback_data=f'template_delete|{mailing_template.id}')])
    template_settings_kb.append([InlineKeyboardButton(text='🔙 Назад', callback_data=f'bot_mailing_templates|{bot_id}')])

    markup = InlineKeyboardMarkup(inline_keyboard=template_settings_kb)

    return markup