import os
import json
import re
from ai import knowledge

BASE_DIR = os.path.dirname(__file__)
STATE_FILE = os.path.join(BASE_DIR, "state.json")

DEFAULT_STATE = {
    "owner_id": None,
    "owner_name": "",
    "auto_reply": True,
    "account_user_id": None
}

def _load_state() -> dict:
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, dict):
                    return {**DEFAULT_STATE, **data}
        except Exception:
            pass
    
    state = DEFAULT_STATE.copy()
    _save_state(state)
    return state

def _save_state(state: dict):
    try:
        with open(STATE_FILE, "w", encoding="utf-8") as f:
            json.dump(state, f, ensure_ascii=False, indent=2)
    except Exception:
        pass

def set_account_user_id(user_id: int):
    state = _load_state()
    state["account_user_id"] = int(user_id)
    _save_state(state)

def get_owner_id() -> int | None:
    state = _load_state()
    return state.get("account_user_id")

def set_owner_id(owner_id: int):
    state = _load_state()
    state["account_user_id"] = int(owner_id)
    _save_state(state)

def get_owner_name() -> str:
    return _load_state().get("owner_name", "")

def is_auto_reply() -> bool:
    return _load_state().get("auto_reply", True)

def set_owner_name(name: str):
    state = _load_state()
    state["owner_name"] = name
    _save_state(state)

def set_auto_reply(flag: bool):
    state = _load_state()
    state["auto_reply"] = bool(flag)
    _save_state(state)

def is_owner(user_id: int | str) -> bool:
    account_user_id = _load_state().get("account_user_id")
    if account_user_id is None:
        return False
    return str(user_id) == str(account_user_id)

def _is_management_command(text: str) -> bool:
    patterns = [
        r"добавь.*базу",
        r"удали.*базу", 
        r"покажи.*базу",
        r"выведи.*базу",
        r"не\s+отвечай",
        r"выключи.*автоответ",
        r"отключи.*автоответ", 
        r"включи.*автоответ",
        r"отвечай",
        r"запомни.*имя",
        r"remember.*name",
        r"мой.*профиль",
        r"my.*profile",
        r"настройки",
        r"settings",
        r"сброс.*настройки",
        r"reset.*settings",
        r"помощь",
        r"help",
        r"команды"
    ]
    
    return any(re.search(pattern, text, re.IGNORECASE) for pattern in patterns)

def process_state_command(prompt: str, user_id: int | str = None) -> tuple[bool, str]:
    text = prompt.lower().strip()
    
    if not _is_management_command(text):
        return False, ""
    
    if user_id is not None and not is_owner(user_id):
        return True, "Отказано в доступе. Только владелец аккаунта может выполнять команды."

    if re.search(r"добавь.*базу.*?([^:]+):\s*(.+)", text, re.IGNORECASE):
        match = re.search(r"добавь.*базу.*?([^:]+):\s*(.+)", text, re.IGNORECASE)
        if match:
            category = match.group(1).strip()
            info = match.group(2).strip()
            if knowledge.add_knowledge(category, info):
                return True, f"Добавлено в базу знаний ({category}): {info}"
            else:
                return True, "Не удалось добавить в базу знаний"
        return True, "Формат: добавь в базу [категория]: [информация]"

    if re.search(r"удали.*базу.*?([^:]+):\s*(.+)", text, re.IGNORECASE):
        match = re.search(r"удали.*базу.*?([^:]+):\s*(.+)", text, re.IGNORECASE)
        if match:
            category = match.group(1).strip()
            info = match.group(2).strip()
            if knowledge.remove_knowledge(category, info):
                return True, f"Удалено из базы знаний ({category}): {info}"
            else:
                return True, "Не найдено в базе знаний"
        return True, "Формат: удали из базы [категория]: [информация]"

    if re.search(r"(покажи|выведи|показать|показай).*базу", text, re.IGNORECASE):
        knowledge_text = knowledge.knowledge_to_text()
        if knowledge_text:
            return True, f"База знаний:\n{knowledge_text}"
        else:
            return True, "База знаний пуста"

    name_patterns = [
        r"запомни[^\w]*что[^\w]*я[^\w]+([а-яёa-z]{2,}(?:\s+[а-яёa-z]{2,})*)",
        r"запомни[^\w]*меня[^\w]*зовут[^\w]+([а-яёa-z]{2,}(?:\s+[а-яёa-z]{2,})*)",
        r"запомни[^\w]*мое[^\w]*имя[^\w]+([а-яёa-z]{2,}(?:\s+[а-яёa-z]{2,})*)",
        r"запомни[^\w]*я[^\w]+([а-яёa-z]{2,})",
        r"запомни[^\w]*меня[^\w]+зовут[^\w]+([а-яёa-z]{2,})",
        r"remember[^\w]*my[^\w]*name[^\w]*is[^\w]+([a-z]{2,}(?:\s+[a-z]{2,})*)",
        r"my[^\w]*name[^\w]*is[^\w]+([a-z]{2,}(?:\s+[a-z]{2,})*)",
        r"call[^\w]*me[^\w]+([a-z]{2,}(?:\s+[a-z]{2,})*)"
    ]
    
    for pattern in name_patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            name = match.group(1).strip().title()
            name = re.sub(r'\b(зовут|меня|я|мое|имя|name|is|call|me)\b', '', name, flags=re.IGNORECASE).strip()
            if len(name) > 1:
                set_owner_name(name)
                return True, f"Запомнил, что вы {name}."

    if re.search(r"(не\s+отвечай|выключи.*автоответ\w*|отключи.*автоответ\w*|stop.*reply|disable.*auto)", text, re.IGNORECASE):
        set_auto_reply(False)
        return True, "Автоответ выключен."

    if re.search(r"(отвечай|включи.*автоответ\w*|включи.*автоответчик|start.*reply|enable.*auto)", text, re.IGNORECASE) and not re.search(r"не\s+отвечай", text, re.IGNORECASE):
        set_auto_reply(True)
        return True, "Автоответ включен."

    if re.search(r"(настройки|settings|config)", text, re.IGNORECASE):
        auto_reply = "включен" if is_auto_reply() else "выключен"
        account_id = _load_state().get("account_user_id")
        
        settings_text = f"""
Текущие настройки:

Автоответ: {auto_reply}
ID аккаунта: {account_id or 'не установлен'}
Имя владельца: {get_owner_name() or 'не установлено'}
        """
        return True, settings_text.strip()

    if re.search(r"(мой.*профиль|my.*profile|who.*am.*i)", text, re.IGNORECASE):
        owner_name = get_owner_name()
        account_id = _load_state().get("account_user_id")
        auto_reply = "включен" if is_auto_reply() else "выключен"
        
        profile_text = f"""
Ваш профиль:

ID аккаунта: {account_id or 'не установлен'}
Имя: {owner_name or 'не установлено'}
Автоответ: {auto_reply}
        """
        return True, profile_text.strip()

    if re.search(r"(очисти|сброс|reset).*настройки", text, re.IGNORECASE):
        state = _load_state()
        account_id = state.get('account_user_id')
        state = DEFAULT_STATE.copy()
        if account_id:
            state['account_user_id'] = account_id
        _save_state(state)
        return True, "Настройки сброшены к значениям по умолчанию (кроме ID аккаунта)"

    if re.search(r"(помощь|help|команды)", text, re.IGNORECASE):
        help_text = """
Команды управления:

Профиль:
запомни мое имя [Имя] - установить имя
мой профиль - информация о профиле

Настройки:
настройки - текущие настройки
включи автоответ - включить автоответ
выключи автоответ - отключить автоответ

База знаний:
добавь в базу [категория]: [информация]
удали из базу [категория]: [информация]
покажи базу знаний - показать всю базу

Система:
сброс настроек - сбросить настройки
        """
        return True, help_text.strip()

    return False, ""
