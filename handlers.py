import os
import asyncio
import shutil
from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery, FSInputFile, Document
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext

import keyboards as kb
import texts
from states import AddAccount, SetPassword, BuyFlow, MassPassword, UploadSession
from config import ADMIN_IDS
from database import (
    init_db, add_account, get_accounts, get_account, delete_account,
    save_api_key, get_api_key, update_session,
    register_user, get_stats, get_all_users, get_accounts_by_user, get_account_admin
)
from account_manager import (
    send_code, sign_in, clear_chats, clear_contacts,
    kick_all_sessions, leave_all_bots, set_2fa_password, download_session,
    check_account, listen_for_codes, _get_api_id
)
from tronaccs_api import TronaccsAPI

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

# cmd_start перенесён в новый обработчик ниже (с баннером и проверкой подписки)


# ════════════════════════════════════════
#  НАВИГАЦИЯ
# ════════════════════════════════════════

@router.callback_query(F.data == "back_main")
async def back_main(cq: CallbackQuery):
    await register_user(cq.from_user.id, cq.from_user.username, cq.from_user.first_name)
    await cq.message.edit_text(texts.WELCOME, reply_markup=kb.main_menu(cq.from_user.id), parse_mode="HTML")


@router.callback_query(F.data == "menu_accounts")
async def menu_accounts(cq: CallbackQuery):
    accs = await get_accounts(cq.from_user.id)
    count = len(accs)
    acc_banner_file_id = await get_bot_setting("accounts_banner_file_id")
    caption = f"📱 <b>Аккаунты</b>\n\nВсего: <b>{count}</b>"
    if acc_banner_file_id:
        try:
            await cq.message.delete()
        except Exception:
            pass
        await cq.message.answer_photo(
            photo=acc_banner_file_id,
            caption=caption,
            reply_markup=kb.accounts_menu(accs),
            parse_mode="HTML"
        )
    else:
        await cq.message.edit_text(caption, reply_markup=kb.accounts_menu(accs), parse_mode="HTML")


@router.callback_query(F.data == "acc_add_menu")
async def acc_add_menu(cq: CallbackQuery):
    await cq.message.edit_text(
        "➕ <b>Загрузить аккаунт</b>\n\nВыберите способ:",
        reply_markup=kb.acc_add_menu(), parse_mode="HTML"
    )


@router.callback_query(F.data == "acc_list")
async def acc_list(cq: CallbackQuery):
    accs = await get_accounts(cq.from_user.id)
    accs_list = [dict(a) for a in accs]
    if not accs_list:
        return await cq.message.edit_text(
            "📭 <b>Аккаунтов нет</b>\n\nЗагрузите первый аккаунт.",
            reply_markup=kb.back_btn("menu_accounts"), parse_mode="HTML"
        )
    await cq.message.edit_text(
        f"📱 <b>Мои аккаунты</b> ({len(accs_list)})",
        reply_markup=kb.account_list_menu(accs_list), parse_mode="HTML"
    )


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
    await cq.answer()
    await state.set_state(AddAccount.waiting_phone)
    await cq.message.edit_text(
        "📞 <b>Введите номер телефона</b>\n\nФормат: <code>+79001234567</code>",
        reply_markup=kb.back_btn("acc_add_menu"), parse_mode="HTML"
    )


@router.callback_query(F.data == "acc_add_cancel")
async def acc_add_cancel(cq: CallbackQuery, state: FSMContext):
    await cq.answer()
    await state.clear()
    await cq.message.edit_text(
        "❌ Добавление отменено.",
        reply_markup=kb.acc_add_menu(), parse_mode="HTML"
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
        reply_markup=kb.back_btn("acc_add_cancel"),
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

    await add_account(msg.from_user.id, data["phone"], result["session_file"])
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

    await add_account(msg.from_user.id, data["phone"], result["session_file"], password)
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
    accs = await get_accounts(cq.from_user.id)
    accs_list = [dict(a) for a in accs]
    await cq.message.edit_text(
        "📱 <b>Выберите аккаунт:</b>",
        reply_markup=kb.account_list_menu(accs_list), parse_mode="HTML"
    )


@router.callback_query(F.data == "acc_select_all")
async def acc_select_all(cq: CallbackQuery):
    accs = await get_accounts(cq.from_user.id)
    accs_list = [dict(a) for a in accs]
    selected = temp(cq.from_user.id).get("selected", [])
    await cq.message.edit_text(
        f"☑️ <b>Массовое управление</b>\nВыбрано: {len(selected)}/{len(accs_list)}",
        reply_markup=kb.account_select_list(accs_list, selected), parse_mode="HTML"
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
    accs = await get_accounts(cq.from_user.id)
    accs_list = [dict(a) for a in accs]
    await cq.message.edit_reply_markup(
        reply_markup=kb.account_select_list(accs_list, selected)
    )


@router.callback_query(F.data.startswith("acc_open_"))
async def acc_open(cq: CallbackQuery):
    acc_id = int(cq.data.split("_")[2])
    acc = await get_account(acc_id, cq.from_user.id)
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
    acc = await get_account(acc_id, cq.from_user.id)
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


@router.callback_query(F.data.startswith("do_check_"))
async def do_check(cq: CallbackQuery):
    acc_id = int(cq.data.split("_")[2])
    acc = await get_account(acc_id, cq.from_user.id)
    if not acc:
        return await cq.answer("Аккаунт не найден")

    await cq.message.edit_text(
        f"🔍 <b>Проверяю аккаунт...</b>\n\n"
        f"📞 {acc['phone']}\n"
        f"⏳ Это займёт ~10 секунд (проверка спамблока)",
        parse_mode="HTML"
    )
    result = await check_account(acc["phone"], acc["session_file"])
    await cq.message.edit_text(
        texts.account_check_text(result),
        reply_markup=kb.single_account_menu(acc_id),
        parse_mode="HTML"
    )


@router.callback_query(F.data.startswith("mass_check|"))
async def mass_check(cq: CallbackQuery):
    ids = cq.data.split("|")[1].split(",")
    total = len(ids)
    msg = await cq.message.edit_text(
        f"🔍 <b>Проверяю {total} аккаунтов...</b>\n\n{texts.progress_bar(0, total)}",
        parse_mode="HTML"
    )

    results = []
    for i, acc_id in enumerate(ids):
        acc = await get_account(int(acc_id), cq.from_user.id)
        if not acc:
            continue
        info = await check_account(acc["phone"], acc["session_file"])
        results.append((acc["phone"], info))
        await msg.edit_text(
            f"🔍 <b>Проверяю {total} аккаунтов...</b>\n\n{texts.progress_bar(i+1, total)}",
            parse_mode="HTML"
        )

    # Итоговый отчёт
    clean = sum(1 for _, r in results if r.get("ok") and "Чисто" in r.get("spam_status", ""))
    spam = sum(1 for _, r in results if r.get("ok") and "Спамблок" in r.get("spam_status", ""))
    dead = sum(1 for _, r in results if not r.get("ok"))

    summary = (
        f"🛡 <b>Результаты проверки ({total} акк.)</b>\n\n"
        f"✅ Чистых: <b>{clean}</b>\n"
        f"🚫 Спамблок: <b>{spam}</b>\n"
        f"💀 Мёртвых: <b>{dead}</b>\n\n"
        f"─────────────────\n"
    )
    for phone, info in results:
        if info.get("ok"):
            summary += f"• {phone} — {info['spam_status']}\n"
        else:
            summary += f"• {phone} — {info.get('status', '❌')}\n"

    await msg.edit_text(summary[:4096], reply_markup=kb.back_btn("menu_accounts"), parse_mode="HTML")
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
    acc = await get_account(acc_id, cq.from_user.id)
    if not acc:
        return await cq.answer("Аккаунт не найден")

    await cq.message.edit_text("⏳ <b>Кикаю сессии...</b>", parse_mode="HTML")
    result = await kick_all_sessions(acc["phone"], acc["session_file"])

    if result["ok"]:
        await cq.message.edit_text(
            "✅ <b>Все сессии кикнуты!</b>",
            reply_markup=kb.single_account_menu(acc_id), parse_mode="HTML"
        )
    elif result.get("error") == "fresh":
        await cq.message.edit_text(
            "⏳ <b>Аккаунт создан менее 24 часов назад</b>\n\nПопробуйте позже.",
            reply_markup=kb.single_account_menu(acc_id), parse_mode="HTML"
        )
    else:
        await cq.message.edit_text(
            f"❌ <b>Ошибка:</b> {result['error'][:200]}",
            reply_markup=kb.single_account_menu(acc_id), parse_mode="HTML"
        )


@router.callback_query(F.data.startswith("do_leave_bots_"))
async def do_leave_bots(cq: CallbackQuery):
    acc_id = int(cq.data.split("_")[3])
    await _run_action(cq, acc_id, "Удаление из ботов", leave_all_bots)


@router.callback_query(F.data.startswith("do_download_"))
async def do_download(cq: CallbackQuery, bot: Bot):
    acc_id = int(cq.data.split("_")[2])
    acc = await get_account(acc_id, cq.from_user.id)
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
    acc = await get_account(acc_id, msg.from_user.id)
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
async def do_get_code(cq: CallbackQuery, bot: Bot):
    acc_id = int(cq.data.split("_")[3])
    acc = await get_account(acc_id, cq.from_user.id)
    if not acc:
        return await cq.answer("Аккаунт не найден")

    user_id = cq.from_user.id
    await cq.message.edit_text(
        f"👂 <b>Слушаю коды 5 минут...</b>\n\n"
        f"📞 {acc['phone']}\n\n"
        f"Все сообщения от Telegram будут сразу пересланы тебе.",
        reply_markup=kb.back_btn(f"acc_open_{acc_id}"), parse_mode="HTML"
    )

    async def forward_code(text: str):
        await bot.send_message(
            user_id,
            f"📨 <b>Новое сообщение от Telegram:</b>\n\n<code>{text}</code>",
            parse_mode="HTML"
        )

    # Запускаем в фоне чтобы не блокировать бота
    asyncio.create_task(
        listen_for_codes(acc["phone"], acc["session_file"], forward_code, timeout=300)
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
    await delete_account(acc_id, cq.from_user.id)
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
        acc = await get_account(int(acc_id), cq.from_user.id)
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
        acc = await get_account(int(acc_id), cq.from_user.id)
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
        acc = await get_account(int(acc_id), msg.from_user.id)
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
async def buy_confirm(cq: CallbackQuery, bot: Bot):
    item_id = int(cq.data.split("_")[2])
    api_key = await get_api_key(cq.from_user.id)
    api = TronaccsAPI(api_key)

    await cq.message.edit_text(f"⏳ Покупаю аккаунт #{item_id}...")
    result = await api.purchase_item(item_id)

    # Пробуем разные варианты ответа API
    success = (
        result.get("status") is True
        or result.get("status") == "ok"
        or result.get("success") is True
        or "result" in result
        or "item" in result
    )

    if success:
        # Достаём данные купленного аккаунта
        item_data = result.get("result") or result.get("item") or result
        phone = item_data.get("telegram_phone", f"tronaccs_{item_id}") if isinstance(item_data, dict) else f"tronaccs_{item_id}"
        password = item_data.get("telegram_password", "") if isinstance(item_data, dict) else ""
        session_b64 = item_data.get("telegram_session") or item_data.get("session") if isinstance(item_data, dict) else None

        # Сохраняем session файл если пришёл
        session_path = None
        if session_b64:
            import base64
            session_path = os.path.join("sessions", f"{phone.replace('+','')}.session")
            os.makedirs("sessions", exist_ok=True)
            with open(session_path, "wb") as f:
                f.write(base64.b64decode(session_b64))

        await add_account(cq.from_user.id, phone, session_path, password, item_id)

        # Формируем сообщение с данными
        lines = [f"✅ <b>Аккаунт #{item_id} куплен!</b>\n"]
        if isinstance(item_data, dict):
            if item_data.get("telegram_phone"):
                lines.append(f"📞 Телефон: <code>{item_data['telegram_phone']}</code>")
            if password:
                lines.append(f"🔑 Пароль 2FA: <code>{password}</code>")
            if item_data.get("telegram_twofa"):
                lines.append(f"🔐 2FA код: <code>{item_data['telegram_twofa']}</code>")
            if item_data.get("telegram_full_name"):
                lines.append(f"👤 Имя: {item_data['telegram_full_name']}")

        text = "\n".join(lines)
        await cq.message.edit_text(text, reply_markup=kb.back_btn("menu_accounts"), parse_mode="HTML")

        # Отправляем session файл если есть
        if session_path and os.path.exists(session_path):
            await bot.send_document(
                cq.from_user.id,
                FSInputFile(session_path, filename=f"{phone.replace('+','')}.session"),
                caption=f"📦 Session файл для {phone}"
            )

        # Отправляем сырые данные отдельным сообщением для надёжности
        raw = str(item_data)[:3000] if item_data else str(result)[:3000]
        await bot.send_message(
            cq.from_user.id,
            f"📋 <b>Полные данные аккаунта:</b>\n<code>{raw}</code>",
            parse_mode="HTML"
        )
    else:
        await cq.message.edit_text(
            f"❌ <b>Ошибка покупки</b>\n\n<code>{result}</code>",
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

    bought_accounts = []
    for item in items:
        result = await api.purchase_item(item["item_id"])
        success = (
            result.get("status") is True
            or result.get("status") == "ok"
            or result.get("success") is True
            or "result" in result
            or "item" in result
        )
        if success:
            item_data = result.get("result") or result.get("item") or result
            phone = item_data.get("telegram_phone", f"tronaccs_{item['item_id']}") if isinstance(item_data, dict) else f"tronaccs_{item['item_id']}"
            password = item_data.get("telegram_password", "") if isinstance(item_data, dict) else ""
            session_b64 = item_data.get("telegram_session") or item_data.get("session") if isinstance(item_data, dict) else None

            session_path = None
            if session_b64:
                import base64
                session_path = os.path.join("sessions", f"{phone.replace('+','')}.session")
                os.makedirs("sessions", exist_ok=True)
                with open(session_path, "wb") as f:
                    f.write(base64.b64decode(session_b64))

            await add_account(cq.from_user.id, phone, session_path, password, item["item_id"])
            bought_accounts.append({"phone": phone, "password": password, "session": session_path, "data": item_data})
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

    # Отправляем данные всех купленных аккаунтов
    for acc in bought_accounts:
        lines = [f"📱 <b>{acc['phone']}</b>"]
        if acc["password"]:
            lines.append(f"🔑 2FA: <code>{acc['password']}</code>")
        raw = str(acc["data"])[:1000] if isinstance(acc["data"], dict) else ""
        if raw:
            lines.append(f"\n<code>{raw}</code>")
        await cq.message.answer("\n".join(lines), parse_mode="HTML")
        if acc["session"] and os.path.exists(acc["session"]):
            await cq.message.answer_document(
                FSInputFile(acc["session"], filename=f"{acc['phone'].replace('+','')}.session")
            )
        await asyncio.sleep(0.3)


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


async def _get_phone_from_session(session_name: str) -> str:
    """Получает реальный номер телефона из session файла.
    Поддерживает Pyrogram и Telethon форматы."""

    session_path = session_name + ".session"

    # 1. Читаем SQLite напрямую (работает для Telethon и Pyrogram v1)
    try:
        import sqlite3
        if os.path.exists(session_path):
            conn = sqlite3.connect(session_path)
            cur = conn.cursor()
            # Telethon: таблица sessions, колонка phone
            try:
                cur.execute("SELECT phone FROM sessions LIMIT 1")
                row = cur.fetchone()
                if row and row[0]:
                    conn.close()
                    phone = str(row[0])
                    return phone if phone.startswith("+") else f"+{phone}"
            except Exception:
                pass
            # Pyrogram v1: таблица sessions, колонка phone_number
            try:
                cur.execute("SELECT phone_number FROM sessions LIMIT 1")
                row = cur.fetchone()
                if row and row[0]:
                    conn.close()
                    phone = str(row[0])
                    return phone if phone.startswith("+") else f"+{phone}"
            except Exception:
                pass
            conn.close()
    except Exception:
        pass

    # 2. Подключаемся через Pyrogram (онлайн запрос к Telegram)
    try:
        from pyrogram import Client
        client = Client(
            name=session_name,
            api_id=_get_api_id(),
            api_hash=os.getenv("API_HASH", "b18441a1ff607e10a989891a5462e627"),
            no_updates=True,
        )
        await client.connect()
        me = await client.get_me()
        await client.disconnect()
        if me and me.phone_number:
            phone = str(me.phone_number)
            return phone if phone.startswith("+") else f"+{phone}"
    except Exception:
        pass

    return None


# ════════════════════════════════════════
#  ЗАГРУЗКА АККАУНТА ФАЙЛОМ
# ════════════════════════════════════════

@router.callback_query(F.data == "acc_upload")
async def acc_upload(cq: CallbackQuery, state: FSMContext):
    await cq.answer()
    await state.set_state(UploadSession.waiting_file)
    await cq.message.edit_text(
        "📁 <b>Отправьте файл аккаунта</b>\n\n"
        "Поддерживаются:\n"
        "• <code>.session</code> — Pyrogram/Telethon сессия\n"
        "• <code>.zip</code> — архив с tdata (Telegram Desktop)\n"
        "• <code>.json</code> — данные аккаунта",
        reply_markup=kb.back_btn("acc_add_menu"), parse_mode="HTML"
    )


@router.message(UploadSession.waiting_file, F.document)
async def upload_session_file(msg: Message, state: FSMContext, bot: Bot):
    doc = msg.document
    fname = doc.file_name or ""
    uid = msg.from_user.id

    os.makedirs("sessions", exist_ok=True)
    tmp_path = os.path.join("sessions", f"tmp_{uid}_{fname}")

    file = await bot.get_file(doc.file_id)
    await bot.download_file(file.file_path, destination=tmp_path)

    # .session файл
    if fname.endswith(".session"):
        tmp_name = tmp_path.replace(".session", "")
        # Переименовываем временно для pyrogram (без .session в пути)
        await msg.answer("⏳ Определяю номер телефона...")
        phone = await _get_phone_from_session(tmp_name)
        if not phone:
            # Номер не определён — используем временную метку, чтобы не путать аккаунты
            import time as _time
            phone = f"unknown_{int(_time.time())}"

        session_path = os.path.join("sessions", f"{uid}_{phone.replace('+','')}.session")
        os.rename(tmp_path, session_path)
        await add_account(uid, phone, session_path)
        await state.clear()
        return await msg.answer(
            f"✅ <b>Аккаунт добавлен!</b>\n\n📞 <code>{phone}</code>",
            reply_markup=kb.back_btn("menu_accounts"), parse_mode="HTML"
        )

    # .zip — ищем .session внутри, потом tdata
    elif fname.endswith(".zip"):
        import zipfile
        try:
            with zipfile.ZipFile(tmp_path, "r") as z:
                names = z.namelist()
                session_inside = [n for n in names if n.endswith(".session")]

                if session_inside:
                    session_name = session_inside[0]
                    base = os.path.basename(session_name).replace(".session", "")
                    tmp_session = os.path.join("sessions", f"tmp_{uid}_{base}")
                    # Сохраняем без расширения для pyrogram
                    with z.open(session_name) as src, open(tmp_session + ".session", "wb") as dst:
                        dst.write(src.read())
                    os.remove(tmp_path)

                    await msg.answer("⏳ Определяю номер телефона...")
                    phone = await _get_phone_from_session(tmp_session)
                    if not phone:
                        import time as _time
                        phone = f"unknown_{int(_time.time())}"

                    final_path = os.path.join("sessions", f"{uid}_{phone.replace('+','')}.session")
                    os.rename(tmp_session + ".session", final_path)
                    await add_account(uid, phone, final_path)
                    await state.clear()
                    return await msg.answer(
                        f"✅ <b>Аккаунт добавлен!</b>\n\n📞 <code>{phone}</code>",
                        reply_markup=kb.back_btn("menu_accounts"), parse_mode="HTML"
                    )

                # Нет .session — пробуем tdata
                extract_dir = os.path.join("sessions", f"tdata_{uid}")
                os.makedirs(extract_dir, exist_ok=True)
                z.extractall(extract_dir)
            os.remove(tmp_path)

        except Exception as e:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)
            await state.clear()
            return await msg.answer(
                f"❌ <b>Ошибка распаковки ZIP:</b> {e}",
                reply_markup=kb.back_btn("menu_accounts"), parse_mode="HTML"
            )

        # Конвертируем tdata → session через opentele
        await msg.answer("⏳ Конвертирую tdata → session...")
        try:
            from opentele.td import TDesktop
            from opentele.api import UseCurrentSession

            tdata_path = extract_dir
            for root, dirs, files in os.walk(extract_dir):
                if "key_datas" in files or any(f.startswith("D") and len(f) == 17 for f in files):
                    tdata_path = root
                    break

            tdesk = TDesktop(tdata_path)
            session_path = os.path.join("sessions", f"{uid}_tdata")
            client = await tdesk.ToTelethon(
                session=session_path,
                flag=UseCurrentSession,
                api_id=_get_api_id(),
                api_hash=os.getenv("API_HASH", "b18441a1ff607e10a989891a5462e627"),
            )
            await client.connect()
            me = await client.get_me()
            phone = me.phone or f"tdata_{uid}"
            await client.disconnect()

            final_path = os.path.join("sessions", f"{uid}_{phone}.session")
            raw = session_path + ".session"
            if os.path.exists(raw):
                os.rename(raw, final_path)
            else:
                os.rename(session_path, final_path)

            await add_account(uid, f"+{phone}", final_path)
            await state.clear()
            import shutil
            shutil.rmtree(extract_dir, ignore_errors=True)
            return await msg.answer(
                f"✅ <b>tdata конвертирована!</b>\n\n📞 +{phone}",
                reply_markup=kb.back_btn("menu_accounts"), parse_mode="HTML"
            )

        except ImportError:
            await add_account(uid, f"tdata_{uid}", extract_dir)
            await state.clear()
            return await msg.answer(
                "⚠️ <b>tdata сохранена, но не сконвертирована</b>\n\n"
                "Нужна библиотека <code>opentele</code> в requirements.txt",
                reply_markup=kb.back_btn("menu_accounts"), parse_mode="HTML"
            )
        except Exception as e:
            await state.clear()
            return await msg.answer(
                f"❌ <b>Ошибка конвертации tdata:</b>\n<code>{str(e)[:300]}</code>",
                reply_markup=kb.back_btn("menu_accounts"), parse_mode="HTML"
            )

    # .json — сохраняем данные
    elif fname.endswith(".json"):
        import json
        try:
            with open(tmp_path, "r") as f:
                data = json.load(f)
            phone = data.get("phone", data.get("id", f"json_{uid}"))
            await add_account(uid, str(phone), tmp_path)
            await state.clear()
            return await msg.answer(
                f"✅ <b>JSON аккаунт добавлен!</b>\n\n📞 {phone}",
                reply_markup=kb.back_btn("menu_accounts"), parse_mode="HTML"
            )
        except Exception as e:
            os.remove(tmp_path)
            await state.clear()
            return await msg.answer(
                f"❌ Ошибка чтения JSON: {e}",
                reply_markup=kb.back_btn("menu_accounts"), parse_mode="HTML"
            )

    else:
        os.remove(tmp_path)
        await msg.answer(
            "❌ <b>Неподдерживаемый формат</b>\n\nОтправьте <code>.session</code>, <code>.zip</code> (tdata) или <code>.json</code>",
            parse_mode="HTML"
        )


@router.message(UploadSession.waiting_file)
async def upload_no_file(msg: Message):
    await msg.answer("❌ Отправьте файл, не текст")


# noop для кнопки номера страницы
@router.callback_query(F.data == "noop")
async def noop(cq: CallbackQuery):
    await cq.answer()


# ════════════════════════════════════════
#  АДМИН ПАНЕЛЬ
# ════════════════════════════════════════

def is_admin(user_id: int) -> bool:
    return user_id in ADMIN_IDS


@router.callback_query(F.data == "admin_panel")
async def admin_panel(cq: CallbackQuery):
    if not is_admin(cq.from_user.id):
        return await cq.answer("⛔ Нет доступа", show_alert=True)
    await cq.message.edit_text(
        "🔐 <b>Админ панель</b>\n\nВыберите раздел:",
        reply_markup=kb.admin_menu(), parse_mode="HTML"
    )


@router.callback_query(F.data == "admin_stats")
async def admin_stats(cq: CallbackQuery):
    if not is_admin(cq.from_user.id):
        return await cq.answer("⛔ Нет доступа", show_alert=True)
    s = await get_stats()
    text = (
        "📊 <b>Статистика бота</b>\n\n"
        f"👥 Всего пользователей: <b>{s['total']}</b>\n"
        f"📅 Активны за 24ч: <b>{s['daily']}</b>\n"
        f"📆 Активны за 7 дней: <b>{s['weekly']}</b>\n"
        f"📱 Всего аккаунтов: <b>{s['accounts']}</b>\n"
        f"💎 Платящих: <b>0</b> (скоро)"
    )
    await cq.message.edit_text(text, reply_markup=kb.back_btn("admin_panel"), parse_mode="HTML")


@router.callback_query(F.data.startswith("admin_users_"))
async def admin_users(cq: CallbackQuery):
    if not is_admin(cq.from_user.id):
        return await cq.answer("⛔ Нет доступа", show_alert=True)
    offset = int(cq.data.split("_")[2])
    users = await get_all_users(limit=20, offset=offset)
    users_list = [dict(u) for u in users]
    if not users_list:
        return await cq.message.edit_text(
            "👥 Пользователей нет", reply_markup=kb.back_btn("admin_panel"), parse_mode="HTML"
        )
    await cq.message.edit_text(
        f"👥 <b>Пользователи</b> (с {offset+1}):",
        reply_markup=kb.admin_users_menu(users_list, offset), parse_mode="HTML"
    )


# admin_user_detail перенесён в новый обработчик ниже


@router.callback_query(F.data.startswith("admin_acc_"))
async def admin_acc_open(cq: CallbackQuery):
    if not is_admin(cq.from_user.id):
        return await cq.answer("⛔ Нет доступа", show_alert=True)
    acc_id = int(cq.data.split("_")[2])
    acc = await get_account_admin(acc_id)
    if not acc:
        return await cq.answer("Аккаунт не найден", show_alert=True)
    acc = dict(acc)
    text = (
        f"📱 <b>Аккаунт #{acc_id}</b>\n"
        f"📞 {acc['phone']}\n"
        f"👤 Владелец: <code>{acc['user_id']}</code>\n"
        f"🕒 Добавлен: {acc['added_at']}"
    )
    await cq.message.edit_text(
        text, reply_markup=kb.admin_acc_menu(acc_id, acc["user_id"]), parse_mode="HTML"
    )


# ─── Действия с аккаунтом от имени админа ───

async def _adm_get_acc(cq: CallbackQuery, parts: list):
    """Вспомогательная: проверяет права, возвращает (acc_id, owner_uid, acc)."""
    if not is_admin(cq.from_user.id):
        await cq.answer("⛔ Нет доступа", show_alert=True)
        return None, None, None
    acc_id, owner_uid = int(parts[-2]), int(parts[-1])
    acc = await get_account_admin(acc_id)
    if not acc:
        await cq.answer("Аккаунт не найден", show_alert=True)
        return None, None, None
    return acc_id, owner_uid, dict(acc)


@router.callback_query(F.data.startswith("adm_check_"))
async def adm_check(cq: CallbackQuery):
    parts = cq.data.split("_")
    acc_id, owner_uid, acc = await _adm_get_acc(cq, parts)
    if not acc:
        return
    await cq.answer("⏳ Проверяю...")
    result = await check_account(acc["phone"], acc["session_file"])
    status = "✅ Активен" if result.get("ok") else f"❌ {result.get('error', 'Ошибка')}"
    await cq.message.edit_text(
        f"📱 <b>Аккаунт #{acc_id}</b>\n\n🛡 Статус: {status}",
        reply_markup=kb.admin_acc_menu(acc_id, owner_uid), parse_mode="HTML"
    )


@router.callback_query(F.data.startswith("adm_clearchats_"))
async def adm_clearchats(cq: CallbackQuery):
    parts = cq.data.split("_")
    acc_id, owner_uid, acc = await _adm_get_acc(cq, parts)
    if not acc:
        return
    await cq.answer("⏳")
    result = await clear_chats(acc["phone"], acc["session_file"])
    txt = "✅ Чаты очищены" if result.get("ok") else f"❌ {result.get('error')}"
    await cq.message.edit_text(txt, reply_markup=kb.admin_acc_menu(acc_id, owner_uid), parse_mode="HTML")


@router.callback_query(F.data.startswith("adm_clearcontacts_"))
async def adm_clearcontacts(cq: CallbackQuery):
    parts = cq.data.split("_")
    acc_id, owner_uid, acc = await _adm_get_acc(cq, parts)
    if not acc:
        return
    await cq.answer("⏳")
    result = await clear_contacts(acc["phone"], acc["session_file"])
    txt = "✅ Контакты очищены" if result.get("ok") else f"❌ {result.get('error')}"
    await cq.message.edit_text(txt, reply_markup=kb.admin_acc_menu(acc_id, owner_uid), parse_mode="HTML")


@router.callback_query(F.data.startswith("adm_kick_"))
async def adm_kick(cq: CallbackQuery):
    parts = cq.data.split("_")
    acc_id, owner_uid, acc = await _adm_get_acc(cq, parts)
    if not acc:
        return
    await cq.answer("⏳")
    result = await kick_all_sessions(acc["phone"], acc["session_file"])
    txt = "✅ Сессии кикнуты" if result.get("ok") else f"❌ {result.get('error')}"
    await cq.message.edit_text(txt, reply_markup=kb.admin_acc_menu(acc_id, owner_uid), parse_mode="HTML")


@router.callback_query(F.data.startswith("adm_leavebots_"))
async def adm_leavebots(cq: CallbackQuery):
    parts = cq.data.split("_")
    acc_id, owner_uid, acc = await _adm_get_acc(cq, parts)
    if not acc:
        return
    await cq.answer("⏳")
    result = await leave_all_bots(acc["phone"], acc["session_file"])
    txt = "✅ Из ботов вышел" if result.get("ok") else f"❌ {result.get('error')}"
    await cq.message.edit_text(txt, reply_markup=kb.admin_acc_menu(acc_id, owner_uid), parse_mode="HTML")


@router.callback_query(F.data.startswith("adm_download_"))
async def adm_download(cq: CallbackQuery, bot: Bot):
    parts = cq.data.split("_")
    acc_id, owner_uid, acc = await _adm_get_acc(cq, parts)
    if not acc:
        return
    await cq.answer("⏳")
    path = await download_session(acc["session_file"])
    if path:
        await bot.send_document(cq.from_user.id, FSInputFile(path))
    else:
        await cq.message.answer("❌ Файл сессии не найден")


@router.callback_query(F.data.startswith("adm_getcode_"))
async def adm_getcode(cq: CallbackQuery):
    parts = cq.data.split("_")
    acc_id, owner_uid, acc = await _adm_get_acc(cq, parts)
    if not acc:
        return
    await cq.answer("⏳ Жду код...")
    async def forward_adm_code(text: str):
        await cq.message.answer(f"📲 <b>Код получен:</b> <code>{text}</code>", parse_mode="HTML")

    result = await listen_for_codes(acc["phone"], acc["session_file"], forward_adm_code, timeout=300)
    if not result.get("ok"):
        await cq.message.edit_text(
            f"❌ {result.get('error', 'Не удалось получить код')}",
            reply_markup=kb.admin_acc_menu(acc_id, owner_uid), parse_mode="HTML"
        )


# ════════════════════════════════════════
#  ПРОВЕРКА БАНА
# ════════════════════════════════════════

from database import (
    ban_user, unban_user, is_banned as db_is_banned,
    get_user, set_bot_setting, get_bot_setting,
    add_required_channel, get_required_channels, delete_required_channel,
    get_all_accounts
)
from states import AdminMsg, AdminBanner, AdminChannel


async def check_ban(user_id: int, msg_or_cq) -> bool:
    """Возвращает True если пользователь забанен (и отвечает ему)."""
    if await db_is_banned(user_id):
        text = "🚫 Вы заблокированы в этом боте."
        if hasattr(msg_or_cq, "answer"):
            await msg_or_cq.answer(text)
        else:
            await msg_or_cq.message.answer(text)
        return True
    return False


async def check_subscriptions(user_id: int, bot: Bot) -> list:
    """Возвращает список каналов, на которые пользователь НЕ подписан."""
    channels = await get_required_channels()
    not_subscribed = []
    for ch in channels:
        try:
            member = await bot.get_chat_member(ch["channel_id"], user_id)
            if member.status in ("left", "kicked", "banned"):
                not_subscribed.append(dict(ch))
        except Exception:
            not_subscribed.append(dict(ch))
    return not_subscribed


# ════════════════════════════════════════
#  СТАРТ — с баннером и проверкой подписки
# ════════════════════════════════════════

@router.message(CommandStart())
async def cmd_start(msg: Message, bot: Bot):
    await init_db()
    await register_user(msg.from_user.id, msg.from_user.username, msg.from_user.first_name)

    if await check_ban(msg.from_user.id, msg):
        return

    # Проверка обязательных подписок
    not_sub = await check_subscriptions(msg.from_user.id, bot)
    if not_sub:
        await msg.answer(
            "📢 <b>Для использования бота необходимо подписаться на каналы:</b>",
            reply_markup=kb.subscribe_menu(not_sub), parse_mode="HTML"
        )
        return

    banner_file_id = await get_bot_setting("banner_file_id")
    banner_caption = await get_bot_setting("banner_caption") or texts.WELCOME

    if banner_file_id:
        await msg.answer_photo(
            photo=banner_file_id,
            caption=banner_caption,
            reply_markup=kb.main_menu(msg.from_user.id),
            parse_mode="HTML"
        )
    else:
        await msg.answer(texts.WELCOME, reply_markup=kb.main_menu(msg.from_user.id), parse_mode="HTML")


@router.callback_query(F.data == "check_subscribe")
async def check_subscribe_cb(cq: CallbackQuery, bot: Bot):
    not_sub = await check_subscriptions(cq.from_user.id, bot)
    if not_sub:
        await cq.answer("❌ Вы ещё не подписались на все каналы!", show_alert=True)
        return
    await cq.answer("✅ Отлично!")
    banner_file_id = await get_bot_setting("banner_file_id")
    banner_caption = await get_bot_setting("banner_caption") or texts.WELCOME
    if banner_file_id:
        await cq.message.answer_photo(
            photo=banner_file_id,
            caption=banner_caption,
            reply_markup=kb.main_menu(cq.from_user.id),
            parse_mode="HTML"
        )
    else:
        await cq.message.answer(texts.WELCOME, reply_markup=kb.main_menu(cq.from_user.id), parse_mode="HTML")


# ════════════════════════════════════════
#  АДМИН — ВСЕ АККАУНТЫ
# ════════════════════════════════════════

@router.callback_query(F.data.startswith("admin_accs_"))
async def admin_all_accs(cq: CallbackQuery):
    if not is_admin(cq.from_user.id):
        return await cq.answer("⛔ Нет доступа", show_alert=True)
    offset = int(cq.data.split("_")[2])
    accs = await get_all_accounts(limit=20, offset=offset)
    accs_list = [dict(a) for a in accs]
    if not accs_list:
        return await cq.message.edit_text(
            "📱 Аккаунтов нет", reply_markup=kb.back_btn("admin_panel"), parse_mode="HTML"
        )
    await cq.message.edit_text(
        f"📱 <b>Все аккаунты</b> (с {offset+1}):",
        reply_markup=kb.admin_all_accs_menu(accs_list, offset), parse_mode="HTML"
    )


# ════════════════════════════════════════
#  АДМИН — ПОЛЬЗОВАТЕЛИ (обновлённые)
# ════════════════════════════════════════

@router.callback_query(F.data.startswith("admin_user_") & ~F.data.startswith("admin_user_accs_"))
async def admin_user_detail_new(cq: CallbackQuery):
    if not is_admin(cq.from_user.id):
        return await cq.answer("⛔ Нет доступа", show_alert=True)
    target_uid = int(cq.data.split("_")[2])
    user = await get_user(target_uid)
    accs = await get_accounts_by_user(target_uid)
    accs_list = [dict(a) for a in accs]

    if not user:
        return await cq.answer("Пользователь не найден", show_alert=True)
    user = dict(user)

    name = user.get("first_name") or user.get("username") or str(target_uid)
    username_str = f"@{user['username']}" if user.get("username") else "—"
    banned_str = "🚫 Забанен" if user.get("is_banned") else "✅ Активен"

    text = (
        f"👤 <b>Пользователь</b>\n\n"
        f"🆔 ID: <code>{target_uid}</code>\n"
        f"👤 Имя: {name}\n"
        f"📛 Username: {username_str}\n"
        f"📱 Аккаунтов: <b>{len(accs_list)}</b>\n"
        f"Статус: {banned_str}"
    )
    await cq.message.edit_text(
        text,
        reply_markup=kb.admin_user_detail_menu(target_uid, bool(user.get("is_banned")), len(accs_list)),
        parse_mode="HTML"
    )


@router.callback_query(F.data.startswith("admin_user_accs_"))
async def admin_user_accs(cq: CallbackQuery):
    if not is_admin(cq.from_user.id):
        return await cq.answer("⛔ Нет доступа", show_alert=True)
    target_uid = int(cq.data.split("_")[3])
    accs = await get_accounts_by_user(target_uid)
    accs_list = [dict(a) for a in accs]
    await cq.message.edit_text(
        f"📱 <b>Аккаунты пользователя</b> <code>{target_uid}</code>:",
        reply_markup=kb.admin_user_accs_menu(target_uid, accs_list), parse_mode="HTML"
    )


@router.callback_query(F.data.startswith("admin_ban_"))
async def admin_ban(cq: CallbackQuery):
    if not is_admin(cq.from_user.id):
        return await cq.answer("⛔ Нет доступа", show_alert=True)
    target_uid = int(cq.data.split("_")[2])
    await ban_user(target_uid)
    await cq.answer("🚫 Пользователь забанен")
    # Обновляем карточку
    user = await get_user(target_uid)
    accs = await get_accounts_by_user(target_uid)
    if user:
        user = dict(user)
        name = user.get("first_name") or str(target_uid)
        await cq.message.edit_text(
            f"👤 <b>{name}</b>\n🆔 <code>{target_uid}</code>\nСтатус: 🚫 Забанен",
            reply_markup=kb.admin_user_detail_menu(target_uid, True, len(accs)),
            parse_mode="HTML"
        )


@router.callback_query(F.data.startswith("admin_unban_"))
async def admin_unban(cq: CallbackQuery):
    if not is_admin(cq.from_user.id):
        return await cq.answer("⛔ Нет доступа", show_alert=True)
    target_uid = int(cq.data.split("_")[2])
    await unban_user(target_uid)
    await cq.answer("✅ Пользователь разбанен")
    user = await get_user(target_uid)
    accs = await get_accounts_by_user(target_uid)
    if user:
        user = dict(user)
        name = user.get("first_name") or str(target_uid)
        await cq.message.edit_text(
            f"👤 <b>{name}</b>\n🆔 <code>{target_uid}</code>\nСтатус: ✅ Активен",
            reply_markup=kb.admin_user_detail_menu(target_uid, False, len(accs)),
            parse_mode="HTML"
        )


@router.callback_query(F.data.startswith("admin_msg_"))
async def admin_msg_start(cq: CallbackQuery, state: FSMContext):
    if not is_admin(cq.from_user.id):
        return await cq.answer("⛔ Нет доступа", show_alert=True)
    target_uid = int(cq.data.split("_")[2])
    await state.set_state(AdminMsg.waiting_text)
    await state.update_data(target_uid=target_uid)
    await cq.message.edit_text(
        f"✉️ <b>Напишите сообщение для пользователя</b> <code>{target_uid}</code>:",
        reply_markup=kb.back_btn("admin_users_0"), parse_mode="HTML"
    )


@router.message(AdminMsg.waiting_text)
async def admin_msg_send(msg: Message, state: FSMContext, bot: Bot):
    data = await state.get_data()
    target_uid = data["target_uid"]
    await state.clear()
    try:
        await bot.send_message(target_uid, f"📨 <b>Сообщение от администратора:</b>\n\n{msg.text}", parse_mode="HTML")
        await msg.answer("✅ Сообщение отправлено", reply_markup=kb.back_btn("admin_panel"))
    except Exception as e:
        await msg.answer(f"❌ Не удалось отправить: {e}", reply_markup=kb.back_btn("admin_panel"))


# ════════════════════════════════════════
#  АДМИН — БАННЕР
# ════════════════════════════════════════

# ════════════════════════════════════════
#  АДМИН — БАННЕРЫ
# ════════════════════════════════════════

@router.callback_query(F.data == "admin_banner")
async def admin_banner(cq: CallbackQuery):
    if not is_admin(cq.from_user.id):
        return await cq.answer("⛔ Нет доступа", show_alert=True)
    await cq.message.edit_text(
        "🖼 <b>Баннеры</b>\n\nВыберите, какой баннер хотите настроить:",
        reply_markup=kb.admin_banner_menu(), parse_mode="HTML"
    )


@router.callback_query(F.data == "admin_banner_main")
async def admin_banner_main(cq: CallbackQuery):
    if not is_admin(cq.from_user.id):
        return await cq.answer("⛔ Нет доступа", show_alert=True)
    banner_file_id = await get_bot_setting("banner_file_id")
    text = "🏠 <b>Баннер главного меню</b>\n\n"
    text += "✅ Установлен. Показывается при /start." if banner_file_id else "❌ Не установлен. Показывается стандартный текст."
    await cq.message.edit_text(text, reply_markup=kb.admin_banner_single_menu("main", bool(banner_file_id)), parse_mode="HTML")


@router.callback_query(F.data == "admin_banner_accounts")
async def admin_banner_accounts_view(cq: CallbackQuery):
    if not is_admin(cq.from_user.id):
        return await cq.answer("⛔ Нет доступа", show_alert=True)
    banner_file_id = await get_bot_setting("accounts_banner_file_id")
    text = "📱 <b>Баннер раздела «Аккаунты»</b>\n\n"
    text += "✅ Установлен. Показывается при входе в аккаунты." if banner_file_id else "❌ Не установлен. Показывается стандартный текст."
    await cq.message.edit_text(text, reply_markup=kb.admin_banner_single_menu("accounts", bool(banner_file_id)), parse_mode="HTML")


@router.callback_query(F.data.startswith("admin_banner_set_"))
async def admin_banner_set(cq: CallbackQuery, state: FSMContext):
    if not is_admin(cq.from_user.id):
        return await cq.answer("⛔ Нет доступа", show_alert=True)
    banner_type = cq.data.split("admin_banner_set_")[1]  # "main" or "accounts"
    await state.set_state(AdminBanner.waiting_photo)
    await state.update_data(banner_type=banner_type)
    label = "главного меню" if banner_type == "main" else "раздела «Аккаунты»"
    back_cb = f"admin_banner_{banner_type}" if banner_type == "accounts" else "admin_banner_main"
    await cq.message.edit_text(
        f"🖼 <b>Отправьте фото для баннера {label}</b>",
        reply_markup=kb.back_btn(back_cb), parse_mode="HTML"
    )


@router.message(AdminBanner.waiting_photo, F.photo)
async def admin_banner_photo(msg: Message, state: FSMContext):
    if not is_admin(msg.from_user.id):
        return
    data = await state.get_data()
    banner_type = data.get("banner_type", "main")
    file_id = msg.photo[-1].file_id
    db_key = "banner_file_id" if banner_type == "main" else "accounts_banner_file_id"
    await set_bot_setting(db_key, file_id)
    await state.clear()
    label = "главного меню" if banner_type == "main" else "раздела «Аккаунты»"
    await msg.answer(
        f"✅ <b>Баннер {label} установлен!</b>",
        reply_markup=kb.back_btn("admin_banner"), parse_mode="HTML"
    )


@router.message(AdminBanner.waiting_photo)
async def admin_banner_not_photo(msg: Message):
    await msg.answer("❌ Отправьте фото, не текст")


@router.callback_query(F.data.startswith("admin_banner_del_"))
async def admin_banner_del(cq: CallbackQuery):
    if not is_admin(cq.from_user.id):
        return await cq.answer("⛔ Нет доступа", show_alert=True)
    banner_type = cq.data.split("admin_banner_del_")[1]
    db_key = "banner_file_id" if banner_type == "main" else "accounts_banner_file_id"
    await set_bot_setting(db_key, "")
    await cq.answer("🗑 Баннер удалён")
    label = "главного меню" if banner_type == "main" else "раздела «Аккаунты»"
    await cq.message.edit_text(
        f"🖼 <b>Баннер {label}</b>\n\n❌ Не установлен.",
        reply_markup=kb.admin_banner_single_menu(banner_type, False), parse_mode="HTML"
    )


# ════════════════════════════════════════
#  АДМИН — ОБЯЗАТЕЛЬНЫЕ ПОДПИСКИ
# ════════════════════════════════════════

@router.callback_query(F.data == "admin_channels")
async def admin_channels(cq: CallbackQuery):
    if not is_admin(cq.from_user.id):
        return await cq.answer("⛔ Нет доступа", show_alert=True)
    channels = await get_required_channels()
    ch_list = [dict(c) for c in channels]
    count = len(ch_list)
    text = (
        f"📢 <b>Обязательные подписки</b>\n\n"
        f"Добавлено: {count}/5\n\n"
        "Нажмите ❌ рядом с каналом чтобы удалить его.\n"
        "Бот добавляется в канал как администратор."
    )
    await cq.message.edit_text(text, reply_markup=kb.admin_channels_menu(ch_list), parse_mode="HTML")


@router.callback_query(F.data == "admin_ch_add")
async def admin_ch_add(cq: CallbackQuery, state: FSMContext):
    if not is_admin(cq.from_user.id):
        return await cq.answer("⛔ Нет доступа", show_alert=True)
    channels = await get_required_channels()
    if len(channels) >= 5:
        return await cq.answer("❌ Максимум 5 каналов", show_alert=True)
    await state.set_state(AdminChannel.waiting_link)
    await cq.message.edit_text(
        "📢 <b>Добавление канала/группы</b>\n\n"
        "Отправьте ссылку на канал или группу.\n"
        "Формат: <code>https://t.me/username</code> или <code>@username</code>\n\n"
        "⚠️ Бот должен быть администратором в этом канале!",
        reply_markup=kb.back_btn("admin_channels"), parse_mode="HTML"
    )


@router.message(AdminChannel.waiting_link)
async def admin_ch_link(msg: Message, state: FSMContext, bot: Bot):
    if not is_admin(msg.from_user.id):
        return
    link = msg.text.strip()
    await state.clear()

    # Определяем channel_id из ссылки
    if link.startswith("@"):
        channel_id = link
    elif "t.me/" in link:
        username = link.split("t.me/")[-1].split("/")[0].split("?")[0]
        channel_id = f"@{username}"
    else:
        return await msg.answer("❌ Неверный формат ссылки. Пример: @channel или https://t.me/channel")

    # Проверяем что бот есть в канале
    try:
        chat = await bot.get_chat(channel_id)
        title = chat.title or channel_id
        url = f"https://t.me/{chat.username}" if chat.username else link
        await add_required_channel(channel_id, url, title)
        await msg.answer(
            f"✅ <b>Канал добавлен!</b>\n\n📢 {title}",
            reply_markup=kb.back_btn("admin_channels"), parse_mode="HTML"
        )
    except Exception as e:
        await msg.answer(
            f"❌ Не удалось получить информацию о канале: {e}\n\n"
            "Убедитесь что бот добавлен в канал как администратор.",
            reply_markup=kb.back_btn("admin_channels"), parse_mode="HTML"
        )


@router.callback_query(F.data.startswith("admin_ch_del_"))
async def admin_ch_del(cq: CallbackQuery):
    if not is_admin(cq.from_user.id):
        return await cq.answer("⛔ Нет доступа", show_alert=True)
    ch_id = int(cq.data.split("_")[3])
    await delete_required_channel(ch_id)
    await cq.answer("✅ Канал удалён")
    channels = await get_required_channels()
    ch_list = [dict(c) for c in channels]
    await cq.message.edit_text(
        f"📢 <b>Обязательные подписки</b>\n\nДобавлено: {len(ch_list)}/5",
        reply_markup=kb.admin_channels_menu(ch_list), parse_mode="HTML"
    )
