import os
import re
from telethon import events
from telethon.tl.custom.message import Message
from faust_tool.core.loader import _unload_module, LOADED_MODULES

def register(client):
    @client.on(events.NewMessage(pattern=r'^\.unload\b'))
    async def unload_cmd(event: Message):
        raw = event.raw_text.strip()
        parts = raw.split(maxsplit=2)

        if len(parts) < 3:
            await event.edit(
                "Неправильный синтаксис.\n\n"
                "Правильно:\n"
                "<code>.unload ftg &lt;имя модуля&gt;</code>\n"
                "<code>.unload native &lt;имя модуля&gt;</code>",
                parse_mode="html"
            )
            return

        _, mod_type, mod_name_raw = parts
        mod_type = mod_type.lower()
        if mod_type not in ("ftg", "native"):
            await event.edit(
                "Неправильный тип модуля.\nИспользуйте <code>ftg</code> или <code>native</code>.",
                parse_mode="html"
            )
            return

        mod_name = mod_name_raw.strip()
        if (mod_name.startswith('"') and mod_name.endswith('"')) or (mod_name.startswith("'") and mod_name.endswith("'")):
            mod_name = mod_name[1:-1].strip()

        def norm(s):
            return re.sub(r'[\s_\-]+', '', s or '').lower()

        candidates = [(name, info) for name, info in LOADED_MODULES.items() if info[0] == mod_type]

        found = None
        for name, info in candidates:
            _, _, file_path, display_name = (info + (None, None, None, name))[:4]
            if not display_name:
                display_name = name
            if norm(display_name) == norm(mod_name):
                found = name
                break

        matches = []
        if not found:
            for name, info in candidates:
                _, _, _, display_name = (info + (None, None, None, name))[:4]
                if not display_name:
                    display_name = name
                if norm(mod_name) in norm(display_name) or norm(display_name) in norm(mod_name):
                    matches.append(name)

            if len(matches) == 1:
                found = matches[0]
            elif len(matches) > 1:
                out = "Найдено несколько совпадений. Уточните точное имя модуля:\n\n"
                for m in matches[:30]:
                    out += f"- {m}\n"
                out += "\nИспользуйте точное имя из списка (учитывайте пробелы и регистр)."
                await event.edit(out)
                return

        if not found:
            await event.edit(
                f"Модуль <b>{mod_name}</b> не найден среди загруженных {mod_type}-модулей.",
                parse_mode="html"
            )
            return

        _, mod_obj, file_path, display_name = (LOADED_MODULES[found] + (None, None, None, found))[:4]
        if not display_name:
            display_name = found

        _unload_module(found, client)

        if file_path and os.path.exists(file_path):
            await client.send_file(
                "me",
                file_path,
                caption=f"Оригинальное имя файла: <b>{os.path.basename(file_path)}</b>\n"
                        f"Название в help: <b>{display_name}</b>",
                parse_mode="html"
            )
            os.remove(file_path)
            await event.edit(
                f"Модуль <b>{display_name}</b> выгружен и удалён, файл отправлен в избранное.",
                parse_mode="html"
            )
        else:
            await client.send_message("me", f"Модуль <b>{display_name}</b> выгружен", parse_mode="html")
            await event.edit(
                f"Модуль <b>{display_name}</b> выгружен (файл не найден, удаление пропущено).",
                parse_mode="html"
            )
