import asyncio
from telethon import events
from telethon.tl.functions.messages import DeleteHistoryRequest
from faust_tool.core.loader import register_command

def register(client):
    @register_command(client, "voice", r"^\.voice$", "Распознать голосовое/видео")
    async def voice_command(event):
        if event.reply_to_msg_id:
            reply_msg = await event.get_reply_message()

            if not (reply_msg.voice or reply_msg.video_note or reply_msg.video):
                await event.edit("Ответь на голосовое, видеосообщение или кружок.")
                return

            client._last_test_msg = await event.edit("Идет распознавание...")
            client._awaiting_response = True

            await client.send_message("@smartspeech_sber_bot", reply_msg)
        else:
            await event.edit("Ответь на голосовое или видеосообщение, чтобы обработать его в речь.")

    @client.on(events.NewMessage(from_users="@smartspeech_sber_bot"))
    async def catch_initial_response(event):
        if getattr(client, "_awaiting_response", False):
            if event.raw_text.strip() == "Аудиосообщение принято!":
                msg_id = event.id

                for _ in range(90):
                    latest_msg = await client.get_messages("@smartspeech_sber_bot", ids=msg_id)
                    if latest_msg.text != "Аудиосообщение принято!":
                        if hasattr(client, "_last_test_msg") and client._last_test_msg:
                            await client._last_test_msg.edit(latest_msg.text)
                            client._last_test_msg = None

                        client._awaiting_response = False

                        await client(DeleteHistoryRequest(
                            peer="@smartspeech_sber_bot",
                            max_id=0,
                            just_clear=False
                        ))
                        return

                    await asyncio.sleep(1)

    @register_command(client, "voice_detect_on", r"\.voice detect on", "Включить автообработку голосовых")
    async def voice_detect_on(event):
        if not hasattr(client, "_voice_detect"):
            client._voice_detect = {}
        client._voice_detect[event.sender_id] = True
        client._voice_busy = False
        await event.edit("Автоматическая обработка голосовых сообщений включена.")

    @register_command(client, "voice_detect_off", r"\.voice detect off", "Отключить автообработку голосовых")
    async def voice_detect_off(event):
        if hasattr(client, "_voice_detect") and client._voice_detect.get(event.sender_id):
            client._voice_detect[event.sender_id] = False
            await event.edit("Автоматическая обработка голосовых сообщений отключена.")
        else:
            await event.edit("Режим voice detect не был включён.")
