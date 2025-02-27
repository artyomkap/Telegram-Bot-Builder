from aiogram.fsm.state import StatesGroup, State


class ProfileState(StatesGroup):
    new_nickname = State()
    id_or_nick = State()
    transfer_amount = State()
    withdraw_amount = State()
    withdraw_wallet = State()
    top_up_amount = State()


class DomainState(StatesGroup):
    new_domain = State()
    domain_id = State()
    landing_id = State()


class ManifestState(StatesGroup):
    manifest_id = State()
    manifest_title = State()
    manifest_image = State()
    manifest_link = State()


class CloakingState(StatesGroup):
    cloaking_id = State()
    countries = State()
    ips = State()
    isp_providers = State()


class NewBotState(StatesGroup):
    domain_id = State()
    bot_token = State()
    start_text = State()
    button_type = State()
    button_text = State()
    button_answer = State()
    button_url = State()
    web_app_text = State()
    web_app_link = State()
    change_web_app_link = State()
    new_bot_name = State()
    change_button_text = State()
    change_button_url = State()
    change_button_answer = State()


class BotMailing(StatesGroup):
    mailing_text = State()
    mailing_buttons = State()
    new_mailing_name = State()
    new_mailing_text = State()
    new_mailing_buttons = State()
    new_mailing_interval = State()
    change_mailing_text = State()
    change_mailing_buttons = State()
    change_mailing_name = State()
    change_mailing_interval = State()
    template_id = State()
    mailing_response = State()


class ParserStates(StatesGroup):
    begin_text = State()
    end_text = State()


