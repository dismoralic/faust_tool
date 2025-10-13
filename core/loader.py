import os
import sys
import importlib
import importlib.util
import subprocess
from telethon import events
from telethon.tl.custom.message import Message
from telethon.extensions import html as html_parser

REGISTERED_COMMANDS = {}

def register_command(client, module_name: str, pattern: str, desc: str = ""):

    if module_name not in REGISTERED_COMMANDS:
        REGISTERED_COMMANDS[module_name] = []
    REGISTERED_COMMANDS[module_name].append((pattern, desc))

    def decorator(func):
        return client.on(events.NewMessage(pattern=pattern))(func)

    return decorator

class FakeDB:
    def __init__(self):
        self.storage = {}

    def set(self, module, key, value):
        if module not in self.storage:
            self.storage[module] = {}
        self.storage[module][key] = value

    def get(self, module, key, default=None):
        return self.storage.get(module, {}).get(key, default)

class LoaderEnv:
    class Module:
        def __init__(self):
            self.strings = {"name": self.__class__.__name__}
            if not hasattr(LoaderEnv, "_db"):
                LoaderEnv._db = FakeDB()
            self._db = LoaderEnv._db

    @staticmethod
    def sudo(func):
        return func

sys.modules[f"{__name__.split('.')[0]}.loader"] = LoaderEnv

def _safe_import(module_path, module_name):
    try:
        return __import__(module_path, fromlist=["*"])
    except ModuleNotFoundError as e:
        pkg = e.name
        print(f"[FAUST] Не найден пакет {pkg}, установка...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", pkg])
        return __import__(module_path, fromlist=["*"])
    except Exception as e:
        print(f"[FAUST] Ошибка импорта {module_name}: {e}")
        return None

utils_mod = _safe_import(f"{__name__.split('.')[0]}.core.utils", "utils")
sys.modules[f"{__name__.split('.')[0]}.utils"] = utils_mod

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

PACKAGE_NAME = os.path.basename(ROOT).replace("-", "_")

MODULES_DIR = os.path.join(ROOT, "modules")
NATIVE_MODULES_DIR = os.path.join(ROOT, "native_modules")
FTG_MODULES_DIR = os.path.join(ROOT, "ftg_modules")

LOADED_MODULES = {}
LOADED_HANDLERS = {}

_old_edit = Message.edit
async def edit_patch(self, text=None, **kwargs):
    if "parse_mode" not in kwargs:
        kwargs["parse_mode"] = "html"
    return await _old_edit(self, text, **kwargs)
Message.edit = edit_patch

def _install_package(pkg_name):
    print(f"[FAUST] Установка пакета: {pkg_name}")
    subprocess.check_call([sys.executable, "-m", "pip", "install", pkg_name])

def _import_module_from_path(path: str):
    try:
        spec = importlib.util.spec_from_file_location(
            os.path.splitext(os.path.basename(path))[0], path
        )
        mod = importlib.util.module_from_spec(spec)
        try:
            spec.loader.exec_module(mod)
        except ModuleNotFoundError as e:
            _install_package(e.name)
            spec.loader.exec_module(mod)
        return mod
    except Exception as e:
        print(f"[FAUST] Ошибка импорта {path}: {e}")
        return None

def _import_ftg_module(name: str):
    try:
        full_name = f"{PACKAGE_NAME}.ftg_modules.{name}"
        if full_name in sys.modules:
            mod = importlib.reload(sys.modules[full_name])
        else:
            try:
                mod = importlib.import_module(full_name)
            except ModuleNotFoundError as e:
                _install_package(e.name)
                mod = importlib.import_module(full_name)
        return mod
    except Exception as e:
        print(f"[FAUST] Ошибка импорта {name}: {e}")
        return None

def _unload_module(name, client):
    if name not in LOADED_MODULES:
        return

    _, mod, *_ = LOADED_MODULES[name]
    mod_module_name = getattr(mod, "__module__", None) or getattr(mod, "__name__", None)

    to_remove = []
    for cmd, handler in list(LOADED_HANDLERS.items()):
        if handler.__module__ == mod_module_name:
            try:
                client.remove_event_handler(handler, events.NewMessage)
            except Exception:
                pass
            to_remove.append(cmd)

    for cmd in to_remove:
        LOADED_HANDLERS.pop(cmd, None)

    if mod_module_name in sys.modules:
        sys.modules.pop(mod_module_name, None)

    LOADED_MODULES.pop(name, None)

def load_ftg_module(path_or_name: str, client):
    if os.path.sep in path_or_name or path_or_name.endswith(".py"):
        file_path = os.path.abspath(path_or_name)
        name = os.path.splitext(os.path.basename(path_or_name))[0]
    else:
        file_path = os.path.abspath(os.path.join(FTG_MODULES_DIR, f"{path_or_name}.py"))
        name = path_or_name

    if not os.path.exists(file_path):
        print(f"[FAUST] FTG-модуль не найден по пути: {file_path}")
        return None

    if name in LOADED_MODULES:
        _unload_module(name, client)

    mod = _import_ftg_module(name)
    if mod is None:
        return None

    for obj in mod.__dict__.values():
        if isinstance(obj, type) and hasattr(obj, "strings") and isinstance(obj.strings, dict):
            try:
                instance = obj()
                instance._db = FakeDB()
                display_name = instance.strings.get("name", name)

                if display_name in LOADED_MODULES:
                    _unload_module(display_name, client)

                for attr in dir(instance):
                    if attr.endswith("cmd"):
                        cmd_name = attr[:-3]
                        method = getattr(instance, attr)

                        @client.on(events.NewMessage(pattern=fr"^\.{cmd_name}"))
                        async def handler(event, m=method):
                            orig_respond = event.respond
                            async def respond_patch(text, *args, **kwargs):
                                if "parse_mode" not in kwargs:
                                    kwargs["parse_mode"] = "html"
                                return await orig_respond(text, *args, **kwargs)
                            event.respond = respond_patch

                            orig_reply = event.reply
                            async def reply_patch(text, *args, **kwargs):
                                if "parse_mode" not in kwargs:
                                    kwargs["parse_mode"] = "html"
                                return await orig_reply(text, *args, **kwargs)
                            event.reply = reply_patch

                            await m(event)

                        handler.__module__ = instance.__module__
                        LOADED_HANDLERS[cmd_name] = handler

                LOADED_MODULES[display_name] = ("ftg", instance, file_path, display_name)
                return instance
            except Exception as e:
                print(f"[FAUST] Ошибка при создании экземпляра модуля {name}: {e}")
                return None

    return None

def load_all_ftg_modules(client, folder=FTG_MODULES_DIR):
    if not os.path.exists(folder):
        os.makedirs(folder)
    for file in os.listdir(folder):
        if file.endswith(".py") and not file.startswith("__"):
            load_ftg_module(os.path.splitext(file)[0], client)

def load_native_module(path: str, client):
    mod = _import_module_from_path(path)
    if mod is None:
        return None

    name = os.path.splitext(os.path.basename(path))[0]

    if name in LOADED_MODULES:
        _unload_module(name, client)

    if hasattr(mod, "register"):
        try:
            mod.register(client)
            LOADED_MODULES[name] = ("native", mod, path, name)
            return mod
        except Exception:
            return None
    else:
        return None

def load_all_native_modules(client, folder=NATIVE_MODULES_DIR):
    if not os.path.exists(folder):
        os.makedirs(folder)
    for file in os.listdir(folder):
        if file.endswith(".py") and not file.startswith("__"):
            load_native_module(os.path.join(folder, file), client)

def load_builtin_modules(client, folder=MODULES_DIR):
    if not os.path.exists(folder):
        os.makedirs(folder)
    for file in os.listdir(folder):
        if file.endswith(".py") and not file.startswith("__"):
            mod = _import_module_from_path(os.path.join(folder, file))
            if mod and hasattr(mod, "register"):
                try:
                    mod.register(client)
                except Exception:
                    pass

def load_all_modules(client):
    load_builtin_modules(client)
    load_all_native_modules(client)
    load_all_ftg_modules(client)

def get_loaded_modules():
    return LOADED_MODULES
