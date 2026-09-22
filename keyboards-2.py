from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder
from config import ADMIN_IDS

# ═══════════════════════════════
#   ГЛАВНОЕ МЕНЮ
# ═══════════════════════════════

def main_menu(user_id: int = None) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.row(
        InlineKeyboardButton(text="👤 Аккаунты", callback_data="menu_accounts"),
        InlineKeyboardButton(text="🛒 Скупка", callback_data="menu_buy"),
    )
    kb.row(
        InlineKeyboardButton(text="⚙️ Настройки", callback_data="menu_settings"),
    )
    if user_id and user_id in ADMIN_IDS:
        kb.row(InlineKeyboardButton(text="🔐 Админ панель", callback_data="admin_panel"))
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
        # Показываем номер телефона (аккаунта) как название кнопки
        label = acc['phone'] if acc['phone'] else f"Аккаунт #{acc['id']}"
        kb.row(InlineKeyboardButton(
            text=f"📱 {label}",
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
        label = acc['phone'] if acc['phone'] else f"Аккаунт #{acc['id']}"
        kb.row(InlineKeyboardButton(
            text=f"{check} 📱 {label}",
            callback_data=f"acc_toggle_{acc['id']}"
        ))
    if selected:
        kb.row(InlineKeyboardButton(
            text=f"⚡ Действия с {len(selected)} акк.",
            callback_data="acc_mass_actions"
        ))
    kb.row(InlineKeyboardButton(text="◀️ Назад", callback_data="acc_list"))
    return kb.as_markup()

# ═══════════════════════════════
#   МЕНЮ ОДНОГО АККАУНТА (FIX: была мёртвым кодом после return)
# ═══════════════════════════════

def single_account_menu(acc_id: int) -> InlineKeyboardMarkup:
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
    kb.row(InlineKeyboardButton(text="◀️ Назад", callback_data="acc_list"))
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

# ═══════════════════════════════
#   АДМИН ПАНЕЛЬ
# ═══════════════════════════════

def admin_menu() -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.row(InlineKeyboardButton(text="📊 Статистика", callback_data="admin_stats"))
    kb.row(InlineKeyboardButton(text="👥 Пользователи", callback_data="admin_users_0"))
    kb.row(InlineKeyboardButton(text="◀️ Назад", callback_data="back_main"))
    return kb.as_markup()

def admin_users_menu(users: list, offset: int = 0) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    for u in users:
        name = u["first_name"] or u["username"] or f"ID {u['user_id']}"
        username = f" @{u['username']}" if u["username"] else ""
        kb.row(InlineKeyboardButton(
            text=f"👤 {name}{username}",
            callback_data=f"admin_user_{u['user_id']}"
        ))
    nav = []
    if offset > 0:
        nav.append(InlineKeyboardButton(text="◀️", callback_data=f"admin_users_{offset-20}"))
    if len(users) == 20:
        nav.append(InlineKeyboardButton(text="▶️", callback_data=f"admin_users_{offset+20}"))
    if nav:
        kb.row(*nav)
    kb.row(InlineKeyboardButton(text="◀️ Назад", callback_data="admin_panel"))
    return kb.as_markup()

def admin_user_detail(target_uid: int, accs: list) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    for acc in accs:
        label = acc["phone"] or f"Аккаунт #{acc['id']}"
        kb.row(InlineKeyboardButton(
            text=f"📱 {label}",
            callback_data=f"admin_acc_{acc['id']}"
        ))
    kb.row(InlineKeyboardButton(text="◀️ Назад", callback_data="admin_users_0"))
    return kb.as_markup()

def admin_acc_menu(acc_id: int, owner_uid: int) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.row(InlineKeyboardButton(text="🛡 Проверить статус", callback_data=f"adm_check_{acc_id}_{owner_uid}"))
    kb.row(
        InlineKeyboardButton(text="🗑 Очистить чаты", callback_data=f"adm_clearchats_{acc_id}_{owner_uid}"),
        InlineKeyboardButton(text="👥 Очистить контакты", callback_data=f"adm_clearcontacts_{acc_id}_{owner_uid}"),
    )
    kb.row(
        InlineKeyboardButton(text="🔒 Кикнуть сессии", callback_data=f"adm_kick_{acc_id}_{owner_uid}"),
        InlineKeyboardButton(text="🤖 Удалить из ботов", callback_data=f"adm_leavebots_{acc_id}_{owner_uid}"),
    )
    kb.row(
        InlineKeyboardButton(text="💾 Скачать сессию", callback_data=f"adm_download_{acc_id}_{owner_uid}"),
        InlineKeyboardButton(text="📲 Получить код", callback_data=f"adm_getcode_{acc_id}_{owner_uid}"),
    )
    kb.row(InlineKeyboardButton(text="◀️ Назад", callback_data=f"admin_user_{owner_uid}"))
    return kb.as_markup()

def confirm_cancel(confirm_cb: str, cancel_cb: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="✅ Да", callback_data=confirm_cb),
        InlineKeyboardButton(text="❌ Нет", callback_data=cancel_cb),
    ]])
