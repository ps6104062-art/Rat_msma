import os
import asyncio
from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery, FSInputFile
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext

import keyboards as kb
import texts
from states import AddAccount, SetPassword, BuyFlow, MassPassword
from database import (
    init_db, add_account, get_accounts, get_account, delete_account,
    save_api_key, get_api_key, update_session
)
from account_manager import (
    send_code, sign_in, clear_chats, clear_contacts,
    kick_all_sessions, leave_all_bots, set_2fa_password, download_session
)
from tronaccs_api import TronaccsAPI
from config import ADMIN_IDS

router = Router()

# ─── хранилище временных данных ───
_temp = {}  # {user_id: {...}}

def temp(user_id: int) -> dict:
    if user_id not in _temp:
        _temp[user_id] = {}
    return _temp[user_id]


# ════════════════════════════════════════
#  СТАРТ
# ════════════════════════════════════════

@router.message(CommandStart())
async def cmd_start(msg: Message):
    if msg.from_user.id not in ADMIN_IDS:
        return await msg.answer("⛔ Нет доступа.")
    await init_db()
    await msg.answer(texts.WELCOME, reply_markup=kb.main_menu(), parse_mode="HTML")


# ════════════════════════════════════════
#  НАВИГАЦИЯ
# ════════════════════════════════════════

@router.callback_query(F.data == "back_main")
async def back_main(cq: CallbackQuery):
    await cq.message.edit_text(texts.WELCOME, reply_markup=kb.main_menu(), parse_mode="HTML")


@router.callback_query(F.data == "menu_accounts")
async def menu_accounts(cq: CallbackQuery):
    accs = await get_accounts()
    if not accs:
        await cq.message.edit_text(texts.ACCOUNTS_EMPTY, reply_markup=kb.accounts_menu([]), parse_mode="HTML")
    else:
        text = texts.accounts_menu_text(len(accs))
        await cq.message.edit_text(text, reply_markup=kb.accounts_menu(accs), parse_mode="HTML")


@router.callback_query(F.data == "menu_buy")
async def menu_buy(cq: CallbackQuery):
    api_key = await get_api_key(cq.from_user.id)
    await cq.message.edit_text(
        texts.BUY_MENU + (texts.BUY_NO_API if not api_key else ""),
        reply_markup=kb.buy_menu(bool(api_key)),
        parse_mode="HTML"
    )


@router.callback_query(F.data == "menu_settings")
async def menu_settings(cq: CallbackQuery):
    await cq.message.edit_text(texts.SETTINGS_MENU, reply_markup=kb.settings_menu(), parse_mode="HTML")


# ════════════════════════════════════════
#  ДОБАВЛЕНИЕ АККАУНТА
# ════════════════════════════════════════

@router.callback_query(F.data == "acc_add")
async def acc_add(cq: CallbackQuery, state: FSMContext):
    await state.set_state(AddAccount.waiting_phone)
    await cq.message.edit_text(
        "📞 <b>Введите номер телефона</b>\n\nФормат: <code>+79001234567</code>",
        reply_markup=kb.back_btn("menu_accounts"), parse_mode="HTML"
    )


@router.message(AddAccount.waiting_phone)
async def acc_phone(msg: Message, state: FSMContext):
    phone = msg.text.strip()
    if not phone.startswith("+"):
        return await msg.answer("❌ Неверный формат. Пример: <code>+79001234567</code>", parse_mode="HTML")

    await msg.answer(f"📤 Отправляю код на <code>{phone}</code>...", parse_mode="HTML")
    result = await send_code(phone)

    if not result["ok"]:
        await state.clear()
        return await msg.answer(f"❌ Ошибка: {result['error']}", reply_markup=kb.back_btn("acc_add"))

    await state.update_data(phone=phone, phone_code_hash=result["phone_code_hash"])
    await state.set_state(AddAccount.waiting_code)
    await msg.answer(
        "✅ Код отправлен!\n\n🔢 <b>Введите код из Telegram:</b>",
        parse_mode="HTML"
    )


@router.message(AddAccount.waiting_code)
async def acc_code(msg: Message, state: FSMContext):
    code = msg.text.strip()
    data = await state.get_data()

    result = await sign_in(data["phone"], code, data["phone_code_hash"])

    if result.get("need_2fa"):
        await state.set_state(AddAccount.waiting_2fa)
        return await msg.answer("🔐 <b>Введите пароль 2FA:</b>", parse_mode="HTML")

    if not result["ok"]:
        return await msg.answer(f"❌ {result['error']}")

    await add_account(data["phone"], result["session_file"])
    await state.clear()
    await msg.answer(
        f"✅ <b>Аккаунт добавлен!</b>\n\n👤 {result.get('user', '')}\n📞 {data['phone']}",
        reply_markup=kb.back_btn("menu_accounts"), parse_mode="HTML"
    )


@router.message(AddAccount.waiting_2fa)
async def acc_2fa(msg: Message, state: FSMContext):
    password = msg.text.strip()
    data = await state.get_data()

    result = await sign_in(data["phone"], data.get("code", ""), data["phone_code_hash"], password)

    if not result["ok"]:
        return await msg.answer(f"❌ {result['error']}")

    await add_account(data["phone"], result["session_file"], password)
    await state.clear()
    await msg.answer(
        f"✅ <b>Аккаунт добавлен!</b>\n\n👤 {result.get('user', '')}\n📞 {data['phone']}",
        reply_markup=kb.back_btn("menu_accounts"), parse_mode="HTML"
    )


# ════════════════════════════════════════
#  ВЫБОР АККАУНТОВ
# ════════════════════════════════════════

@router.callback_query(F.data == "acc_select_one")
async def acc_select_one(cq: CallbackQuery):
    accs = await get_accounts()
    accs_list = [dict(a) for a in accs]
    await cq.message.edit_text(
        "📱 <b>Выберите аккаунт:</b>",
        reply_markup=kb.account_list(accs_list), parse_mode="HTML"
    )


@router.callback_query(F.data == "acc_select_all")
async def acc_select_all(cq: CallbackQuery):
    accs = await get_accounts()
    accs_list = [dict(a) for a in accs]
    selected = temp(cq.from_user.id).get("selected", [])
    await cq.message.edit_text(
        f"☑️ <b>Массовые действия</b>\nВыбрано: {len(selected)}/{len(accs_list)}",
        reply_markup=kb.account_list(accs_list, selected, multi=True), parse_mode="HTML"
    )


@router.callback_query(F.data.startswith("acc_toggle_"))
async def acc_toggle(cq: CallbackQuery):
    acc_id = int(cq.data.split("_")[2])
    t = temp(cq.from_user.id)
    selected = t.get("selected", [])

    if acc_id in selected:
        selected.remove(acc_id)
    else:
        selected.append(acc_id)
    t["selected"] = selected

    accs = await get_accounts()
    accs_list = [dict(a) for a in accs]
    await cq.message.edit_reply_markup(
        reply_markup=kb.account_list(accs_list, selected, multi=True)
    )


@router.callback_query(F.data.startswith("acc_open_"))
async def acc_open(cq: CallbackQuery):
    acc_id = int(cq.data.split("_")[2])
    acc = await get_account(acc_id)
    if not acc:
        return await cq.answer("Аккаунт не найден")
    await cq.message.edit_text(
        texts.account_info(dict(acc)),
        reply_markup=kb.single_account_menu(acc_id), parse_mode="HTML"
    )


# ════════════════════════════════════════
#  ДЕЙСТВИЯ С ОДНИМ АККАУНТОМ
# ════════════════════════════════════════

async def _run_action(cq: CallbackQuery, acc_id: int, action_name: str, coro):
    acc = await get_account(acc_id)
    if not acc:
        return await cq.answer("Аккаунт не найден")

    msg = await cq.message.edit_text(f"⏳ <b>{action_name}...</b>", parse_mode="HTML")
    result = await coro(acc["phone"], acc["session_file"])

    if result["ok"]:
        info = ""
        if "cleared" in result:
            info = f"\nОчищено: {result['cleared']}"
        if "deleted" in result:
            info = f"\nУдалено: {result['deleted']}"
        if "blocked" in result:
            info = f"\nЗаблокировано: {result['blocked']}"
        await msg.edit_text(
            f"✅ <b>{action_name} выполнено!</b>{info}",
            reply_markup=kb.back_btn(f"acc_open_{acc_id}"), parse_mode="HTML"
        )
    else:
        await msg.edit_text(
            f"❌ <b>Ошибка:</b> {result['error']}",
            reply_markup=kb.back_btn(f"acc_open_{acc_id}"), parse_mode="HTML"
        )


@router.callback_query(F.data.startswith("do_clear_chats_"))
async def do_clear_chats(cq: CallbackQuery):
    acc_id = int(cq.data.split("_")[3])
    await _run_action(cq, acc_id, "Очистка чатов", clear_chats)


@router.callback_query(F.data.startswith("do_clear_contacts_"))
async def do_clear_contacts(cq: CallbackQuery):
    acc_id = int(cq.data.split("_")[3])
    await _run_action(cq, acc_id, "Очистка контактов", clear_contacts)


@router.callback_query(F.data.startswith("do_kick_sessions_"))
async def do_kick_sessions(cq: CallbackQuery):
    acc_id = int(cq.data.split("_")[3])
    await _run_action(cq, acc_id, "Кик сессий", kick_all_sessions)


@router.callback_query(F.data.startswith("do_leave_bots_"))
async def do_leave_bots(cq: CallbackQuery):
    acc_id = int(cq.data.split("_")[3])
    await _run_action(cq, acc_id, "Удаление из ботов", leave_all_bots)


@router.callback_query(F.data.startswith("do_download_"))
async def do_download(cq: CallbackQuery, bot: Bot):
    acc_id = int(cq.data.split("_")[2])
    acc = await get_account(acc_id)
    if not acc:
        return await cq.answer("Аккаунт не найден")

    path = await download_session(acc["session_file"])
    if not path:
        return await cq.answer("❌ Файл сессии не найден")

    await cq.message.answer_document(
        FSInputFile(path, filename=f"{acc['phone']}.session"),
        caption=f"📦 Сессия {acc['phone']}"
    )
    await cq.answer("✅ Отправлено")


@router.callback_query(F.data.startswith("do_set_password_"))
async def do_set_password(cq: CallbackQuery, state: FSMContext):
    acc_id = int(cq.data.split("_")[3])
    await state.set_state(SetPassword.waiting_password)
    await state.update_data(acc_id=acc_id)
    await cq.message.edit_text(
        "🔑 <b>Введите новый пароль 2FA:</b>",
        reply_markup=kb.back_btn(f"acc_open_{acc_id}"), parse_mode="HTML"
    )


@router.message(SetPassword.waiting_password)
async def set_password_input(msg: Message, state: FSMContext):
    data = await state.get_data()
    acc_id = data["acc_id"]
    acc = await get_account(acc_id)
    if not acc:
        await state.clear()
        return await msg.answer("Аккаунт не найден")

    await msg.answer("⏳ Устанавливаю пароль...")
    result = await set_2fa_password(acc["phone"], acc["session_file"], msg.text.strip())
    await state.clear()

    if result["ok"]:
        await msg.answer("✅ <b>Пароль 2FA установлен!</b>",
                        reply_markup=kb.back_btn(f"acc_open_{acc_id}"), parse_mode="HTML")
    else:
        await msg.answer(f"❌ Ошибка: {result['error']}",
                        reply_markup=kb.back_btn(f"acc_open_{acc_id}"))


@router.callback_query(F.data.startswith("do_get_code_"))
async def do_get_code(cq: CallbackQuery, state: FSMContext):
    acc_id = int(cq.data.split("_")[3])
    acc = await get_account(acc_id)
    if not acc:
        return await cq.answer("Аккаунт не найден")

    await cq.message.edit_text("⏳ Отправляю код...")
    result = await send_code(acc["phone"])

    if result["ok"]:
        await state.update_data(phone=acc["phone"], phone_code_hash=result["phone_code_hash"], acc_id=acc_id)
        await cq.message.edit_text(
            f"✅ <b>Код отправлен</b> на <code>{acc['phone']}</code>\n\nВведи полученный код:",
            reply_markup=kb.back_btn(f"acc_open_{acc_id}"), parse_mode="HTML"
        )
    else:
        await cq.message.edit_text(
            f"❌ Ошибка: {result['error']}",
            reply_markup=kb.back_btn(f"acc_open_{acc_id}")
        )


@router.callback_query(F.data.startswith("do_delete_acc_"))
async def do_delete_acc(cq: CallbackQuery):
    acc_id = int(cq.data.split("_")[3])
    await cq.message.edit_text(
        "⚠️ <b>Удалить аккаунт?</b>\n\nЭто действие нельзя отменить.",
        reply_markup=kb.confirm_cancel(f"confirm_delete_{acc_id}", "menu_accounts"),
        parse_mode="HTML"
    )


@router.callback_query(F.data.startswith("confirm_delete_"))
async def confirm_delete(cq: CallbackQuery):
    acc_id = int(cq.data.split("_")[2])
    await delete_account(acc_id)
    await cq.message.edit_text(
        "✅ <b>Аккаунт удалён.</b>",
        reply_markup=kb.back_btn("menu_accounts"), parse_mode="HTML"
    )


# ════════════════════════════════════════
#  МАССОВЫЕ ДЕЙСТВИЯ
# ════════════════════════════════════════

@router.callback_query(F.data == "acc_mass_actions")
async def acc_mass_actions(cq: CallbackQuery):
    selected = temp(cq.from_user.id).get("selected", [])
    if not selected:
        return await cq.answer("Выберите хотя бы один аккаунт")
    await cq.message.edit_text(
        f"⚡ <b>Массовые действия</b>\nВыбрано: <b>{len(selected)}</b> аккаунтов\n\nВыберите действие:",
        reply_markup=kb.mass_actions_menu(selected), parse_mode="HTML"
    )


async def _run_mass_action(cq: CallbackQuery, ids: list, action_name: str, action_func):
    total = len(ids)
    msg = await cq.message.edit_text(
        f"⚙️ <b>{action_name}</b>\n\n{texts.progress_bar(0, total)}",
        parse_mode="HTML"
    )
    done = 0
    errors = 0

    for acc_id in ids:
        acc = await get_account(int(acc_id))
        if not acc:
            errors += 1
            continue
        try:
            await action_func(acc["phone"], acc["session_file"])
            done += 1
        except Exception:
            errors += 1

        await msg.edit_text(
            f"⚙️ <b>{action_name}</b>\n\n{texts.progress_bar(done + errors, total)}\n✅ {done} | ❌ {errors}",
            parse_mode="HTML"
        )
        await asyncio.sleep(0.5)

    await msg.edit_text(
        f"✅ <b>{action_name} завершено!</b>\n\nУспешно: {done}\nОшибок: {errors}",
        reply_markup=kb.back_btn("menu_accounts"), parse_mode="HTML"
    )


@router.callback_query(F.data.startswith("mass_clear_chats|"))
async def mass_clear_chats(cq: CallbackQuery):
    ids = cq.data.split("|")[1].split(",")
    await _run_mass_action(cq, ids, "Очистка чатов", clear_chats)


@router.callback_query(F.data.startswith("mass_clear_contacts|"))
async def mass_clear_contacts(cq: CallbackQuery):
    ids = cq.data.split("|")[1].split(",")
    await _run_mass_action(cq, ids, "Очистка контактов", clear_contacts)


@router.callback_query(F.data.startswith("mass_kick_sessions|"))
async def mass_kick_sessions(cq: CallbackQuery):
    ids = cq.data.split("|")[1].split(",")
    await _run_mass_action(cq, ids, "Кик сессий", kick_all_sessions)


@router.callback_query(F.data.startswith("mass_leave_bots|"))
async def mass_leave_bots(cq: CallbackQuery):
    ids = cq.data.split("|")[1].split(",")
    await _run_mass_action(cq, ids, "Удаление из ботов", leave_all_bots)


@router.callback_query(F.data.startswith("mass_download|"))
async def mass_download(cq: CallbackQuery, bot: Bot):
    ids = cq.data.split("|")[1].split(",")
    await cq.message.edit_text("⏳ Собираю сессии...")
    sent = 0
    for acc_id in ids:
        acc = await get_account(int(acc_id))
        if not acc:
            continue
        path = await download_session(acc["session_file"])
        if path:
            await cq.message.answer_document(
                FSInputFile(path, filename=f"{acc['phone']}.session"),
                caption=f"📦 {acc['phone']}"
            )
            sent += 1
    await cq.message.answer(
        f"✅ Отправлено {sent} сессий",
        reply_markup=kb.back_btn("menu_accounts")
    )


@router.callback_query(F.data.startswith("mass_set_password|"))
async def mass_set_password(cq: CallbackQuery, state: FSMContext):
    ids = cq.data.split("|")[1].split(",")
    await state.set_state(MassPassword.waiting_password)
    await state.update_data(mass_ids=ids)
    await cq.message.edit_text(
        f"🔑 <b>Введите пароль 2FA</b>\n\nБудет установлен на <b>{len(ids)}</b> аккаунтов:",
        reply_markup=kb.back_btn("acc_select_all"), parse_mode="HTML"
    )


@router.message(MassPassword.waiting_password)
async def mass_password_input(msg: Message, state: FSMContext):
    data = await state.get_data()
    ids = data["mass_ids"]
    password = msg.text.strip()
    await state.clear()
    await msg.answer(f"⏳ Устанавливаю пароль на {len(ids)} аккаунтов...")

    done = 0
    errors = 0
    for acc_id in ids:
        acc = await get_account(int(acc_id))
        if not acc:
            errors += 1
            continue
        result = await set_2fa_password(acc["phone"], acc["session_file"], password)
        if result["ok"]:
            done += 1
        else:
            errors += 1
        await asyncio.sleep(0.5)

    await msg.answer(
        f"✅ <b>Готово!</b>\n\nУстановлено: {done}\nОшибок: {errors}",
        reply_markup=kb.back_btn("menu_accounts"), parse_mode="HTML"
    )


# ════════════════════════════════════════
#  СКУПКА — TRONACCS API
# ════════════════════════════════════════

@router.callback_query(F.data.in_({"buy_set_api", "settings_api"}))
async def buy_set_api(cq: CallbackQuery, state: FSMContext):
    await state.set_state(BuyFlow.waiting_api_key)
    await cq.message.edit_text(
        "🔑 <b>Введите API ключ tronaccs.market</b>\n\n"
        "Найти: <i>tronaccs.market → Профиль → API</i>",
        reply_markup=kb.back_btn("menu_buy"), parse_mode="HTML"
    )


@router.message(BuyFlow.waiting_api_key)
async def buy_api_key_input(msg: Message, state: FSMContext):
    api_key = msg.text.strip()
    await msg.answer("🔍 Проверяю ключ...")

    api = TronaccsAPI(api_key)
    valid = await api.validate_key()

    if not valid:
        return await msg.answer(
            "❌ Неверный API ключ. Попробуйте ещё раз:",
            reply_markup=kb.back_btn("menu_buy")
        )

    await save_api_key(msg.from_user.id, api_key)
    await state.clear()
    await msg.answer(
        "✅ <b>API ключ сохранён!</b>",
        reply_markup=kb.buy_menu(True), parse_mode="HTML"
    )


@router.callback_query(F.data == "buy_search")
async def buy_search(cq: CallbackQuery):
    t = temp(cq.from_user.id)
    t.setdefault("filters", {})
    await cq.message.edit_text(
        texts.buy_filters_text(t["filters"]),
        reply_markup=kb.buy_filters_menu(), parse_mode="HTML"
    )


# Фильтры
@router.callback_query(F.data == "filter_premium")
async def filter_premium(cq: CallbackQuery):
    t = temp(cq.from_user.id)
    filters = t.setdefault("filters", {})
    if filters.get("premium") == 1:
        filters.pop("premium")
        await cq.answer("⭐ Premium: выключен")
    else:
        filters["premium"] = 1
        await cq.answer("⭐ Premium: включён")
    await cq.message.edit_text(
        texts.buy_filters_text(filters),
        reply_markup=kb.buy_filters_menu(), parse_mode="HTML"
    )


@router.callback_query(F.data == "filter_no_spam")
async def filter_no_spam(cq: CallbackQuery):
    t = temp(cq.from_user.id)
    filters = t.setdefault("filters", {})
    if filters.get("spamblock") == 0:
        filters.pop("spamblock")
        await cq.answer("Спамблок: фильтр снят")
    else:
        filters["spamblock"] = 0
        await cq.answer("🚫 Без спамблока: включён")
    await cq.message.edit_text(
        texts.buy_filters_text(filters),
        reply_markup=kb.buy_filters_menu(), parse_mode="HTML"
    )


@router.callback_query(F.data == "filter_price")
async def filter_price(cq: CallbackQuery, state: FSMContext):
    await state.set_state(BuyFlow.setting_price_from)
    await cq.message.edit_text(
        "💰 <b>Введите диапазон цены</b>\n\nФормат: <code>100 500</code> (от до в рублях)",
        parse_mode="HTML"
    )


@router.message(BuyFlow.setting_price_from)
async def filter_price_input(msg: Message, state: FSMContext):
    parts = msg.text.strip().split()
    if len(parts) != 2 or not all(p.isdigit() for p in parts):
        return await msg.answer("Неверный формат. Пример: <code>100 500</code>", parse_mode="HTML")
    t = temp(msg.from_user.id)
    t.setdefault("filters", {})
    t["filters"]["priceFrom"] = int(parts[0])
    t["filters"]["priceTo"] = int(parts[1])
    await state.clear()
    await msg.answer(
        texts.buy_filters_text(t["filters"]),
        reply_markup=kb.buy_filters_menu(), parse_mode="HTML"
    )


@router.callback_query(F.data == "filter_country")
async def filter_country(cq: CallbackQuery, state: FSMContext):
    await state.set_state(BuyFlow.setting_country)
    await cq.message.edit_text(
        "🌍 <b>Введите код страны</b>\n\nПримеры: <code>RU</code>, <code>UA</code>, <code>KZ</code>",
        parse_mode="HTML"
    )


@router.message(BuyFlow.setting_country)
async def filter_country_input(msg: Message, state: FSMContext):
    t = temp(msg.from_user.id)
    t.setdefault("filters", {})
    t["filters"]["country"] = msg.text.strip().upper()
    await state.clear()
    await msg.answer(
        texts.buy_filters_text(t["filters"]),
        reply_markup=kb.buy_filters_menu(), parse_mode="HTML"
    )


@router.callback_query(F.data == "filter_age")
async def filter_age(cq: CallbackQuery, state: FSMContext):
    await state.set_state(BuyFlow.setting_age_from)
    await cq.message.edit_text(
        "📅 <b>Минимальный возраст аккаунта (лет):</b>",
        parse_mode="HTML"
    )


@router.message(BuyFlow.setting_age_from)
async def filter_age_input(msg: Message, state: FSMContext):
    if not msg.text.strip().isdigit():
        return await msg.answer("Введите число")
    t = temp(msg.from_user.id)
    t.setdefault("filters", {})
    t["filters"]["ageFrom"] = int(msg.text.strip())
    await state.clear()
    await msg.answer(
        texts.buy_filters_text(t["filters"]),
        reply_markup=kb.buy_filters_menu(), parse_mode="HTML"
    )


@router.callback_query(F.data == "filter_contacts")
async def filter_contacts(cq: CallbackQuery, state: FSMContext):
    await state.set_state(BuyFlow.setting_contacts_from)
    await cq.message.edit_text("👤 <b>Минимум контактов:</b>", parse_mode="HTML")


@router.message(BuyFlow.setting_contacts_from)
async def filter_contacts_input(msg: Message, state: FSMContext):
    if not msg.text.strip().isdigit():
        return await msg.answer("Введите число")
    t = temp(msg.from_user.id)
    t.setdefault("filters", {})
    t["filters"]["contactsFrom"] = int(msg.text.strip())
    await state.clear()
    await msg.answer(
        texts.buy_filters_text(t["filters"]),
        reply_markup=kb.buy_filters_menu(), parse_mode="HTML"
    )


@router.callback_query(F.data == "buy_do_search")
async def buy_do_search(cq: CallbackQuery):
    api_key = await get_api_key(cq.from_user.id)
    if not api_key:
        return await cq.answer("Нет API ключа")

    t = temp(cq.from_user.id)
    filters = t.get("filters", {})
    page = t.get("page", 1)

    await cq.message.edit_text("🔍 Ищу аккаунты...")
    api = TronaccsAPI(api_key)
    result = await api.get_items(filters, page)

    items = result.get("items", [])
    if not items:
        return await cq.message.edit_text(
            "😔 <b>Ничего не найдено</b>\n\nПопробуйте изменить фильтры.",
            reply_markup=kb.back_btn("buy_search"), parse_mode="HTML"
        )

    t["last_items"] = items
    await cq.message.edit_text(
        f"📋 <b>Найдено аккаунтов:</b> {len(items)}",
        reply_markup=kb.buy_results_menu(items, page),
        parse_mode="HTML"
    )


@router.callback_query(F.data.startswith("buy_page_"))
async def buy_page(cq: CallbackQuery):
    page = int(cq.data.split("_")[2])
    api_key = await get_api_key(cq.from_user.id)
    t = temp(cq.from_user.id)
    t["page"] = page

    api = TronaccsAPI(api_key)
    result = await api.get_items(t.get("filters", {}), page)
    items = result.get("items", [])
    t["last_items"] = items

    await cq.message.edit_reply_markup(reply_markup=kb.buy_results_menu(items, page))


@router.callback_query(F.data.startswith("buy_item_"))
async def buy_item_detail(cq: CallbackQuery):
    item_id = int(cq.data.split("_")[2])
    api_key = await get_api_key(cq.from_user.id)
    api = TronaccsAPI(api_key)
    result = await api.get_item(item_id)

    item = result if isinstance(result, dict) and "item_id" in result else result.get("item", {})
    await cq.message.edit_text(
        texts.item_detail(item),
        reply_markup=kb.buy_item_confirm(item_id), parse_mode="HTML"
    )


@router.callback_query(F.data.startswith("buy_confirm_"))
async def buy_confirm(cq: CallbackQuery):
    item_id = int(cq.data.split("_")[2])
    api_key = await get_api_key(cq.from_user.id)
    api = TronaccsAPI(api_key)

    await cq.message.edit_text(f"⏳ Покупаю аккаунт #{item_id}...")
    result = await api.purchase_item(item_id)

    if result.get("status") is True or result.get("status") == "ok":
        await add_account(f"tronaccs_{item_id}", tronaccs_item_id=item_id)
        await cq.message.edit_text(
            f"✅ <b>Аккаунт #{item_id} куплен!</b>\n\n{result.get('result', '')}\n\n"
            "Добавлен в панель. Для активации добавьте session файл вручную.",
            reply_markup=kb.back_btn("menu_accounts"), parse_mode="HTML"
        )
    else:
        await cq.message.edit_text(
            f"❌ <b>Ошибка покупки</b>\n\n{result}",
            reply_markup=kb.back_btn("buy_do_search"), parse_mode="HTML"
        )


@router.callback_query(F.data == "buy_all")
async def buy_all(cq: CallbackQuery):
    t = temp(cq.from_user.id)
    items = t.get("last_items", [])
    if not items:
        return await cq.answer("Нет товаров")
    await cq.message.edit_text(
        f"⚠️ <b>Купить все {len(items)} аккаунтов?</b>",
        reply_markup=kb.confirm_cancel("buy_all_confirm", "buy_do_search"),
        parse_mode="HTML"
    )


@router.callback_query(F.data == "buy_all_confirm")
async def buy_all_confirm(cq: CallbackQuery):
    t = temp(cq.from_user.id)
    items = t.get("last_items", [])
    api_key = await get_api_key(cq.from_user.id)
    api = TronaccsAPI(api_key)

    msg = await cq.message.edit_text(f"⏳ Покупаю {len(items)} аккаунтов...")
    done = 0
    errors = 0

    for item in items:
        result = await api.purchase_item(item["item_id"])
        if result.get("status") is True:
            await add_account(f"tronaccs_{item['item_id']}", tronaccs_item_id=item["item_id"])
            done += 1
        else:
            errors += 1
        await asyncio.sleep(1)
        await msg.edit_text(
            f"⏳ <b>Покупка...</b>\n\n{texts.progress_bar(done + errors, len(items))}\n✅ {done} | ❌ {errors}",
            parse_mode="HTML"
        )

    await msg.edit_text(
        f"✅ <b>Массовая скупка завершена!</b>\n\nКуплено: {done}\nОшибок: {errors}",
        reply_markup=kb.back_btn("menu_accounts"), parse_mode="HTML"
    )


@router.callback_query(F.data == "buy_my_orders")
async def buy_my_orders(cq: CallbackQuery):
    api_key = await get_api_key(cq.from_user.id)
    api = TronaccsAPI(api_key)
    result = await api.get_my_orders()
    items = result.get("items", [])

    if not items:
        return await cq.message.edit_text(
            "📦 <b>Покупок нет</b>",
            reply_markup=kb.back_btn("menu_buy"), parse_mode="HTML"
        )

    lines = [f"📦 <b>Мои покупки ({len(items)})</b>\n"]
    for item in items[:15]:
        lines.append(f"• #{item['item_id']} — {item.get('price_fees', '?')} ₽ — {item.get('telegram_counrty', '?')}")

    await cq.message.edit_text(
        "\n".join(lines),
        reply_markup=kb.back_btn("menu_buy"), parse_mode="HTML"
    )


# noop для кнопки номера страницы
@router.callback_query(F.data == "noop")
async def noop(cq: CallbackQuery):
    await cq.answer()
