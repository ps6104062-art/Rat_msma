WELCOME = """
╔══════════════════════════════╗
║   🔥  <b>ACCOUNT PANEL</b>  🔥      ║
╚══════════════════════════════╝

Профессиональное управление
Telegram-аккаунтами

Выберите раздел:
"""

ACCOUNTS_EMPTY = """
📭 <b>Аккаунтов нет</b>

Добавьте первый аккаунт через авторизацию по номеру телефона.
"""

def accounts_menu_text(count: int) -> str:
    return f"""
📱 <b>Управление аккаунтами</b>

Всего аккаунтов: <b>{count}</b>

Выберите режим работы:
"""

def account_info(acc) -> str:
    return f"""
📱 <b>Аккаунт #{acc['id']}</b>

📞 Телефон: <code>{acc['phone']}</code>
🔑 2FA: {'✅ Есть' if acc['two_fa_password'] else '❌ Нет'}
📁 Сессия: {'✅ Активна' if acc['session_file'] else '❌ Нет файла'}
📅 Добавлен: {acc['added_at']}

Выберите действие:
"""

BUY_MENU = """
🛒 <b>Скупка аккаунтов</b>
<i>tronaccs.market</i>

Покупайте аккаунты напрямую через API маркета с фильтрами по стране, возрасту, premium и другим параметрам.
"""

BUY_NO_API = """
🔑 <b>Нужен API ключ</b>

Получите его на tronaccs.market в разделе настроек профиля.
"""

def buy_filters_text(filters: dict) -> str:
    lines = ["🔍 <b>Фильтры поиска</b>\n"]
    if filters.get("priceFrom") or filters.get("priceTo"):
        lines.append(f"💰 Цена: {filters.get('priceFrom','?')} – {filters.get('priceTo','?')} ₽")
    if filters.get("country"):
        lines.append(f"🌍 Страна: {filters['country']}")
    if filters.get("premium") == 1:
        lines.append("⭐ Только Premium")
    if filters.get("spamblock") == 0:
        lines.append("🚫 Без спамблока")
    if filters.get("ageFrom"):
        lines.append(f"📅 Возраст от: {filters['ageFrom']} лет")
    if filters.get("contactsFrom"):
        lines.append(f"👤 Контактов от: {filters['contactsFrom']}")
    lines.append("\nНастройте или нажмите Найти:")
    return "\n".join(lines)

def item_detail(item: dict) -> str:
    premium = "⭐ Premium" if item.get("telegram_premium") else "Обычный"
    spam = "🚫 Есть" if item.get("telegram_spam_block") else "✅ Нет"
    twofa = "🔒 Есть" if item.get("telegram_password") else "🔓 Нет"
    return f"""
🔎 <b>Аккаунт #{item['item_id']}</b>

👤 Имя: {item.get('telegram_full_name', '—')}
🌍 Страна: {item.get('telegram_counrty', '—')}
📊 Тип: {premium}
🚫 Спамблок: {spam}
🔐 2FA: {twofa}
👥 Контакты: {item.get('telegram_contacts_count', 0)}
💬 Диалоги: {item.get('telegram_conversations_count', 0)}
📢 Каналы: {item.get('telegram_channels_count', 0)}

💰 Цена: <b>{item.get('price_fees', item.get('price'))} ₽</b>
"""

SETTINGS_MENU = """
⚙️ <b>Настройки</b>

Управление API ключами и параметрами бота.
"""

def progress_bar(done: int, total: int) -> str:
    if total == 0:
        return "░░░░░░░░░░ 0%"
    pct = int(done / total * 100)
    filled = int(done / total * 10)
    bar = "█" * filled + "░" * (10 - filled)
    return f"{bar} {pct}% ({done}/{total})"
