import json
import os
import re
import time
from datetime import datetime
from typing import List, Dict, Any, Optional
import hashlib

BASE_DIR = os.path.dirname(__file__)
USERS_DIR = os.path.join(BASE_DIR, "users")
os.makedirs(USERS_DIR, exist_ok=True)

def _sanitize_user_id(user_id: str) -> str:
    return re.sub(r'[<>:"/\\|?*]', '_', str(user_id))

def _user_history_file(user_id: str) -> str:
    uid = _sanitize_user_id(user_id)
    udir = os.path.join(USERS_DIR, uid)
    os.makedirs(udir, exist_ok=True)
    return os.path.join(udir, "history.json")

def _user_history_backup_file(user_id: str) -> str:
    uid = _sanitize_user_id(user_id)
    udir = os.path.join(USERS_DIR, uid)
    os.makedirs(udir, exist_ok=True)
    timestamp = int(time.time())
    return os.path.join(udir, f"history_backup_{timestamp}.json")

def load_history(user_id: str, max_entries: int = 30) -> List[Dict[str, Any]]:
    path = _user_history_file(user_id)
    if not os.path.exists(path):
        return []
    
    max_retries = 2
    for attempt in range(max_retries):
        try:
            with open(path, "r", encoding="utf-8") as f:
                content = f.read().strip()
                if not content:
                    return []
                history = json.loads(content)
            
            if not isinstance(history, list):
                return []
            
            validated_history = []
            for entry in history:
                if isinstance(entry, dict) and 'user' in entry and 'assistant' in entry:
                    validated_entry = {
                        "timestamp": entry.get("timestamp", datetime.utcnow().isoformat()),
                        "prompt": entry.get("user", entry.get("prompt", "")),
                        "response": entry.get("assistant", entry.get("response", "")),
                        "meta": entry.get("meta", {})
                    }
                    validated_history.append(validated_entry)
            
            return validated_history[-max_entries:] if max_entries else validated_history
            
        except json.JSONDecodeError as e:
            if attempt == max_retries - 1:
                backup_path = _user_history_backup_file(user_id)
                try:
                    os.rename(path, backup_path)
                except:
                    pass
                return []
            time.sleep(0.1)
        except Exception as e:
            if attempt == max_retries - 1:
                return []
            time.sleep(0.1)
    
    return []

def add_entry(user_id: str, user_text: str, assistant_text: str, metadata: Optional[Dict] = None) -> bool:
    if not user_text or not assistant_text:
        return False
    
    path = _user_history_file(user_id)
    max_retries = 3
    
    for attempt in range(max_retries):
        try:
            current_history = load_history(user_id, max_entries=0)
            
            entry = {
                "timestamp": datetime.utcnow().isoformat(),
                "prompt": user_text.strip(),
                "response": assistant_text.strip(),
                "meta": metadata or {},
                "hash": hashlib.md5(f"{user_text}{assistant_text}".encode()).hexdigest()[:12]
            }
            
            current_history.append(entry)
            
            if len(current_history) > 100:
                current_history = current_history[-80:]
            
            temp_path = path + ".tmp"
            with open(temp_path, "w", encoding="utf-8") as f:
                json.dump(current_history, f, ensure_ascii=False, indent=2, default=str)
            
            if os.path.exists(path):
                os.replace(temp_path, path)
            else:
                os.rename(temp_path, path)
            
            return True
            
        except Exception as e:
            if attempt == max_retries - 1:
                return False
            time.sleep(0.1)
    
    return False

def clear_history(user_id: Optional[str] = None) -> int:
    cleared_count = 0
    try:
        if user_id is None:
            for uid in os.listdir(USERS_DIR):
                user_dir = os.path.join(USERS_DIR, uid)
                if os.path.isdir(user_dir):
                    history_path = os.path.join(user_dir, "history.json")
                    if os.path.exists(history_path):
                        try:
                            os.remove(history_path)
                            cleared_count += 1
                        except:
                            pass
        else:
            path = _user_history_file(user_id)
            if os.path.exists(path):
                os.remove(path)
                cleared_count = 1
    except Exception:
        pass
    
    return cleared_count

def get_history_stats(user_id: Optional[str] = None) -> Dict[str, Any]:
    stats = {}
    
    try:
        if user_id:
            hist = load_history(user_id, max_entries=0)
            stats = {
                "user_id": user_id,
                "total_messages": len(hist),
                "last_interaction": hist[-1]["timestamp"] if hist else None,
                "message_pairs": len(hist)
            }
        else:
            total_users = 0
            total_messages = 0
            active_users = 0
            
            for uid in os.listdir(USERS_DIR):
                user_dir = os.path.join(USERS_DIR, uid)
                if os.path.isdir(user_dir):
                    history_path = os.path.join(user_dir, "history.json")
                    if os.path.exists(history_path):
                        total_users += 1
                        try:
                            hist = load_history(uid, max_entries=0)
                            if hist:
                                total_messages += len(hist)
                                active_users += 1
                        except:
                            pass
            
            stats = {
                "total_users": total_users,
                "active_users": active_users,
                "total_messages": total_messages,
                "avg_messages_per_user": total_messages / active_users if active_users else 0
            }
    except Exception:
        pass
    
    return stats

def history_to_text(history: List[Dict[str, Any]], max_length: int = 2000) -> str:
    if not history:
        return ""
    
    text_parts = []
    total_len = 0
    recent_history = history[-6:]
    
    for entry in recent_history:
        user_msg = entry.get("prompt", "").strip()
        assistant_msg = entry.get("response", "").strip()
        
        if not user_msg or not assistant_msg:
            continue
        
        block = f"П: {user_msg}\nО: {assistant_msg}\n\n"
        block_len = len(block)
        
        if total_len + block_len > max_length:
            break
            
        text_parts.append(block)
        total_len += block_len
    
    return "".join(text_parts).strip()

def search_history(user_id: str, query: str, max_results: int = 5) -> List[Dict[str, Any]]:
    if not query or not user_id:
        return []
    
    query_lower = query.lower()
    history = load_history(user_id, max_entries=0)
    results = []
    
    for entry in reversed(history):
        if len(results) >= max_results:
            break
            
        user_text = entry.get("prompt", "").lower()
        assistant_text = entry.get("response", "").lower()
        
        if (query_lower in user_text or query_lower in assistant_text):
            results.append(entry)
    
    return results

def get_conversation_summary(user_id: str) -> Dict[str, Any]:
    history = load_history(user_id, max_entries=0)
    if not history:
        return {}
    
    total_interactions = len(history)
    first_interaction = history[0]["timestamp"] if history else None
    last_interaction = history[-1]["timestamp"] if history else None
    
    topics = set()
    for entry in history[-10:]:
        prompt = entry.get("prompt", "").lower()
        if any(word in prompt for word in ['работа', 'проект']):
            topics.add('работа')
        if any(word in prompt for word in ['техника', 'компьютер']):
            topics.add('техника')
        if any(word in prompt for word in ['личное', 'семья']):
            topics.add('личное')
    
    return {
        "total_interactions": total_interactions,
        "first_interaction": first_interaction,
        "last_interaction": last_interaction,
        "frequent_topics": list(topics),
        "interaction_frequency": "high" if total_interactions > 20 else "medium" if total_interactions > 5 else "low"
    }