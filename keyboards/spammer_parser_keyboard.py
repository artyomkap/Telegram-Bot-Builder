from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton

spammer_parser_menu_kb = [
    [InlineKeyboardButton(text='📄 Парсер', callback_data='parser'),
     InlineKeyboardButton(text='📨 Спамер', callback_data='spammer')]
]

spammer_parser_menu = InlineKeyboardMarkup(inline_keyboard=spammer_parser_menu_kb)

parser_menu_kb = [
    [InlineKeyboardButton(text='⤴️ Изменить имена', callback_data='change_names'),
     InlineKeyboardButton(text='⤵️ Изменить окончания', callback_data='change_endings')],
    [InlineKeyboardButton(text='💭 Чаты', callback_data='chats'),
     InlineKeyboardButton(text='📁 Парсить', callback_data='start_parsing')],
    [InlineKeyboardButton(text='🔙 Назад', callback_data='back_to_spam_parse_menu')]
]

parser_menu = InlineKeyboardMarkup(inline_keyboard=parser_menu_kb)

chats_menu_kb = [
    [InlineKeyboardButton(text='Выгрузить файлом', callback_data='download_tg_folder')],
    [InlineKeyboardButton(text='🔙 Назад', callback_data='back_to_spam_parse_menu')]
]

chats_menu = InlineKeyboardMarkup(inline_keyboard=chats_menu_kb)

spammer_menu_kb = [
     [InlineKeyboardButton(text='🕒 Настройка задержки', callback_data="spammer_delay")],
     [InlineKeyboardButton(text='▶️ Запустить спам', callback_data="start_spam")],
     [InlineKeyboardButton(text='📝 Добавить новую сессию', callback_data='add_session'),
      InlineKeyboardButton(text='🗑 Удалить мою сессию', callback_data='delete_session')],
    [InlineKeyboardButton(text='🔙 Назад', callback_data='back_to_spam_parse_menu')]
]

spammer_menu = InlineKeyboardMarkup(inline_keyboard=spammer_menu_kb)

back_to_spam_menu_kb = [
    [InlineKeyboardButton(text='🔙 Назад', callback_data='back_to_spam_menu')]
]

back_to_spam_menu = InlineKeyboardMarkup(inline_keyboard=back_to_spam_menu_kb)

start_spammer_menu_kb = [
    [InlineKeyboardButton(text='✏️ Ввести сообщение вручную', callback_data='manual_message')],
    [InlineKeyboardButton(text='❤️ Сообщение из избранного', callback_data='saved_message')],
    [InlineKeyboardButton(text='🔙 Назад', callback_data='back_to_spam_menu')]
]

start_spammer_menu = InlineKeyboardMarkup(inline_keyboard=start_spammer_menu_kb)

choose_chats_kb = [
    [InlineKeyboardButton(text='Чаты из парсера', callback_data='chats|1'),
     InlineKeyboardButton(text='Чаты из папки(ссылка)', callback_data='chats|2'),
     InlineKeyboardButton(text='Чаты пользователя', callback_data='chats|3')],
    [InlineKeyboardButton(text='🔙 Назад', callback_data='back_to_start_menu')]
]

choose_chats = InlineKeyboardMarkup(inline_keyboard=choose_chats_kb)


confirm_spam_menu_kb = [
    [InlineKeyboardButton(text='▶️ Начать', callback_data='confirm_spam'),
     InlineKeyboardButton(text='❌ Нет', callback_data='back_to_spam_menu')]
]

confirm_spam_menu = InlineKeyboardMarkup(inline_keyboard=confirm_spam_menu_kb)

delete_session_kb = [
    [InlineKeyboardButton(text='✅ Да', callback_data='session_delete_confirm'),
     InlineKeyboardButton(text='❌ Нет', callback_data='back_to_spam_menu')]
]

delete_session = InlineKeyboardMarkup(inline_keyboard=delete_session_kb)


confirm_start_spam_kb = [
    [InlineKeyboardButton(text='Начать рассылку', callback_data='start_spamming')],
    [InlineKeyboardButton(text='🔙 Отменить', callback_data='back_to_start_menu')]
]

confirm_start_spam = InlineKeyboardMarkup(inline_keyboard=confirm_start_spam_kb)


stop_spam_kb = [
    [InlineKeyboardButton(text='❌ Остановить рассылку', callback_data='stop_spam')]
]

stop_spam = InlineKeyboardMarkup(inline_keyboard=stop_spam_kb)