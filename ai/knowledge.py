import os
import json
import logging
from typing import Dict, List, Optional

BASE_DIR = os.path.dirname(os.path.dirname(__file__))
KNOWLEDGE_DIR = os.path.join(BASE_DIR, "knowledge")
KNOWLEDGE_FILE = os.path.join(KNOWLEDGE_DIR, "knowledge_base.json")

logger = logging.getLogger("faust_assistant")

os.makedirs(KNOWLEDGE_DIR, exist_ok=True)

def _load_knowledge_base() -> Dict[str, List[str]]:
    if os.path.exists(KNOWLEDGE_FILE):
        try:
            with open(KNOWLEDGE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.error("Ошибка загрузки базы знаний: %s", e)
    return {}

def _save_knowledge_base(knowledge: Dict[str, List[str]]):
    try:
        with open(KNOWLEDGE_FILE, "w", encoding="utf-8") as f:
            json.dump(knowledge, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.error("Ошибка сохранения базы знаний: %s", e)

def add_knowledge(category: str, information: str) -> bool:
    try:
        knowledge = _load_knowledge_base()
        if category not in knowledge:
            knowledge[category] = []
        
        if information not in knowledge[category]:
            knowledge[category].append(information)
            _save_knowledge_base(knowledge)
            logger.info("Добавлена информация в категорию '%s': %s", category, information[:50])
            return True
        return False
    except Exception as e:
        logger.error("Ошибка добавления в базу знаний: %s", e)
        return False

def remove_knowledge(category: str, information: str) -> bool:
    try:
        knowledge = _load_knowledge_base()
        if category in knowledge and information in knowledge[category]:
            knowledge[category].remove(information)
            if not knowledge[category]:
                del knowledge[category]
            _save_knowledge_base(knowledge)
            logger.info("Удалена информация из категории '%s': %s", category, information[:50])
            return True
        return False
    except Exception as e:
        logger.error("Ошибка удаления из базы знаний: %s", e)
        return False

def get_knowledge_by_category(category: str) -> List[str]:
    knowledge = _load_knowledge_base()
    return knowledge.get(category, [])

def get_all_knowledge() -> Dict[str, List[str]]:
    return _load_knowledge_base()

def search_knowledge(query: str) -> List[str]:
    knowledge = _load_knowledge_base()
    results = []
    query_lower = query.lower()
    
    for category, items in knowledge.items():
        if query_lower in category.lower():
            results.extend(items)
        for item in items:
            if query_lower in item.lower():
                results.append(item)
    
    return results

def knowledge_to_text() -> str:
    knowledge = _load_knowledge_base()
    if not knowledge:
        return ""
    
    sections = []
    for category, items in knowledge.items():
        if items:
            section = f"{category}:\n" + "\n".join(f"- {item}" for item in items)
            sections.append(section)
    
    return "\n\n".join(sections)