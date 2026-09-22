from aiogram.fsm.state import State, StatesGroup


class AddAccount(StatesGroup):
    waiting_phone = State()
    waiting_code = State()
    waiting_2fa = State()


class SetPassword(StatesGroup):
    waiting_password = State()


class BuyFlow(StatesGroup):
    waiting_api_key = State()
    setting_price_from = State()
    setting_price_to = State()
    setting_country = State()
    setting_age_from = State()
    setting_contacts_from = State()


class MassPassword(StatesGroup):
    waiting_password = State()


class UploadSession(StatesGroup):
    waiting_phone = State()
    waiting_file = State()
