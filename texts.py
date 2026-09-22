WELCOME = """
✦  <b>ACCOUNT PANEL</b>  ✦

Профессиональная платформа управления
Telegram-аккаунтами

Выберите раздел:
"""

ACCOUNTS_EMPTY = """
◈  <b>Аккаунтов нет</b>

Добавьте первый аккаунт — через авторизацию
по номеру телефона или загрузку файла сессии.
"""

def accounts_menu_text(count: int) -> str:
    return f"""
◈  <b>Управление аккаунтами</b>

Всего аккаунтов: <b>{count}</b>

Выберите режим работы:
"""

def account_info(acc) -> str:
    return f"""
◈  <b>Аккаунт</b>  <code>{acc['phone']}</code>

🔑  2FA:      {'Установлен' if acc['two_fa_password'] else 'Не задан'}
📁  Сессия:   {'Активна' if acc['session_file'] else 'Отсутствует'}
📅  Добавлен: {acc['added_at']}

Выберите действие:
"""

BUY_MENU = """
◈  <b>Скупка аккаунтов</b>
<i>tronaccs.market</i>

Прямая покупка через API маркета — фильтры по стране,
возрасту, Premium-статусу и другим параметрам.
"""

BUY_NO_API = """
🔑  <b>Требуется API-ключ</b>

Получите его на <b>tronaccs.market</b> в разделе настроек профиля.
"""

def buy_filters_text(filters: dict) -> str:
    lines = ["◈  <b>Фильтры поиска</b>\n"]
    if filters.get("priceFrom") or filters.get("priceTo"):
        lines.append(f"💰  Цена:       {filters.get('priceFrom','?')} – {filters.get('priceTo','?')} ₽")
    if filters.get("country"):
        lines.append(f"🌍  Страна:     {filters['country']}")
    if filters.get("premium") == 1:
        lines.append("⭐  Только Premium")
    if filters.get("spamblock") == 0:
        lines.append("🚫  Без спамблока")
    if filters.get("ageFrom"):
        lines.append(f"📅  Возраст от: {filters['ageFrom']} лет")
    if filters.get("contactsFrom"):
        lines.append(f"👤  Контактов:  от {filters['contactsFrom']}")
    lines.append("\nНастройте параметры или нажмите Найти:")
    return "\n".join(lines)

def item_detail(item: dict) -> str:
    premium = "⭐ Premium" if item.get("telegram_premium") else "Стандартный"
    spam    = "Есть"      if item.get("telegram_spam_block") else "Отсутствует"
    twofa   = "Установлен" if item.get("telegram_password") else "Не задан"
    return f"""
◈  <b>Аккаунт #{item['item_id']}</b>

👤  Имя:         {item.get('telegram_full_name', '—')}
🌍  Страна:      {item.get('telegram_counrty', '—')}
📊  Тип:         {premium}
🚫  Спамблок:    {spam}
🔐  2FA:         {twofa}
👥  Контакты:    {item.get('telegram_contacts_count', 0)}
💬  Диалоги:     {item.get('telegram_conversations_count', 0)}
📢  Каналы:      {item.get('telegram_channels_count', 0)}

💰  Цена: <b>{item.get('price_fees', item.get('price'))} ₽</b>
"""

SETTINGS_MENU = """
◈  <b>Настройки</b>

Управление API-ключами и параметрами бота.
"""

def account_check_text(info: dict) -> str:
    if not info.get("ok"):
        return (
            f"◈  <b>Проверка аккаунта</b>\n\n"
            f"Статус: {info.get('status', '❌ Ошибка')}\n"
            f"<code>{info.get('error', '')[:300]}</code>"
        )
    premium  = "⭐ Premium" if info["premium"] else "Стандартный"
    sessions = str(info["sessions"]) if info["sessions"] >= 0 else "н/д"
    return (
        f"◈  <b>Статус аккаунта</b>\n\n"
        f"👤  {info['first_name']} {info['last_name']}\n"
        f"🔗  @{info['username']}\n"
        f"📞  <code>{info['phone']}</code>\n"
        f"💎  {premium}\n\n"
        f"─────────────────────\n"
        f"🚫  Спамблок: <b>{info['spam_status']}</b>\n"
        + (f"<i>{info['spam_detail']}</i>\n" if info.get('spam_detail') else "") +
        f"─────────────────────\n"
        f"📱  Активных сессий: <b>{sessions}</b>\n"
        f"💬  Диалогов всего:  <b>{info['dialogs']}</b>\n"
        f"👥  Групп:           <b>{info['groups']}</b>\n"
        f"📢  Каналов:         <b>{info['channels']}</b>\n"
        f"🤖  Ботов:           <b>{info['bots']}</b>"
    )
