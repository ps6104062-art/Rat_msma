import os
import asyncio
from pyrogram import Client
from pyrogram.errors import (
    SessionPasswordNeeded, PhoneCodeInvalid, PhoneCodeExpired,
    FloodWait, BadRequest
)
from config import SESSIONS_DIR


def get_client(phone: str, session_file: str = None) -> Client:
    """Создаёт Pyrogram клиент для аккаунта."""
    session_name = session_file or os.path.join(SESSIONS_DIR, phone.replace("+", ""))
    return Client(
        name=session_name,
        api_id=int(os.getenv("API_ID", "2040")),
        api_hash=os.getenv("API_HASH", "b18441a1ff607e10a989891a5462e627"),
        no_updates=True,
    )


async def send_code(phone: str) -> dict:
    """Отправляет код подтверждения на номер."""
    client = get_client(phone)
    try:
        await client.connect()
        sent = await client.send_code(phone)
        return {"ok": True, "phone_code_hash": sent.phone_code_hash}
    except FloodWait as e:
        return {"ok": False, "error": f"Флуд-вейт {e.value} сек"}
    except Exception as e:
        return {"ok": False, "error": str(e)}
    finally:
        try:
            await client.disconnect()
        except:
            pass


async def sign_in(phone: str, code: str, phone_code_hash: str, password: str = None) -> dict:
    """Авторизует аккаунт по коду."""
    session_name = os.path.join(SESSIONS_DIR, phone.replace("+", ""))
    client = Client(
        name=session_name,
        api_id=int(os.getenv("API_ID", "2040")),
        api_hash=os.getenv("API_HASH", "b18441a1ff607e10a989891a5462e627"),
        no_updates=True,
    )
    try:
        await client.connect()
        try:
            user = await client.sign_in(phone, phone_code_hash, code)
        except SessionPasswordNeeded:
            if not password:
                return {"ok": False, "need_2fa": True}
            user = await client.check_password(password)
        await client.disconnect()
        return {"ok": True, "session_file": session_name, "user": user.first_name}
    except PhoneCodeInvalid:
        return {"ok": False, "error": "Неверный код"}
    except PhoneCodeExpired:
        return {"ok": False, "error": "Код истёк"}
    except Exception as e:
        return {"ok": False, "error": str(e)}


async def clear_chats(phone: str, session_file: str) -> dict:
    """Выходит из всех чатов и каналов, удаляет личку."""
    client = get_client(phone, session_file)
    cleared = 0
    errors = 0
    try:
        await client.start()
        async for dialog in client.get_dialogs():
            try:
                chat = dialog.chat
                if chat.type.name in ("GROUP", "SUPERGROUP", "CHANNEL"):
                    await client.leave_chat(chat.id)
                elif chat.type.name == "PRIVATE":
                    await client.delete_history(chat.id, revoke=True)
                cleared += 1
                await asyncio.sleep(0.3)
            except Exception:
                errors += 1
        await client.stop()
        return {"ok": True, "cleared": cleared, "errors": errors}
    except Exception as e:
        return {"ok": False, "error": str(e)}


async def clear_contacts(phone: str, session_file: str) -> dict:
    """Удаляет все контакты."""
    client = get_client(phone, session_file)
    try:
        await client.start()
        contacts = await client.get_contacts()
        if contacts:
            user_ids = [c.id for c in contacts]
            await client.delete_contacts(user_ids)
        await client.stop()
        return {"ok": True, "deleted": len(contacts)}
    except Exception as e:
        return {"ok": False, "error": str(e)}


async def kick_all_sessions(phone: str, session_file: str) -> dict:
    """Завершает все активные сессии кроме текущей."""
    client = get_client(phone, session_file)
    try:
        await client.start()
        from pyrogram.raw.functions.auth import ResetAuthorizations
        await client.invoke(ResetAuthorizations())
        await client.stop()
        return {"ok": True}
    except Exception as e:
        err = str(e)
        await client.stop() if client.is_connected else None
        if "FRESHRESETAUTHORIZATION" in err or "fresh" in err.lower():
            return {"ok": False, "error": "fresh"}
        return {"ok": False, "error": err}


async def leave_all_bots(phone: str, session_file: str) -> dict:
    """Удаляет аккаунт из всех ботов (блокирует их)."""
    client = get_client(phone, session_file)
    blocked = 0
    try:
        await client.start()
        async for dialog in client.get_dialogs():
            chat = dialog.chat
            if chat.type.name == "PRIVATE" and getattr(chat, "is_bot", False):
                try:
                    await client.block_user(chat.id)
                    blocked += 1
                    await asyncio.sleep(0.3)
                except Exception:
                    pass
        await client.stop()
        return {"ok": True, "blocked": blocked}
    except Exception as e:
        return {"ok": False, "error": str(e)}


async def set_2fa_password(phone: str, session_file: str, new_password: str) -> dict:
    """Устанавливает двухфакторный пароль."""
    client = get_client(phone, session_file)
    try:
        await client.start()
        await client.enable_cloud_password(new_password, hint="")
        await client.stop()
        return {"ok": True}
    except Exception as e:
        return {"ok": False, "error": str(e)}


async def download_session(session_file: str) -> str | None:
    """Возвращает путь к файлу сессии для скачивания."""
    path = f"{session_file}.session"
    if os.path.exists(path):
        return path
    return None


async def listen_for_codes(phone: str, session_file: str, callback, timeout: int = 300):
    """Слушает входящие коды от Telegram 'timeout' секунд и вызывает callback(text)."""
    from pyrogram import filters
    from pyrogram.handlers import MessageHandler

    client = get_client(phone, session_file)
    received = []

    async def on_message(c, message):
        text = message.text or ""
        received.append(text)
        await callback(text)

    try:
        await client.start()
        client.add_handler(MessageHandler(on_message, filters.user(777000)))
        await asyncio.sleep(timeout)
        await client.stop()
        return {"ok": True, "received": received}
    except Exception as e:
        try:
            await client.stop()
        except:
            pass
        return {"ok": False, "error": str(e)}


async def check_account(phone: str, session_file: str) -> dict:
    client = get_client(phone, session_file)
    try:
        await client.start()

        # Базовая инфо об аккаунте
        me = await client.get_me()

        # Проверка спамблока через @SpamBot
        spam_status = "✅ Чисто"
        spam_detail = ""
        try:
            await client.send_message("SpamBot", "/start")
            await asyncio.sleep(3)
            async for msg in client.get_chat_history("SpamBot", limit=1):
                text = msg.text or ""
                tl = text.lower()
                if any(w in tl for w in ["спам", "spam", "ограничен", "restrict", "limited", "заблокирован"]):
                    spam_status = "🚫 Спамблок"
                    spam_detail = text[:200]
                elif any(w in tl for w in ["free", "свободен", "нет ограничений", "no limits"]):
                    spam_status = "✅ Чисто"
                    spam_detail = ""
                else:
                    spam_status = "⚠️ Неизвестно"
                    spam_detail = text[:200]
        except Exception as e:
            spam_status = "⚠️ Не проверить"
            spam_detail = str(e)[:100]

        # Активные сессии
        sessions_count = 0
        try:
            from pyrogram.raw.functions.account import GetAuthorizations
            auths = await client.invoke(GetAuthorizations())
            sessions_count = len(auths.authorizations)
        except Exception:
            sessions_count = -1

        # Кол-во диалогов, групп, каналов
        groups = 0
        channels = 0
        bots = 0
        dialogs_total = 0
        try:
            async for dialog in client.get_dialogs():
                dialogs_total += 1
                t = dialog.chat.type.name
                if t in ("GROUP", "SUPERGROUP"):
                    groups += 1
                elif t == "CHANNEL":
                    channels += 1
                elif t == "PRIVATE" and getattr(dialog.chat, "is_bot", False):
                    bots += 1
        except Exception:
            pass

        await client.stop()

        return {
            "ok": True,
            "first_name": me.first_name or "",
            "last_name": me.last_name or "",
            "username": me.username or "нет",
            "phone": me.phone_number or phone,
            "premium": me.is_premium or False,
            "spam_status": spam_status,
            "spam_detail": spam_detail,
            "sessions": sessions_count,
            "groups": groups,
            "channels": channels,
            "bots": bots,
            "dialogs": dialogs_total,
        }

    except Exception as e:
        err = str(e)
        # Определяем тип ошибки
        if "AUTH_KEY" in err or "session" in err.lower():
            status = "💀 Мёртвая сессия"
        elif "FLOOD" in err:
            status = "⏳ Флуд-вейт"
        elif "deactivated" in err.lower():
            status = "❌ Аккаунт удалён"
        elif "banned" in err.lower():
            status = "🔨 Забанен"
        else:
            status = f"❌ Ошибка"
        return {"ok": False, "error": err, "status": status}

