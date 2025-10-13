import asyncio
from telethon import events
from googletrans import Translator, LANGUAGES
from faust_tool.core.loader import register_command

def register(client):
    translator = Translator()
    active_translations = {}

    @register_command(
        client,
        "trns_on",
        r"\.trns on (\w+)",
        "Перевод сообщений. Включить: .trns on <код>"
    )
    async def translate_on(event):
        lang_code = event.pattern_match.group(1).lower()
        if lang_code not in LANGUAGES:
            await event.edit("Неверный код языка!")
            return
        active_translations[event.sender_id] = {"mode": "direct", "lang": lang_code}
        await event.edit(f"Перевод включен на {LANGUAGES[lang_code].capitalize()}.")

    @register_command(
        client,
        "trns_list",
        r"\.trns list",
        "Список доступных языков: .trns list"
    )
    async def translate_list(event):
        lang_list = "\n".join([f"`{code}` - {name.capitalize()}" for code, name in LANGUAGES.items()])
        await event.edit(f"**Доступные языки:**\n\n{lang_list}")

    @register_command(
        client,
        "trns_off",
        r"\.trns off",
        "Выключить перевод: .trns off"
    )
    async def translate_off(event):
        if event.sender_id in active_translations:
            del active_translations[event.sender_id]
            await event.edit("Перевод отключен.")
        else:
            await event.edit("Перевод не был включен.")

    @register_command(
        client,
        "trns_detect_on",
        r"\.trns detect on(?: (\w+))?",
        "Автоматический перевод входящих: .trns detect on [код]"
    )
    async def translate_detect_on(event):
        lang_code = (event.pattern_match.group(1) or "ru").lower()
        if lang_code not in LANGUAGES:
            await event.edit("Неверный код языка!")
            return
        active_translations[event.sender_id] = {"mode": "detect", "lang": lang_code}
        await event.edit(f"Автоматический перевод входящих сообщений на {LANGUAGES[lang_code].capitalize()} включен.")

    @register_command(
        client,
        "trns_detect_off",
        r"\.trns detect off",
        "Отключить авто-перевод входящих: .trns detect off"
    )
    async def translate_detect_off(event):
        if (
            event.sender_id in active_translations
            and active_translations[event.sender_id]["mode"] == "detect"
        ):
            del active_translations[event.sender_id]
            await event.edit("Автоматический перевод входящих сообщений отключен.")
        else:
            await event.edit("Режим автодетекта не был включён.")

    @client.on(events.NewMessage)
    async def auto_translate(event):
        if (
            event.sender_id in active_translations
            and event.text
            and not event.text.startswith(".")
        ):
            mode = active_translations[event.sender_id]["mode"]
            lang = active_translations[event.sender_id]["lang"]

            if event.out and mode == "direct":
                try:
                    loop = asyncio.get_event_loop()
                    translated = await loop.run_in_executor(
                        None, lambda: translator.translate(event.text, dest=lang)
                    )
                    if translated and translated.src and translated.src != lang:
                        await event.edit(translated.text)
                except Exception as e:
                    await event.reply(f"Ошибка перевода: {e}")

            elif not event.out and mode == "detect":
                try:
                    loop = asyncio.get_event_loop()
                    translated = await loop.run_in_executor(
                        None, lambda: translator.translate(event.text, dest=lang)
                    )
                    if translated and translated.src and translated.src != lang:
                        await event.reply(translated.text)
                except Exception as e:
                    await event.reply(f"Ошибка перевода: {e}")
