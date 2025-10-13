import re
import asyncio
from typing import Tuple, Union, List, Optional
from telethon import TelegramClient, types
from telethon.tl.functions.channels import LeaveChannelRequest, JoinChannelRequest, GetFullChannelRequest
from telethon.tl.functions.messages import GetFullChatRequest, CreateChatRequest, ExportChatInviteRequest
from telethon.tl.functions.contacts import BlockRequest, UnblockRequest, DeleteContactsRequest
from telethon.tl.functions.account import UpdateProfileRequest, UpdateUsernameRequest
from telethon.tl.functions.photos import UploadProfilePhotoRequest, DeletePhotosRequest
from telethon.tl.types import InputPeerEmpty, InputPhoneContact, UserStatusOnline, UserStatusOffline

_client: TelegramClient | None = None

def init(client: TelegramClient):
    global _client
    _client = client
    
    async def set_bot_as_owner():
        try:
            me = await client.get_me()
            if me and get_owner_id() is None:
                set_owner_id(me.id)
                print(f"Установлен владелец бота: {me.first_name} (ID: {me.id})")
        except Exception as e:
            print(f"Ошибка при установке владельца: {e}")
    
    client.loop.create_task(set_bot_as_owner())

async def _resolve_entity(identifier: str) -> Optional[types.TypeInputPeer]:
    if not _client:
        return None

    identifier = identifier.strip()
    
    attempts = [
        lambda: _client.get_input_entity(identifier),
        lambda: _client.get_entity(int(identifier) if identifier.isdigit() else identifier),
    ]
    
    for attempt in attempts:
        try:
            return await attempt()
        except:
            continue
    
    async for dialog in _client.iter_dialogs():
        dialog_name = dialog.name or ""
        dialog_username = getattr(dialog.entity, 'username', '')
        
        search_targets = [
            dialog_name.lower(),
            dialog_username.lower(),
            str(getattr(dialog.entity, 'id', ''))
        ]
        
        if any(identifier.lower() in target for target in search_targets if target):
            return dialog.entity
    
    return None

async def _get_entity_details(entity):
    try:
        if isinstance(entity, (types.Chat, types.Channel)):
            full_info = await _client(GetFullChannelRequest(entity))
        else:
            full_info = await _client(GetFullChatRequest(entity))
        return full_info
    except:
        return None

async def process_command(prompt: str, sender_id: Union[int, str] = None) -> Tuple[bool, str]:
    if not _client:
        return False, "Клиент не инициализирован."

    if sender_id is not None and not is_owner(sender_id):
        return True, "Отказано в доступе. Только владельцу доступны команды."

    text = prompt.strip().lower()
    original_text = prompt.strip()

    if re.search(r"(удали|стереть|убрать)\s+(диалог|чат|беседу)?\s*(?:с|из|у)?\s*(.+)", text) or \
       re.search(r"(delete|remove)\s+(chat|dialog)?\s*(.+)", text):
        match = re.search(r"(удали|стереть|убрать|delete|remove)\s+(диалог|чат|беседу|chat|dialog)?\s*(?:с|из|у)?\s*(.+)", text)
        target = match.group(3) if match else text.split()[-1]
        
        entity = await _resolve_entity(target)
        if not entity:
            return True, f"Чат '{target}' не найден."
        try:
            await _client.delete_dialog(entity)
            return True, f"Чат '{target}' успешно удалён."
        except Exception as e:
            return True, f"Ошибка удаления: {str(e)}"

    if re.search(r"(очисти|почисти|удали|стереть)\s*(все|мои)?\s*(сообщения|месседжи)?\s*(?:в|из|от)?\s*(.+)", text) or \
       re.search(r"(clear|clean)\s*(my|all)?\s*(messages)?\s*(.+)", text):
        match = re.search(r"(очисти|почисти|удали|стереть|clear|clean)\s*(все|мои|my|all)?\s*(сообщения|месседжи|messages)?\s*(?:в|из|от)?\s*(.+)", text)
        target = match.group(4) if match else text.split()[-1]
        
        entity = await _resolve_entity(target)
        if not entity:
            return True, f"Чат '{target}' не найден."
        try:
            deleted_count = 0
            async for msg in _client.iter_messages(entity, from_user="me"):
                await msg.delete()
                deleted_count += 1
                if deleted_count >= 100:
                    break
            return True, f"Удалено {deleted_count} сообщений в '{target}'."
        except Exception as e:
            return True, f"Ошибка очистки: {str(e)}"

    if re.search(r"(отпишись|покинуть|выйти|leave|unsubscribe)\s*(?:из|от|from)?\s*(канала|чата|группы|channel|chat|group)?\s*(.+)", text):
        match = re.search(r"(отпишись|покинуть|выйти|leave|unsubscribe)\s*(?:из|от|from)?\s*(канала|чата|группы|channel|chat|group)?\s*(.+)", text)
        target = match.group(3) if match else text.split()[-1]
        
        entity = await _resolve_entity(target)
        if not entity:
            return True, f"Чат '{target}' не найден."
        try:
            await _client(LeaveChannelRequest(entity))
            return True, f"Успешно отписан от '{target}'."
        except Exception as e:
            return True, f"Ошибка отписки: {str(e)}"

    if re.search(r"(подпишись|вступи|присоединись|join|subscribe)\s*(?:в|на|to)?\s*(канал|чат|группу|channel|chat|group)?\s*(.+)", text):
        match = re.search(r"(подпишись|вступи|присоединись|join|subscribe)\s*(?:в|на|to)?\s*(канал|чат|группу|channel|chat|group)?\s*(.+)", text)
        target = match.group(3) if match else text.split()[-1]
        
        try:
            entity = await _client.get_entity(target)
            await _client(JoinChannelRequest(entity))
            chat_title = getattr(entity, 'title', target)
            return True, f"Успешно подписан на '{chat_title}'."
        except Exception as e:
            return True, f"Ошибка подписки: {str(e)}"

    if re.search(r"(архив|архивируй|разархив|разархивируй)\s*(чат)?\s*(.+)", text):
        match = re.search(r"(архив|архивируй|разархив|разархивируй)\s*(чат)?\s*(.+)", text)
        action = match.group(1) if match else ""
        target = match.group(3) if match else text.split()[-1]
        
        entity = await _resolve_entity(target)
        if not entity:
            return True, f"Чат '{target}' не найден."
        
        try:
            if action.startswith('архив'):
                await _client.archive(entity)
                return True, f"Чат '{target}' архивирован."
            else:
                await _client.unarchive(entity)
                return True, f"Чат '{target}' разархивирован."
        except Exception as e:
            return True, f"Ошибка архивации: {str(e)}"

    if re.search(r"(закрепи|прикрепи|открепи|сними)\s*(сообщение)?\s*(?:в|from)?\s*(.+)", text):
        match = re.search(r"(закрепи|прикрепи|открепи|сними)\s*(сообщение)?\s*(?:в|from)?\s*(.+)", text)
        action = match.group(1) if match else ""
        target = match.group(3) if match else text.split()[-1]
        
        entity = await _resolve_entity(target)
        if not entity:
            return True, f"Чат '{target}' не найден."
        
        try:
            if action in ['закрепи', 'прикрепи']:
                async for message in _client.iter_messages(entity, from_user="me", limit=1):
                    await message.pin()
                    return True, f"Сообщение закреплено в '{target}'."
                return True, "Не найдено сообщений для закрепления."
            else:
                await _client.unpin_message(entity)
                return True, f"Сообщение откреплено в '{target}'."
        except Exception as e:
            return True, f"Ошибка закрепления: {str(e)}"

    if re.search(r"(найди|поищи|find|search)\s*(сообщения|messages)?\s*(?:с|with)?\s*(.+)", text):
        match = re.search(r"(найди|поищи|find|search)\s*(сообщения|messages)?\s*(?:с|with)?\s*(.+)", text)
        query = match.group(3) if match else text.split()[-1]
        
        try:
            results = []
            async for dialog in _client.iter_dialogs(limit=15):
                async for message in _client.iter_messages(dialog.entity, search=query, limit=2):
                    chat_name = dialog.name or "Unknown"
                    text_preview = message.text[:40] + "..." if message.text and len(message.text) > 40 else message.text
                    results.append(f"• {chat_name}: {text_preview}")
                    if len(results) >= 8:
                        break
                if len(results) >= 8:
                    break
            
            if results:
                return True, f"Найдено по запросу '{query}':\n" + "\n".join(results)
            else:
                return True, f"По запросу '{query}' ничего не найдено."
        except Exception as e:
            return True, f"Ошибка поиска: {str(e)}"

    if re.search(r"(статус|bio|status)\s*(установи|сделай|set)?\s*(.+)", text):
        match = re.search(r"(статус|bio|status)\s*(установи|сделай|set)?\s*(.+)", text)
        bio_text = match.group(3) if match else " ".join(text.split()[1:])
        
        try:
            await _client(UpdateProfileRequest(about=bio_text))
            return True, f"Статус обновлён: {bio_text}"
        except Exception as e:
            return True, f"Ошибка обновления статуса: {str(e)}"

    if re.search(r"(имя|name)\s*(установи|смени|set|change)\s*(.+)", text):
        match = re.search(r"(имя|name)\s*(установи|смени|set|change)\s*(.+)", text)
        name_parts = match.group(3).split() if match else text.split()[1:]
        
        if len(name_parts) >= 2:
            first_name, last_name = name_parts[0], " ".join(name_parts[1:])
        else:
            first_name, last_name = name_parts[0], ""
        
        try:
            await _client(UpdateProfileRequest(first_name=first_name, last_name=last_name))
            return True, f"Имя обновлено: {first_name} {last_name}"
        except Exception as e:
            return True, f"Ошибка обновления имени: {str(e)}"

    if re.search(r"(юзернейм|username)\s*(установи|смени|set)\s*(@?\w+)", text):
        match = re.search(r"(юзернейм|username)\s*(установи|смени|set)\s*(@?)(\w+)", text)
        username = match.group(4) if match else text.split()[-1].lstrip('@')
        
        try:
            await _client(UpdateUsernameRequest(username))
            return True, f"Юзернейм обновлён: @{username}"
        except Exception as e:
            return True, f"Ошибка обновления юзернейма: {str(e)}"

    if re.search(r"(инфо|информация|info)\s*(о|about|про)?\s*(.+)", text):
        match = re.search(r"(инфо|информация|info)\s*(о|about|про)?\s*(.+)", text)
        target = match.group(3) if match else text.split()[-1]
        
        entity = await _resolve_entity(target)
        if not entity:
            return True, f"Объект '{target}' не найден."
        
        try:
            full_entity = await _client.get_entity(entity)
            info_lines = [f"Информация о '{target}':"]
            
            if hasattr(full_entity, 'title'):
                info_lines.append(f"Название: {full_entity.title}")
            if hasattr(full_entity, 'username'):
                info_lines.append(f"Юзернейм: @{full_entity.username}")
            if hasattr(full_entity, 'id'):
                info_lines.append(f"ID: {full_entity.id}")
            if hasattr(full_entity, 'participants_count'):
                info_lines.append(f"Участников: {full_entity.participants_count}")
            if hasattr(full_entity, 'broadcast'):
                info_lines.append(f"Тип: {'Канал' if full_entity.broadcast else 'Группа'}")
            
            return True, "\n".join(info_lines)
        except Exception as e:
            return True, f"Ошибка получения информации: {str(e)}"

    if re.search(r"(мо[яё]|my)\s*(инфо|информация|аккаунт|info|account)", text):
        try:
            me = await _client.get_me()
            info_lines = ["👤 Информация о вашем аккаунте:"]
            
            if me.first_name:
                info_lines.append(f"Имя: {me.first_name}")
            if me.last_name:
                info_lines.append(f"Фамилия: {me.last_name}")
            if me.username:
                info_lines.append(f"Юзернейм: @{me.username}")
            info_lines.append(f"ID: {me.id}")
            info_lines.append(f"Premium: {'Да' if me.premium else 'Нет'}")
            info_lines.append(f"Бот: {'Да' if me.bot else 'Нет'}")
            
            return True, "\n".join(info_lines)
        except Exception as e:
            return True, f"Ошибка получения информации: {str(e)}"

    if re.search(r"(список|лист|диалоги|dialogs|chats)\s*(групп|каналов|всех)?", text):
        match = re.search(r"(список|лист|диалоги|dialogs|chats)\s*(групп|каналов|всех)?", text)
        filter_type = match.group(2) if match else ""
        
        try:
            dialogs = []
            async for dialog in _client.iter_dialogs(limit=25):
                if filter_type == "групп" and not dialog.is_group:
                    continue
                if filter_type == "каналов" and not dialog.is_channel:
                    continue
                
                dialog_info = f"• {dialog.name}"
                if dialog.unread_count:
                    dialog_info += f" ({dialog.unread_count} непрочитанных)"
                dialogs.append(dialog_info)
            
            if dialogs:
                title = "Последние диалоги"
                if filter_type:
                    title += f" ({filter_type})"
                return True, title + ":\n" + "\n".join(dialogs[:15])
            else:
                return True, "Диалоги не найдены."
        except Exception as e:
            return True, f"Ошибка получения списка: {str(e)}"

    if re.search(r"(заблокируй|блок|block)\s*(пользователя|user)?\s*(.+)", text):
        match = re.search(r"(заблокируй|блок|block)\s*(пользователя|user)?\s*(.+)", text)
        target = match.group(3) if match else text.split()[-1]
        
        entity = await _resolve_entity(target)
        if not entity:
            return True, f"Пользователь '{target}' не найден."
        
        try:
            await _client(BlockRequest(entity))
            return True, f"Пользователь '{target}' заблокирован."
        except Exception as e:
            return True, f"Ошибка блокировки: {str(e)}"

    if re.search(r"(разблокируй|разблок|unblock)\s*(пользователя|user|человека|чела)?\s*(.+)", text):
        match = re.search(r"(разблокируй|разблок|unblock)\s*(пользователя|user|человека|чела)?\s*(.+)", text)
        target = match.group(3) if match else text.split()[-1]
        
        entity = await _resolve_entity(target)
        if not entity:
            return True, f"Пользователь '{target}' не найден."
        
        try:
            await _client(UnblockRequest(entity))
            return True, f"Пользователь '{target}' разблокирован."
        except Exception as e:
            return True, f"Ошибка разблокировки: {str(e)}"

    if re.search(r"(прочитай|отметь)\s*(все|всё|all)\s*(как\s*)?прочитанн?ы?е?", text):
        try:
            await _client.mark_as_read()
            return True, "Все чаты отмечены как прочитанные."
        except Exception as e:
            return True, f"Ошибка: {str(e)}"

    if re.search(r"(создай|create)\s*(группу|chat)\s*(.+?)", text):
        match = re.search(r"(создай|create)\s*(группу|chat)\s*(.+)", text)
        group_name = match.group(3) if match else "Новая группа"
        
        try:
            result = await _client(CreateChatRequest([], group_name))
            return True, f"Группа '{group_name}' создана."
        except Exception as e:
            return True, f"Ошибка создания группы: {str(e)}"

    if re.search(r"(экспорт|выгрузи|export)\s*(историю|чат|history)?\s*(.+)", text):
        match = re.search(r"(экспорт|выгрузи|export)\s*(историю|чат|history)?\s*(.+)", text)
        target = match.group(3) if match else text.split()[-1]
        
        entity = await _resolve_entity(target)
        if not entity:
            return True, f"Чат '{target}' не найден."
        
        try:
            messages = []
            async for message in _client.iter_messages(entity, limit=20):
                sender = await message.get_sender()
                sender_name = getattr(sender, 'first_name', 'Unknown')
                messages.append(f"{sender_name}: {message.text}")
            
            if messages:
                preview = "\n".join(messages[:5])
                return True, f"Последние сообщения из '{target}':\n{preview}"
            else:
                return True, f"В чате '{target}' нет сообщений."
        except Exception as e:
            return True, f"Ошибка экспорта: {str(e)}"

    if re.search(r"(онлайн|статус|online)\s*(пользователя|user)?\s*(.+)", text):
        match = re.search(r"(онлайн|статус|online)\s*(пользователя|user)?\s*(.+)", text)
        target = match.group(3) if match else text.split()[-1]
        
        entity = await _resolve_entity(target)
        if not entity:
            return True, f"Пользователь '{target}' не найден."
        
        try:
            user = await _client.get_entity(entity)
            if hasattr(user, 'status'):
                if isinstance(user.status, UserStatusOnline):
                    status = "В сети"
                elif isinstance(user.status, UserStatusOffline):
                    from datetime import datetime
                    last_seen = user.status.was_online.strftime("%d.%m.%Y %H:%M")
                    status = f"Был в сети: {last_seen}"
                else:
                    status = f"Статус: {type(user.status).__name__}"
                
                return True, f"{getattr(user, 'first_name', 'User')} - {status}"
            else:
                return True, f"Не удалось получить статус пользователя."
        except Exception as e:
            return True, f"Ошибка получения статуса: {str(e)}"

    if re.search(r"(помощь|help|команды|commands)", text):
        help_text = """
**Управление чатами:**
`удали чат [название/юзернейм/ID]` - Удалить диалог
`очисти сообщения в [чат]` - Очистить ваши сообщения
`отпишись от [канал]` - Выйти из канала/группы
`подпишись на [юзернейм]` - Подписаться на канал
`архивируй [чат]` - Архивировать чат
`разархивируй [чат]` - Разархивировать чат

**Управление сообщениями:**
`закрепи в [чат]` - Закрепить сообщение
`открепи в [чат]` - Открепить сообщение
`найди [текст]` - Поиск сообщений

**Управление профилем:**
`статус [текст]` - Изменить био
`имя [Имя Фамилия]` - Изменить имя
`юзернейм [username]` - Изменить юзернейм

**Информация:**
`инфо о [чат/пользователь]` - Информация
`моя информация` - Информация об аккаунте
`список диалогов` - Список чатов
`онлайн [пользователь]` - Статус онлайн

**Другие команды:**
`заблокируй [пользователь]` - Блокировка
`разблокируй [пользователь]` - Разблокировка
`создай группу [название]` - Создать группу
`экспорт [чат]` - Экспорт истории

*можно использовать названия, юзернеймы (@username) или ID*
        """
        return True, help_text.strip()

    return False, ""