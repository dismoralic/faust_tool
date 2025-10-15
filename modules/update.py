import os
import requests
import zipfile
import subprocess
import sys
import shutil
import tempfile
from telethon import events
from telethon.tl.custom.message import Message

def register(client):
    @client.on(events.NewMessage(outgoing=True, pattern=r'^\.update$'))
    async def update_bot(event: Message):
        await event.edit("Начинаем обновление...")
        
        current_file_dir = os.path.dirname(os.path.abspath(__file__))
        bot_dir = os.path.dirname(current_file_dir)
        
        temp_files = []
        
        try:
            await event.edit("Скачиваем обновления с GitHub...")
            
            zip_url = "https://github.com/dismoralic/faust_tool/archive/refs/heads/main.zip"
            
            temp_dir = tempfile.mkdtemp(prefix="faust_update_")
            temp_files.append(temp_dir)
            
            zip_path = os.path.join(temp_dir, "update.zip")
            
            response = requests.get(zip_url, timeout=30)
            response.raise_for_status()
            
            with open(zip_path, 'wb') as f:
                f.write(response.content)
            
            if not os.path.exists(zip_path) or os.path.getsize(zip_path) == 0:
                raise Exception("Файл обновления пуст или не скачался")
            
            await event.edit("Файл скачан. Распаковываем...")
            
            extract_dir = os.path.join(temp_dir, "extracted")
            os.makedirs(extract_dir)
            
            with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                if zip_ref.testzip() is not None:
                    raise Exception("Архив поврежден")
                
                root_folder = None
                for name in zip_ref.namelist():
                    if '/' in name and not name.startswith('__MACOSX'):
                        root_folder = name.split('/')[0]
                        break
                
                if not root_folder:
                    raise Exception("Не удалось определить структуру архива")
                
                await event.edit("Извлекаем файлы...")
                
                for file_info in zip_ref.infolist():
                    if file_info.filename.startswith('__MACOSX') or file_info.filename.endswith('/'):
                        continue
                    
                    if file_info.filename.startswith(root_folder):
                        relative_path = file_info.filename[len(root_folder)+1:]
                    else:
                        relative_path = file_info.filename
                    
                    if not relative_path:
                        continue
                    
                    extract_path = os.path.join(extract_dir, relative_path)
                    
                    os.makedirs(os.path.dirname(extract_path), exist_ok=True)
                    
                    with zip_ref.open(file_info) as source, open(extract_path, 'wb') as target:
                        target.write(source.read())
            
            await event.edit("Файлы извлечены. Копируем обновления...")
            
            backup_dir = os.path.join(temp_dir, "backup")
            os.makedirs(backup_dir)
            
            exclude_items = {'__pycache__', '.git', 'temp_update', 'backup', '.vscode'}
            
            for item in os.listdir(extract_dir):
                if item in exclude_items:
                    continue
                
                src_path = os.path.join(extract_dir, item)
                dst_path = os.path.join(bot_dir, item)
                
                if os.path.exists(dst_path):
                    backup_path = os.path.join(backup_dir, item)
                    if os.path.isdir(dst_path):
                        shutil.copytree(dst_path, backup_path)
                    else:
                        shutil.copy2(dst_path, backup_path)
                
                if os.path.isdir(src_path):
                    if os.path.exists(dst_path):
                        shutil.rmtree(dst_path)
                    shutil.copytree(src_path, dst_path)
                else:
                    shutil.copy2(src_path, dst_path)
            
            await event.edit("Обновление завершено! Перезапускаем бота...")
            
            userbot_path = os.path.join(bot_dir, "userbot.py")
            
            if not os.path.exists(userbot_path):
                if os.path.exists(backup_dir):
                    for item in os.listdir(backup_dir):
                        src_path = os.path.join(backup_dir, item)
                        dst_path = os.path.join(bot_dir, item)
                        if os.path.isdir(src_path):
                            shutil.copytree(src_path, dst_path)
                        else:
                            shutil.copy2(src_path, dst_path)
                raise Exception("Основной файл userbot.py не найден после обновления")
            
            subprocess.Popen([
                sys.executable, 
                userbot_path
            ], cwd=bot_dir)
            
            await event.respond("Бот перезапускается...")
            
            for temp_file in temp_files:
                if os.path.exists(temp_file):
                    shutil.rmtree(temp_file)
            
            client.disconnect()
            return
            
        except requests.RequestException as e:
            await event.edit(f"Ошибка сети при скачивании: {e}")
        except zipfile.BadZipFile:
            await event.edit("Скачанный файл не является ZIP архивом")
        except Exception as e:
            await event.edit(f"Критическая ошибка: {e}")
            
            try:
                if 'backup_dir' in locals() and os.path.exists(backup_dir):
                    await event.edit("Восстанавливаем из бэкапа...")
                    for item in os.listdir(backup_dir):
                        src_path = os.path.join(backup_dir, item)
                        dst_path = os.path.join(bot_dir, item)
                        if os.path.isdir(src_path):
                            if os.path.exists(dst_path):
                                shutil.rmtree(dst_path)
                            shutil.copytree(src_path, dst_path)
                        else:
                            shutil.copy2(src_path, dst_path)
                    await event.edit("Восстановление завершено")
            except Exception as restore_error:
                await event.edit(f"Ошибка восстановления: {restore_error}")
            
        finally:
            for temp_file in temp_files:
                try:
                    if os.path.exists(temp_file):
                        shutil.rmtree(temp_file)
                except:
                    pass
