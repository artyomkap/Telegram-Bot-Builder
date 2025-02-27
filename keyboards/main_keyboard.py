from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton

main_menu = ReplyKeyboardMarkup(
    keyboard=[
        [
            KeyboardButton(text="🤖 Конструктор ботов"),
        ],
        [
            KeyboardButton(text="📄 Парсинг чатов"),
            KeyboardButton(text='📝 Спам-рассылка')
        ]
    ],
    resize_keyboard=True  # Клавиатура будет подстраиваться под размер экрана
)

profile_menu_buttons = [
    [InlineKeyboardButton(text="🔄 Сменить ник", callback_data="change_nickname"),
     InlineKeyboardButton(text="💸 Перевести средства", callback_data="transfer_funds")],
    [InlineKeyboardButton(text="🏧 Вывод средств", callback_data="withdraw_funds"),
     InlineKeyboardButton(text="💵 Пополнить средства", callback_data="top_up")]
]

profile_menu = InlineKeyboardMarkup(row_width=2, inline_keyboard=profile_menu_buttons)

withdraw_decision = [
    [InlineKeyboardButton(text='✅ Да', callback_data='withdraw_confirm'),
     InlineKeyboardButton(text='❌ Нет', callback_data='withdraw_cancel')]
]

withdraw_decision_kb = InlineKeyboardMarkup(inline_keyboard=withdraw_decision, row_width=2)


def get_crypto_bot_currencies():
    currencies = ['USDT', 'USDC', 'BTC', 'ETH', 'TON']
    crypto_bot_currencies_kb = []
    # Размещаем первые 6 значений в 3 ряда
    for i in range(0, len(currencies), 3):

        row_buttons = [InlineKeyboardButton(text=currency, callback_data=f'crypto_bot_currency|{currency}') for currency
                       in currencies[i:i + 3]]
        crypto_bot_currencies_kb.append(row_buttons)
    bnb = 'BNB'
    # Проверяем, есть ли дополнительные элементы
    crypto_bot_currencies_kb.append([InlineKeyboardButton(text=bnb, callback_data=f'crypto_bot_currency|{bnb}')])

    # Добавляем кнопку "Отменить действие" в отдельный ряд
    crypto_bot_currencies_kb.append([InlineKeyboardButton(text='❌ Отменить действие', callback_data='cancel_crypto_bot')])

    crypto_bot_currencies = InlineKeyboardMarkup(inline_keyboard=crypto_bot_currencies_kb)

    return crypto_bot_currencies


def check_crypto_bot_kb(url: str, invoice_hash: int):
    crypto_bot_status_kb = [
        [InlineKeyboardButton(text='🔗 Оплатить', url=url)],
        [InlineKeyboardButton(text='♻️ Проверить оплату', callback_data=f'check_crypto_bot|{invoice_hash}')]
    ]

    crypto_bot_status = InlineKeyboardMarkup(row_width=1, inline_keyboard=crypto_bot_status_kb)

    return crypto_bot_status
