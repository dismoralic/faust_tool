import os
from telethon import events
from telethon.tl.custom.message import Message
from faust_tool.core import loader
import re

def pattern_to_help(pattern: str) -> str:
    pattern = pattern.lstrip("^").rstrip("$")
    pattern = pattern.replace(r"\.", ".")
    
    pattern = re.sub(r"\(\.\+\)", "<текст>", pattern)
    pattern = re.sub(r"\(\d\+\)", "<число>", pattern)
    pattern = re.sub(r"\(\*\)", "<текст?>", pattern)
    pattern = re.sub(r"\(\.\*\)", "<текст?>", pattern)
    pattern = re.sub(r"\(on\|off\)", "on|off", pattern)
    
    pattern = re.sub(r"\(\\d\+\)", "<число>", pattern)
    pattern = re.sub(r"\(\\d\*\)", "<число?>", pattern)
    pattern = re.sub(r"\(\\d\{\d+,?\d*\}\)", "<число>", pattern)
    
    pattern = re.sub(r"\(\\.\+\)", "<текст>", pattern)
    pattern = re.sub(r"\(\\.\*\)", "<текст?>", pattern)
    pattern = re.sub(r"\(\\.\{\d+,?\d*\}\)", "<текст>", pattern)
    
    pattern = re.sub(r"\(\.\+\)", "<текст>", pattern)
    pattern = re.sub(r"\(\.\*\)", "<текст?>", pattern)
    pattern = re.sub(r"\(\.\{\d+,?\d*\}\)", "<текст>", pattern)
    
    pattern = pattern.replace(r"\(", "(").replace(r"\)", ")")
    pattern = pattern.replace(r"\+", "").replace(r"\*", "")
    
    pattern = re.sub(r"\\s\+", " ", pattern)
    pattern = re.sub(r"\\s\*", " ", pattern)
    pattern = pattern.replace(r"\s", " ")
    
    pattern = pattern.replace(r"\/", "/")
    
    def optional_repl(m):
        inner = m.group(1).strip()
        inner = pattern_to_help(inner)
        if " " in inner or "|" in inner:
            return f"({inner})?"
        return f"{inner}?"

    pattern = re.sub(r"\(\?:\s*(.*?)\s*\)\?", optional_repl, pattern)
    
    pattern = re.sub(r"\s+", " ", pattern)
    pattern = pattern.strip()
    
    pattern = pattern.replace("( ", "(").replace(" )", ")")
    pattern = pattern.replace(" ?", "?")
    
    return pattern

def register(client):
    @client.on(events.NewMessage(outgoing=True, pattern=r'^\.help$'))
    async def help_cmd(event: Message):
        text = "faust-tool client\n\n"

        modules = loader.get_loaded_modules()

        text += "Импортированные FTG-модули:\n"
        ftg_mods = [name for name, value in modules.items() if value[0] == "ftg"]
        if ftg_mods:
            for m in ftg_mods:
                text += f"- {m}\n"
                instance = modules[m][1]
                cmds = [
                    f".{cmd_name}"
                    for cmd_name, handler in loader.LOADED_HANDLERS.items()
                    if getattr(handler, "__module__", None) == instance.__class__.__module__
                ]
                if cmds:
                    text += "    • " + " ".join(cmds) + "\n"
        else:
            text += "Нет загруженных FTG-модулей.\n"
        text += "\n"

        text += "Импортированные нативные модули:\n"
        native_mods = [name for name, value in modules.items() if value[0] == "native"]
        if native_mods:
            for m in native_mods:
                text += f"- {m}\n"
                commands = loader.REGISTERED_COMMANDS.get(m, [])
                if commands:
                    for pattern, desc in commands:
                        nice_pattern = pattern_to_help(pattern)
                        nice_pattern = nice_pattern.lstrip(".")
                        text += f"    • .{nice_pattern} — {desc or ''}\n"
        else:
            text += "Нет загруженных нативных модулей.\n"

        text += "\n.dlmod native/ftg <ссылка> / ответ на файл — загрузка нативного или FTG модуля\n\n"
        text += ".unload native/ftg <название> — выгрузка модуля\n"
        text += ".load faust/help <ответом на картинку> — загрузка своей картинки в меню\n"
        text += ".ai <запрос> запрос к ИИ.\n\n"
        text += ".faust — информация о клиенте"

        if len(text) > 4096:
            parts = []
            while len(text) > 4096:
                part = text[:4096]
                last_newline = part.rfind('\n')
                if last_newline != -1:
                    part = text[:last_newline]
                    text = text[last_newline+1:]
                else:
                    part = text[:4000]
                    text = text[4000:]
                parts.append(part)
            parts.append(text)
            
            for part in parts:
                await event.respond(part)
        else:
            await event.respond(text)


        await event.delete()


