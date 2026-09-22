from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder

# ═══════════════════════════════
#   ГЛАВНОЕ МЕНЮ
# ═══════════════════════════════

def main_menu() -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.row(
        InlineKeyboardButton(text="👤 Аккаунты", callback_data="menu_accounts"),
        InlineKeyboardButton(text="🛒 Скупка", callback_data="menu_buy"),
    )
    kb.row(
        InlineKeyboardButton(text="⚙️ Настройки", callback_data="menu_settings"),
    )
    return kb.as_markup()

# ═══════════════════════════════
#   МЕНЮ АККАУНТОВ
# ═══════════════════════════════

def accounts_menu(accounts: list) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.row(
        InlineKeyboardButton(text="📱 Мои аккаунты", callback_data="acc_list"),
        InlineKeyboardButton(text="➕ Загрузить", callback_data="acc_add_menu"),
    )
    kb.row(InlineKeyboardButton(text="◀️ Назад", callback_data="back_main"))
    return kb.as_markup()


def acc_add_menu() -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.row(
        InlineKeyboardButton(text="📲 По коду (номер)", callback_data="acc_add"),
        InlineKeyboardButton(text="📁 Файлом (.session/.zip)", callback_data="acc_upload"),
    )
    kb.row(InlineKeyboardButton(text="◀️ Назад", callback_data="menu_accounts"))
    return kb.as_markup()

def account_list_menu(accounts: list) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    for acc in accounts:
        kb.row(InlineKeyboardButton(
            text=f"📱 {acc['phone']}",
            callback_data=f"acc_open_{acc['id']}"
        ))
    kb.row(InlineKeyboardButton(text="⚡ Массовое управление", callback_data="acc_select_all"))
    kb.row(InlineKeyboardButton(text="◀️ Назад", callback_data="menu_accounts"))
    return kb.as_markup()

def account_select_list(accounts: list, selected: list = None) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    selected = selected or []
    for acc in accounts:
        check = "✅" if acc["id"] in selected else "○"
        kb.row(InlineKeyboardButton(
            text=f"{check} 📱 {acc['phone']}",
            callback_data=f"acc_toggle_{acc['id']}"
        ))
    if selected:
        kb.row(InlineKeyboardButton(
            text=f"⚡ Действия с {len(selected)} акк.",
            callback_data="acc_mass_actions"
        ))
    kb.row(InlineKeyboardButton(text="◀️ Назад", callback_data="acc_list"))
    return kb.as_markup()
    kb = InlineKeyboardBuilder()
    kb.row(
        InlineKeyboardButton(text="🛡 Проверить статус", callback_data=f"do_check_{acc_id}"),
    )
    kb.row(
        InlineKeyboardButton(text="🗑 Очистить чаты", callback_data=f"do_clear_chats_{acc_id}"),
        InlineKeyboardButton(text="👥 Очистить контакты", callback_data=f"do_clear_contacts_{acc_id}"),
    )
    kb.row(
        InlineKeyboardButton(text="🔒 Кикнуть сессии", callback_data=f"do_kick_sessions_{acc_id}"),
        InlineKeyboardButton(text="🤖 Удалить из бота", callback_data=f"do_leave_bots_{acc_id}"),
    )
    kb.row(
        InlineKeyboardButton(text="💾 Скачать сессию", callback_data=f"do_download_{acc_id}"),
        InlineKeyboardButton(text="🔑 Поставить пароль", callback_data=f"do_set_password_{acc_id}"),
    )
    kb.row(
        InlineKeyboardButton(text="📲 Получить код", callback_data=f"do_get_code_{acc_id}"),
    )
    kb.row(
        InlineKeyboardButton(text="❌ Удалить аккаунт", callback_data=f"do_delete_acc_{acc_id}"),
    )
    kb.row(InlineKeyboardButton(text="◀️ Назад", callback_data="acc_select_one"))
    return kb.as_markup()

def mass_actions_menu(selected: list) -> InlineKeyboardMarkup:
    ids = ",".join(map(str, selected))
    kb = InlineKeyboardBuilder()
    kb.row(
        InlineKeyboardButton(text="🛡 Проверить статус", callback_data=f"mass_check|{ids}"),
    )
    kb.row(
        InlineKeyboardButton(text="🗑 Очистить чаты", callback_data=f"mass_clear_chats|{ids}"),
        InlineKeyboardButton(text="👥 Очистить контакты", callback_data=f"mass_clear_contacts|{ids}"),
    )
    kb.row(
        InlineKeyboardButton(text="🔒 Кикнуть сессии", callback_data=f"mass_kick_sessions|{ids}"),
        InlineKeyboardButton(text="🤖 Удалить из ботов", callback_data=f"mass_leave_bots|{ids}"),
    )
    kb.row(
        InlineKeyboardButton(text="💾 Скачать сессии", callback_data=f"mass_download|{ids}"),
        InlineKeyboardButton(text="🔑 Поставить пароль", callback_data=f"mass_set_password|{ids}"),
    )
    kb.row(InlineKeyboardButton(text="◀️ Назад", callback_data="acc_select_all"))
    return kb.as_markup()

# ═══════════════════════════════
#   МЕНЮ СКУПКИ
# ═══════════════════════════════

def buy_menu(has_api_key: bool) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    if not has_api_key:
        kb.row(InlineKeyboardButton(text="🔑 Добавить API ключ", callback_data="buy_set_api"))
    else:
        kb.row(InlineKeyboardButton(text="🔍 Найти аккаунты", callback_data="buy_search"))
        kb.row(
            InlineKeyboardButton(text="📦 Мои покупки", callback_data="buy_my_orders"),
            InlineKeyboardButton(text="🔑 Сменить API", callback_data="buy_set_api"),
        )
    kb.row(InlineKeyboardButton(text="◀️ Назад", callback_data="back_main"))
    return kb.as_markup()

def buy_filters_menu() -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.row(
        InlineKeyboardButton(text="💰 Цена", callback_data="filter_price"),
        InlineKeyboardButton(text="🌍 Страна", callback_data="filter_country"),
    )
    kb.row(
        InlineKeyboardButton(text="⭐ Premium", callback_data="filter_premium"),
        InlineKeyboardButton(text="🚫 Без спамблока", callback_data="filter_no_spam"),
    )
    kb.row(
        InlineKeyboardButton(text="📅 Возраст акк.", callback_data="filter_age"),
        InlineKeyboardButton(text="👤 Контакты", callback_data="filter_contacts"),
    )
    kb.row(InlineKeyboardButton(text="✅ Найти →", callback_data="buy_do_search"))
    kb.row(InlineKeyboardButton(text="◀️ Назад", callback_data="menu_buy"))
    return kb.as_markup()

def buy_results_menu(items: list, page: int = 1, total: int = 0) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    for item in items:
        price = item.get("price_fees", item.get("price", "?"))
        country = item.get("telegram_counrty", "??")
        premium = "⭐" if item.get("telegram_premium") else ""
        kb.row(InlineKeyboardButton(
            text=f"{premium}🌍{country} · {price}₽ · #{item['item_id']}",
            callback_data=f"buy_item_{item['item_id']}"
        ))

    nav = []
    if page > 1:
        nav.append(InlineKeyboardButton(text="◀️", callback_data=f"buy_page_{page-1}"))
    nav.append(InlineKeyboardButton(text=f"{page}", callback_data="noop"))
    if len(items) == 10:
        nav.append(InlineKeyboardButton(text="▶️", callback_data=f"buy_page_{page+1}"))
    if nav:
        kb.row(*nav)

    kb.row(
        InlineKeyboardButton(text="🛒 Купить все", callback_data="buy_all"),
        InlineKeyboardButton(text="◀️ Назад", callback_data="buy_search"),
    )
    return kb.as_markup()

def buy_item_confirm(item_id: int) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.row(
        InlineKeyboardButton(text="✅ Купить", callback_data=f"buy_confirm_{item_id}"),
        InlineKeyboardButton(text="❌ Отмена", callback_data="buy_do_search"),
    )
    return kb.as_markup()

# ═══════════════════════════════
#   НАСТРОЙКИ
# ═══════════════════════════════

def settings_menu() -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.row(InlineKeyboardButton(text="🔑 API ключ tronaccs", callback_data="settings_api"))
    kb.row(InlineKeyboardButton(text="◀️ Назад", callback_data="back_main"))
    return kb.as_markup()

# ═══════════════════════════════
#   УНИВЕРСАЛЬНЫЕ
# ═══════════════════════════════

def back_btn(cb: str = "back_main") -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="◀️ Назад", callback_data=cb)]
    ])

def confirm_cancel(confirm_cb: str, cancel_cb: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="✅ Да", callback_data=confirm_cb),
        InlineKeyboardButton(text="❌ Нет", callback_data=cancel_cb),
    ]])
