import json
import random
import os
import sys
import asyncio
import requests
from telethon import TelegramClient, events
from telethon.sessions import StringSession
from telethon.tl.custom.message import Message
from telethon.extensions import html as html_parser
from faust_tool.core.loader import (
    load_all_ftg_modules,
    load_all_native_modules,
    load_builtin_modules,
    load_ftg_module,
    load_native_module,
)
from faust_tool.ai import state


BASE_DIR = os.path.dirname(os.path.abspath(__file__))

MODULES_DIR = os.path.join(BASE_DIR, "modules")
NATIVE_MODULES_DIR = os.path.join(BASE_DIR, "native_modules")
FTG_MODULES_DIR = os.path.join(BASE_DIR, "ftg_modules")
SESSION_DIR = os.path.join(BASE_DIR, "sessions")

os.makedirs(MODULES_DIR, exist_ok=True)
os.makedirs(NATIVE_MODULES_DIR, exist_ok=True)
os.makedirs(FTG_MODULES_DIR, exist_ok=True)
os.makedirs(SESSION_DIR, exist_ok=True)

SESSION_FILE = os.path.join(SESSION_DIR, "faust.session")

with open(os.path.join(BASE_DIR, "config.json"), encoding="utf-8") as f:
    cfg = json.load(f)

DEVICE_MODELS = [
    "Samsung Galaxy S21",
    "Samsung Galaxy S22 Ultra",
    "Samsung Galaxy A52",
    "Xiaomi Redmi Note 10 Pro",
    "Xiaomi Redmi Note 12",
    "Huawei P30 Pro",
    "Huawei Mate 40 Pro",
    "Google Pixel 6 Pro",
    "OnePlus 9 Pro",
    "Realme GT Neo 3",
]
device_model = random.choice(DEVICE_MODELS)

if os.path.exists(SESSION_FILE):
    with open(SESSION_FILE, 'r', encoding='utf-8') as f:
        session_str = f.read().strip()
    session = StringSession(session_str)
else:
    session = StringSession()


client = TelegramClient(
    session,
    cfg["API_ID"],
    cfg["API_HASH"],
    device_model=device_model,
    system_version="Android 13",
    app_version="9.6.4 (36609)",
    lang_code="en",
    system_lang_code="en-US"
)

_old_edit = Message.edit
async def edit_html(self, text=None, **kwargs):
    if "parse_mode" not in kwargs:
        kwargs["parse_mode"] = "html"
    return await _old_edit(self, text, **kwargs)
Message.edit = edit_html

@client.on(events.NewMessage(pattern=r"^\.dlmod(?:\s+(native))?(?:\s+(.+))?$"))
async def dlmod_cmd(event: Message):
    args = event.pattern_match.group(2)
    native_flag = event.pattern_match.group(1) is not None

    folder = NATIVE_MODULES_DIR if native_flag else FTG_MODULES_DIR

    if event.is_reply and not args:
        reply = await event.get_reply_message()
        if not reply or not reply.file:
            return await event.edit("Реплей должен быть на файл .py")

        filename = reply.file.name or "module.py"
        if not filename.endswith(".py"):
            filename += ".py"

        save_path = os.path.join(folder, filename)
        await reply.download_media(file=save_path)

    elif args:
        url = args.strip()
        filename = url.split("/")[-1]
        if not filename.endswith(".py"):
            filename += ".py"
        save_path = os.path.join(folder, filename)

        try:
            r = requests.get(url, timeout=15)
            if "text/html" in r.headers.get("Content-Type", ""):
                return await event.edit("Ссылка ведёт не на .py файл.")
            with open(save_path, "wb") as f:
                f.write(r.content)
        except Exception as e:
            return await event.edit(f"Ошибка загрузки файла: {e}")

    else:
        return await event.edit("Укажи ссылку или ответь на файл .py")

    module_name = os.path.splitext(os.path.basename(save_path))[0]
    if module_name in sys.modules:
        del sys.modules[module_name]

    try:
        if native_flag:
            load_native_module(save_path, client)
            await event.edit(f"Нативный модуль `{filename}` установлен и перезагружен.")
        else:
            load_ftg_module(save_path, client)
            await event.edit(f"FTG-модуль `{filename}` установлен и перезагружен.")
    except Exception as e:
        await event.edit(f"Ошибка при загрузке модуля `{filename}`:\n<code>{e}</code>")

async def main():
    await client.start()
    print("[FAUST] Юзербот запущен!")

    session_string = client.session.save()
    with open(SESSION_FILE, "w", encoding="utf-8") as f:
        f.write(session_string)
    print(f"[FAUST] Сессия сохранена в {SESSION_FILE}")

    try:
        me = await client.get_me()
        state.set_account_user_id(me.id)
        print(f"[FAUST] ID аккаунта установлен: {me.id}")
    except Exception as e:
        print(f"[FAUST] Ошибка получения аккаунта: {e}")

    load_builtin_modules(client)
    load_all_native_modules(client)
    load_all_ftg_modules(client)

    print("[FAUST] Все модули успешно загружены.")
    print("[FAUST] Ожидание событий...")

    await client.run_until_disconnected()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n[FAUST] Остановлен пользователем.")
