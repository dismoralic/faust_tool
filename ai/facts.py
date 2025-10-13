import json
import os
import re
import tempfile
import logging
import time
import hashlib
from datetime import datetime
from typing import List, Dict, Any, Optional, Tuple
from functools import lru_cache

logger = logging.getLogger(__name__)

BASE_DIR = os.path.dirname(__file__)
USERS_DIR = os.path.join(BASE_DIR, "users")
os.makedirs(USERS_DIR, exist_ok=True)

def _sanitize_user_id(user_id: str) -> str:
    return re.sub(r'[<>:"/\\|?*]', '_', str(user_id))

def _get_user_dir(user_id: str) -> str:
    uid = _sanitize_user_id(user_id)
    path = os.path.join(USERS_DIR, uid)
    os.makedirs(path, exist_ok=True)
    return path

def _get_user_facts_file(user_id: str) -> str:
    return os.path.join(_get_user_dir(user_id), "facts.json")

def _get_user_facts_backup_file(user_id: str) -> str:
    uid = _sanitize_user_id(user_id)
    timestamp = int(time.time())
    return os.path.join(_get_user_dir(user_id), f"facts_backup_{timestamp}.json")

def _atomic_write(path: str, data: Any) -> bool:
    max_retries = 3
    ddir = os.path.dirname(path)
    
    for attempt in range(max_retries):
        try:
            with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=ddir, delete=False) as tf:
                json.dump(data, tf, ensure_ascii=False, indent=2, default=str)
                temp_name = tf.name
            
            if os.path.exists(path):
                os.replace(temp_name, path)
            else:
                os.rename(temp_name, path)
            return True
            
        except Exception as e:
            logger.warning(f"Atomic write attempt {attempt + 1} failed for {path}: {e}")
            if os.path.exists(temp_name):
                try:
                    os.remove(temp_name)
                except:
                    pass
            
            if attempt == max_retries - 1:
                logger.error(f"All atomic write attempts failed for {path}")
                return False
            time.sleep(0.1)
    
    return False

def load_facts(user_id: str) -> Dict[str, Any]:
    path = _get_user_facts_file(user_id)
    if not os.path.exists(path):
        return {"facts": [], "user_name": "", "metadata": {"created": datetime.utcnow().isoformat(), "updated": datetime.utcnow().isoformat()}}
    
    max_retries = 2
    for attempt in range(max_retries):
        try:
            with open(path, "r", encoding="utf-8") as f:
                content = f.read().strip()
                if not content:
                    return {"facts": [], "user_name": "", "metadata": {"created": datetime.utcnow().isoformat(), "updated": datetime.utcnow().isoformat()}}
                
                data = json.loads(content)
            
            if isinstance(data, list):
                return {
                    "facts": data,
                    "user_name": "",
                    "metadata": {"created": datetime.utcnow().isoformat(), "updated": datetime.utcnow().isoformat()}
                }
            elif isinstance(data, dict):
                return {
                    "facts": data.get("facts", []),
                    "user_name": data.get("user_name", ""),
                    "metadata": data.get("metadata", {"created": datetime.utcnow().isoformat(), "updated": datetime.utcnow().isoformat()})
                }
            else:
                return {"facts": [], "user_name": "", "metadata": {"created": datetime.utcnow().isoformat(), "updated": datetime.utcnow().isoformat()}}
                
        except json.JSONDecodeError as e:
            if attempt == max_retries - 1:
                logger.warning(f"JSON decode error for {path}, creating backup")
                try:
                    backup_path = _get_user_facts_backup_file(user_id)
                    os.rename(path, backup_path)
                except:
                    pass
                return {"facts": [], "user_name": "", "metadata": {"created": datetime.utcnow().isoformat(), "updated": datetime.utcnow().isoformat()}}
            time.sleep(0.1)
        except Exception as e:
            if attempt == max_retries - 1:
                logger.warning(f"Load facts error for {user_id}: {e}")
                return {"facts": [], "user_name": "", "metadata": {"created": datetime.utcnow().isoformat(), "updated": datetime.utcnow().isoformat()}}
            time.sleep(0.1)
    
    return {"facts": [], "user_name": "", "metadata": {"created": datetime.utcnow().isoformat(), "updated": datetime.utcnow().isoformat()}}

def save_facts(user_id: str, facts_data: Dict[str, Any]) -> bool:
    path = _get_user_facts_file(user_id)
    
    if not isinstance(facts_data, dict):
        return False
    
    facts_data["metadata"] = facts_data.get("metadata", {})
    facts_data["metadata"]["updated"] = datetime.utcnow().isoformat()
    
    if "created" not in facts_data["metadata"]:
        facts_data["metadata"]["created"] = datetime.utcnow().isoformat()
    
    return _atomic_write(path, facts_data)

def _extract_fact_type(fact: str) -> Tuple[str, str]:
    fact_lower = fact.lower()
    if any(keyword in fact_lower for keyword in ['имя:', 'зовут']):
        return 'name', fact
    elif any(keyword in fact_lower for keyword in ['город:', 'живет']):
        return 'location', fact
    elif any(keyword in fact_lower for keyword in ['интересы:', 'увлекается', 'хобби']):
        return 'interests', fact
    elif any(keyword in fact_lower for keyword in ['работа:', 'профессия']):
        return 'profession', fact
    elif any(keyword in fact_lower for keyword in ['возраст:', 'лет']):
        return 'age', fact
    else:
        return 'general', fact

def _clean_fact_text(fact: str) -> str:
    return re.sub(r'\s*\([^)]*\)\s*$', '', fact).strip()

def _normalize_fact(fact: str) -> str:
    clean_text = _clean_fact_text(fact)
    fact_type, _ = _extract_fact_type(clean_text)
    
    if fact_type == 'name':
        return re.sub(r'(имя|зовут)[:\s]*', '', clean_text, flags=re.IGNORECASE).strip()
    elif fact_type == 'location':
        return re.sub(r'(город|живет)[:\s]*', '', clean_text, flags=re.IGNORECASE).strip()
    elif fact_type == 'interests':
        return re.sub(r'(интересы|увлекается|хобби)[:\s]*', '', clean_text, flags=re.IGNORECASE).strip()
    elif fact_type == 'profession':
        return re.sub(r'(работа|профессия)[:\s]*', '', clean_text, flags=re.IGNORECASE).strip()
    
    return clean_text

@lru_cache(maxsize=4096)
def _fact_similarity(a: str, b: str) -> float:
    from difflib import SequenceMatcher
    
    norm_a = _normalize_fact(a).lower()
    norm_b = _normalize_fact(b).lower()
    
    if norm_a == norm_b:
        return 1.0
    
    a_type, _ = _extract_fact_type(a)
    b_type, _ = _extract_fact_type(b)
    
    if a_type != b_type:
        return 0.0
    
    a_words = set(norm_a.split())
    b_words = set(norm_b.split())
    
    if not a_words or not b_words:
        return 0.0
    
    intersection = len(a_words & b_words)
    union = len(a_words | b_words)
    
    jaccard = intersection / union if union > 0 else 0.0
    sequence = SequenceMatcher(None, norm_a, norm_b).ratio()
    
    return max(jaccard, sequence * 0.8)

def add_fact(user_id: str, fact: str) -> bool:
    if not fact or len(fact.strip()) < 2:
        return False
    
    fact = fact.strip()
    facts_data = load_facts(user_id)
    facts = facts_data.get("facts", [])
    
    fact_type, _ = _extract_fact_type(fact)
    normalized_new = _normalize_fact(fact)
    
    for existing_fact in facts:
        existing_type, _ = _extract_fact_type(existing_fact)
        if fact_type == existing_type and fact_type in ['name', 'location']:
            if _fact_similarity(fact, existing_fact) > 0.6:
                return update_fact(user_id, fact, threshold=0.5)
    
    for existing_fact in facts:
        if _fact_similarity(fact, existing_fact) > 0.8:
            return False
    
    timestamp = datetime.utcnow().strftime('%d.%m.%Y %H:%M')
    fact_with_meta = f"{fact} (добавлено: {timestamp})"
    facts.append(fact_with_meta)
    
    facts_data["facts"] = facts[-50:]
    facts_data["metadata"]["updated"] = datetime.utcnow().isoformat()
    
    return save_facts(user_id, facts_data)

def set_user_name(user_id: str, name: str) -> bool:
    if not name or len(name.strip()) < 2:
        return False
    
    name = name.strip().title()
    facts_data = load_facts(user_id)
    
    facts_data["user_name"] = name
    
    name_fact = f"имя: {name}"
    timestamp = datetime.utcnow().strftime('%d.%m.%Y %H:%M')
    name_fact_with_meta = f"{name_fact} (обновлено: {timestamp})"
    
    facts = facts_data.get("facts", [])
    
    for i, fact in enumerate(facts):
        if _extract_fact_type(fact)[0] == 'name':
            facts[i] = name_fact_with_meta
            break
    else:
        facts.append(name_fact_with_meta)
    
    facts_data["facts"] = facts
    facts_data["metadata"]["updated"] = datetime.utcnow().isoformat()
    
    return save_facts(user_id, facts_data)

def get_user_name(user_id: str) -> str:
    facts_data = load_facts(user_id)
    
    name = facts_data.get("user_name", "")
    if name:
        return name
    
    facts = facts_data.get("facts", [])
    for fact in facts:
        fact_type, fact_content = _extract_fact_type(fact)
        if fact_type == 'name':
            clean_name = _normalize_fact(fact_content)
            if clean_name and len(clean_name) > 1:
                return clean_name.title()
    
    return ""

def update_fact(user_id: str, new_fact: str, threshold: float = 0.6) -> bool:
    if not new_fact or len(new_fact.strip()) < 2:
        return False
    
    new_fact = new_fact.strip()
    facts_data = load_facts(user_id)
    facts = facts_data.get("facts", [])
    
    if not facts:
        return add_fact(user_id, new_fact)
    
    new_fact_type, _ = _extract_fact_type(new_fact)
    best_match_idx = -1
    best_similarity = 0.0
    
    for idx, existing_fact in enumerate(facts):
        existing_type, _ = _extract_fact_type(existing_fact)
        
        if new_fact_type == existing_type and new_fact_type in ['name', 'location', 'profession']:
            similarity = _fact_similarity(new_fact, existing_fact)
            if similarity > best_similarity:
                best_similarity = similarity
                best_match_idx = idx
    
    if best_match_idx >= 0 and best_similarity >= threshold:
        timestamp = datetime.utcnow().strftime('%d.%m.%Y %H:%M')
        facts[best_match_idx] = f"{new_fact} (обновлено: {timestamp})"
    else:
        timestamp = datetime.utcnow().strftime('%d.%m.%Y %H:%M')
        facts.append(f"{new_fact} (добавлено: {timestamp})")
    
    facts_data["facts"] = facts[-50:]
    facts_data["metadata"]["updated"] = datetime.utcnow().isoformat()
    
    return save_facts(user_id, facts_data)

def clear_facts(user_id: Optional[str] = None) -> int:
    cleared_count = 0
    try:
        if user_id is None:
            for uid in os.listdir(USERS_DIR):
                user_dir = os.path.join(USERS_DIR, uid)
                if os.path.isdir(user_dir):
                    facts_path = os.path.join(user_dir, "facts.json")
                    if os.path.exists(facts_path):
                        try:
                            os.remove(facts_path)
                            cleared_count += 1
                        except:
                            pass
        else:
            path = _get_user_facts_file(user_id)
            if os.path.exists(path):
                os.remove(path)
                cleared_count = 1
    except Exception as e:
        logger.warning(f"Clear facts error: {e}")
    
    return cleared_count

def get_facts_stats() -> Dict[str, Any]:
    total_users = 0
    total_facts = 0
    users_with_facts = 0
    fact_types = {}
    
    try:
        for uid in os.listdir(USERS_DIR):
            user_dir = os.path.join(USERS_DIR, uid)
            if os.path.isdir(user_dir):
                facts_path = os.path.join(user_dir, "facts.json")
                if os.path.exists(facts_path):
                    total_users += 1
                    try:
                        data = load_facts(uid)
                        facts = data.get("facts", [])
                        if facts:
                            users_with_facts += 1
                            total_facts += len(facts)
                            
                            for fact in facts:
                                fact_type, _ = _extract_fact_type(fact)
                                fact_types[fact_type] = fact_types.get(fact_type, 0) + 1
                    except Exception:
                        continue
    except Exception as e:
        logger.warning(f"Facts stats error: {e}")
    
    return {
        "total_users": total_users,
        "users_with_facts": users_with_facts,
        "total_facts": total_facts,
        "avg_facts_per_user": total_facts / users_with_facts if users_with_facts else 0,
        "fact_types": fact_types
    }

def facts_to_text(facts_data: Dict[str, Any]) -> str:
    if not facts_data:
        return ""
    
    facts = facts_data.get("facts", [])
    user_name = facts_data.get("user_name", "")
    
    if not facts and not user_name:
        return ""
    
    parts = []
    
    if user_name:
        parts.append(f"Пользователя зовут {user_name}")
    
    fact_categories = {}
    for fact in facts:
        fact_type, fact_content = _extract_fact_type(fact)
        clean_fact = _clean_fact_text(fact_content)
        
        if fact_type not in fact_categories:
            fact_categories[fact_type] = []
        
        if clean_fact not in fact_categories[fact_type]:
            fact_categories[fact_type].append(clean_fact)
    
    category_order = ['name', 'profession', 'location', 'age', 'interests', 'general']
    for category in category_order:
        if category in fact_categories and fact_categories[category]:
            if category == 'name' and user_name:
                continue
            facts_list = ", ".join(fact_categories[category][:3])
            parts.append(facts_list)
    
    return ". ".join(parts) if parts else ""

def get_user_facts_summary(user_id: str) -> Dict[str, Any]:
    facts_data = load_facts(user_id)
    facts = facts_data.get("facts", [])
    user_name = facts_data.get("user_name", "")
    
    summary = {
        "has_name": bool(user_name),
        "fact_count": len(facts),
        "fact_categories": {},
        "last_updated": facts_data.get("metadata", {}).get("updated", "")
    }
    
    for fact in facts:
        fact_type, _ = _extract_fact_type(fact)
        summary["fact_categories"][fact_type] = summary["fact_categories"].get(fact_type, 0) + 1
    
    return summary

def merge_facts(user_id: str, new_facts: List[str]) -> int:
    added_count = 0
    for fact in new_facts:
        if add_fact(user_id, fact):
            added_count += 1
    return added_count