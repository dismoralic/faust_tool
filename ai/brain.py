import os
import json
import time
import logging
import asyncio
import re
from difflib import SequenceMatcher
from functools import lru_cache
from typing import Optional, Tuple, Dict, List, Any
from dataclasses import dataclass
import aiohttp
from datetime import datetime
import hashlib

from ai.history import load_history, add_entry, history_to_text
from ai.facts import load_facts, add_fact, facts_to_text, set_user_name, get_user_name
from ai import state, commands, knowledge

BASE_DIR = os.path.dirname(__file__)
FAQ_PATH = os.getenv("FAUST_FAQ_PATH", os.path.join(BASE_DIR, "faq.json"))

OLLAMA_MODEL = os.getenv("FAUST_OLLAMA_MODEL", "gemma3:1b")
OLLAMA_TIMEOUT = float(os.getenv("FAUST_OLLAMA_TIMEOUT", "30"))
OLLAMA_URL = os.getenv("FAUST_OLLAMA_URL", "http://127.0.0.1:11434/api/generate")

logger = logging.getLogger("faust_assistant")
if not logger.handlers:
    logger.setLevel(logging.INFO)
    fmt = logging.Formatter("%(asctime)s %(levelname)s %(message)s")
    ch = logging.StreamHandler()
    ch.setFormatter(fmt)
    logger.addHandler(ch)

@dataclass
class UserContext:
    facts: Dict[str, Any]
    history_patterns: Dict[str, Any]
    preferences: Dict[str, Any]
    last_updated: float

class EnhancedConversationMemory:
    def __init__(self):
        self.user_contexts: Dict[str, UserContext] = {}
        self.pattern_cache: Dict[str, Dict] = {}
    
    def get_user_context(self, user_id: str) -> UserContext:
        if user_id not in self.user_contexts:
            self.user_contexts[user_id] = UserContext(
                facts={}, history_patterns={}, preferences={}, last_updated=0
            )
        return self.user_contexts[user_id]
    
    def analyze_conversation_patterns(self, history: List[Dict]) -> Dict[str, Any]:
        if not history:
            return {}
        
        analysis = {
            'frequent_topics': self._extract_topics(history),
            'communication_style': self._analyze_communication_style(history),
            'preferred_subjects': self._find_preferred_subjects(history),
            'temporal_patterns': self._analyze_temporal_patterns(history),
            'sentiment_trend': self._analyze_sentiment_trend(history)
        }
        
        return analysis
    
    def _extract_topics(self, history: List[Dict]) -> List[str]:
        topics = []
        topic_keywords = {
            'работа': ['работа', 'проект', 'задача', 'начальник', 'коллега'],
            'техника': ['компьютер', 'телефон', 'интернет', 'программа', 'приложение'],
            'личное': ['семья', 'друзья', 'отношения', 'дом', 'квартира'],
            'хобби': ['хобби', 'увлечение', 'спорт', 'кино', 'музыка', 'книги'],
            'помощь': ['помоги', 'помощь', 'вопрос', 'проблема', 'решить']
        }
        
        for entry in history[-10:]:
            text = (entry.get('prompt', '') + ' ' + entry.get('response', '')).lower()
            for topic, keywords in topic_keywords.items():
                if any(keyword in text for keyword in keywords) and topic not in topics:
                    topics.append(topic)
        
        return topics
    
    def _analyze_communication_style(self, history: List[Dict]) -> str:
        if len(history) < 3:
            return "нейтральный"
        
        formal_indicators = 0
        casual_indicators = 0
        
        for entry in history[-5:]:
            prompt = entry.get('prompt', '').lower()
            if any(word in prompt for word in ['пожалуйста', 'спасибо', 'будьте добры', 'извините']):
                formal_indicators += 1
            if any(word in prompt for word in ['привет', 'пока', 'норм', 'окей', 'лол']):
                casual_indicators += 1
        
        if formal_indicators > casual_indicators:
            return "формальный"
        elif casual_indicators > formal_indicators:
            return "неформальный"
        return "нейтральный"
    
    def _find_preferred_subjects(self, history: List[Dict]) -> List[str]:
        subjects = []
        question_patterns = []
        
        for entry in history[-8:]:
            prompt = entry.get('prompt', '').lower()
            if '?' in prompt:
                question_patterns.append(prompt)
            
            if any(word in prompt for word in ['расскажи', 'знаешь', 'интересно']):
                subject = re.sub(r'.*(расскажи|знаешь|интересно)\s+о?\s*', '', prompt)
                if len(subject) > 3:
                    subjects.append(subject.strip())
        
        return list(set(subjects))[:5]
    
    def _analyze_temporal_patterns(self, history: List[Dict]) -> Dict[str, Any]:
        if len(history) < 2:
            return {}
        
        times = []
        for entry in history:
            if 'timestamp' in entry:
                try:
                    times.append(float(entry['timestamp']))
                except:
                    pass
        
        if len(times) < 2:
            return {}
        
        intervals = [times[i+1] - times[i] for i in range(len(times)-1)]
        avg_interval = sum(intervals) / len(intervals) if intervals else 0
        
        return {
            'average_response_time': avg_interval,
            'interaction_frequency': 'high' if avg_interval < 3600 else 'medium' if avg_interval < 86400 else 'low'
        }
    
    def _analyze_sentiment_trend(self, history: List[Dict]) -> str:
        if not history:
            return "нейтральный"
        
        recent_sentiment = []
        for entry in history[-5:]:
            text = entry.get('prompt', '').lower() + ' ' + entry.get('response', '').lower()
            positive_words = len([w for w in ['спасибо', 'отлично', 'супер', 'хорошо', 'рад'] if w in text])
            negative_words = len([w for w in ['плохо', 'грустно', 'злюсь', 'проблема', 'сложно'] if w in text])
            
            if positive_words > negative_words:
                recent_sentiment.append(1)
            elif negative_words > positive_words:
                recent_sentiment.append(-1)
            else:
                recent_sentiment.append(0)
        
        avg_sentiment = sum(recent_sentiment) / len(recent_sentiment) if recent_sentiment else 0
        
        if avg_sentiment > 0.3:
            return "позитивный"
        elif avg_sentiment < -0.3:
            return "негативный"
        return "нейтральный"

conversation_memory = EnhancedConversationMemory()

_session: aiohttp.ClientSession | None = None
_response_cache: Dict[str, Tuple[str, float]] = {}
_cache_ttl = 300

def get_cache_key(prompt: str, user_id: str, context_hash: str = "") -> str:
    base_key = f"{user_id}:{prompt.lower().strip()}"
    if context_hash:
        base_key += f":{context_hash}"
    return hashlib.md5(base_key.encode()).hexdigest()

async def get_session() -> aiohttp.ClientSession:
    global _session
    if _session is None or _session.closed:
        timeout = aiohttp.ClientTimeout(total=OLLAMA_TIMEOUT + 15)
        connector = aiohttp.TCPConnector(limit=30, keepalive_timeout=10)
        _session = aiohttp.ClientSession(timeout=timeout, connector=connector)
    return _session

@lru_cache(maxsize=1)
def _load_faq_raw() -> dict:
    max_retries = 3
    for attempt in range(max_retries):
        try:
            with open(FAQ_PATH, "r", encoding="utf-8") as f:
                content = f.read().strip()
                if not content:
                    return {}
                return json.loads(content)
        except json.JSONDecodeError as e:
            logger.warning(f"FAQ JSON decode error (attempt {attempt+1}): {e}")
            if attempt == max_retries - 1:
                return {}
            time.sleep(0.1)
        except Exception as e:
            logger.warning(f"FAQ load error (attempt {attempt+1}): {e}")
            if attempt == max_retries - 1:
                return {}
            time.sleep(0.1)
    return {}

faq_data = _load_faq_raw()

@lru_cache(maxsize=4096)
def _similarity(a: str, b: str) -> float:
    a_clean = re.sub(r'[^\w\s]', '', a.lower().strip())
    b_clean = re.sub(r'[^\w\s]', '', b.lower().strip())
    
    if a_clean == b_clean:
        return 1.0
    
    a_words = set(a_clean.split())
    b_words = set(b_clean.split())
    
    if not a_words or not b_words:
        return 0.0
    
    intersection = len(a_words & b_words)
    union = len(a_words | b_words)
    
    jaccard = intersection / union if union > 0 else 0.0
    sequence = SequenceMatcher(None, a_clean, b_clean).ratio()
    
    return max(jaccard, sequence)

def enhanced_local_match(prompt: str, user_context: UserContext) -> Tuple[Optional[str], float, Dict[str, Any]]:
    if not faq_data:
        return None, 0.0, {}
    
    prompt_clean = re.sub(r'[^\w\s]', '', prompt.lower().strip())
    
    exact_match = None
    for q in faq_data.keys():
        q_clean = re.sub(r'[^\w\s]', '', q.lower().strip())
        if prompt_clean == q_clean:
            exact_match = q
            break
    
    if exact_match:
        return exact_match, 1.0, {"match_type": "exact"}
    
    best_match = None
    best_score = 0.0
    match_context = {"match_type": "semantic", "context_boost": 0.0}
    
    user_topics = user_context.facts.get('frequent_topics', [])
    user_style = user_context.facts.get('communication_style', 'нейтральный')
    
    for question, answer in faq_data.items():
        score = _similarity(prompt, question)
        
        context_boost = 0.0
        question_lower = question.lower()
        
        for topic in user_topics:
            if topic in question_lower:
                context_boost += 0.1
                break
        
        if user_style == "формальный" and any(word in question_lower for word in ['пожалуйста', 'будьте', 'извините']):
            context_boost += 0.05
        
        total_score = min(1.0, score + context_boost)
        
        if total_score > best_score:
            best_score = total_score
            best_match = question
            match_context["context_boost"] = context_boost
    
    return best_match, best_score, match_context

def robust_clean_response(text: str) -> str:
    if not text or not isinstance(text, str):
        return "Не совсем понял. Можете переформулировать?"
    
    text = text.strip()
    if len(text) < 2:
        return "Не совсем понял. Можете переформулировать?"
    
    patterns_to_remove = [
        r'^(ассистент|фауст|бот|assistant|ai)[:\s\-]*',
        r'^[\[\{].*?[\}\]]\s*',
        r'\s+',
        r'\.{2,}'
    ]
    
    for pattern in patterns_to_remove:
        text = re.sub(pattern, ' ' if pattern == r'\s+' else '', text, flags=re.IGNORECASE)
    
    text = re.sub(r'\s+', ' ', text).strip()
    
    if not text or len(text) < 2:
        return "Не совсем понял. Можете переформулировать?"
    
    return text

def _check_cache(prompt: str, user_id: str, context_hash: str = "") -> Optional[str]:
    cache_key = get_cache_key(prompt, user_id, context_hash)
    now = time.time()
    
    if cache_key in _response_cache:
        response, timestamp = _response_cache[cache_key]
        if now - timestamp < _cache_ttl:
            return response
        else:
            del _response_cache[cache_key]
    
    if len(_response_cache) > 1000:
        oldest_keys = sorted(_response_cache.keys(), key=lambda k: _response_cache[k][1])[:100]
        for key in oldest_keys:
            del _response_cache[key]
    
    return None

def _add_to_cache(prompt: str, user_id: str, response: str, context_hash: str = ""):
    cache_key = get_cache_key(prompt, user_id, context_hash)
    _response_cache[cache_key] = (response, time.time())

async def resilient_ollama_call(system_prompt: str, user_prompt: str, conversation_history: List, timeout: float = OLLAMA_TIMEOUT) -> str:
    max_retries = 2
    base_delay = 1.0
    
    history_context = ""
    if conversation_history:
        recent = conversation_history[-4:]
        history_lines = []
        for h in recent:
            user_msg = h.get('prompt', '').strip()
            assistant_msg = h.get('response', '').strip()
            if user_msg:
                history_lines.append(f"П: {user_msg}")
            if assistant_msg:
                history_lines.append(f"О: {assistant_msg}")
        if history_lines:
            history_context = "\n".join(history_lines[-8:])
    
    full_prompt = f"{system_prompt}"
    if history_context:
        full_prompt += f"\n\nИстория:\n{history_context}"
    full_prompt += f"\n\nП: {user_prompt}\nО:"
    
    payload = {
        "model": OLLAMA_MODEL,
        "prompt": full_prompt,
        "stream": False,
        "options": {
            "temperature": 0.7,
            "num_predict": 500,
            "top_k": 40,
            "top_p": 0.9,
            "repeat_penalty": 1.1
        }
    }
    
    for attempt in range(max_retries):
        try:
            session = await get_session()
            async with session.post(OLLAMA_URL, json=payload, timeout=timeout) as response:
                if response.status == 200:
                    data = await response.json()
                    response_text = data.get("response", "").strip()
                    if response_text:
                        return response_text
                elif response.status == 503:
                    logger.warning(f"Ollama service unavailable, attempt {attempt + 1}")
                else:
                    logger.warning(f"Ollama HTTP error {response.status}, attempt {attempt + 1}")
        
        except asyncio.TimeoutError:
            logger.warning(f"Ollama timeout, attempt {attempt + 1}")
        except aiohttp.ClientError as e:
            logger.warning(f"Ollama connection error: {e}, attempt {attempt + 1}")
        except Exception as e:
            logger.warning(f"Unexpected Ollama error: {e}, attempt {attempt + 1}")
        
        if attempt < max_retries - 1:
            await asyncio.sleep(base_delay * (2 ** attempt))
    
    return ""

def advanced_name_extraction(prompt: str) -> Optional[str]:
    patterns = [
        r"(?:меня\s+зовут\s+)([а-яёa-z]{2,}(?:\s+[а-яёa-z]{2,})?)",
        r"(?:я\s+)([а-яёa-z]{2,}(?:\s+[а-яёa-z]{2,})?)(?:\s|$|\.|,)",
        r"(?:зовут\s+)([а-яёa-z]{2,}(?:\s+[а-яёa-z]{2,})?)",
        r"(?:мое\s+имя\s+)([а-яёa-z]{2,}(?:\s+[а-яёa-z]{2,})?)",
        r"(?:имя\s+)([а-яёa-z]{2,}(?:\s+[а-яёa-z]{2,})?)(?:\s|$|\.|,)"
    ]
    
    for pattern in patterns:
        match = re.search(pattern, prompt.lower())
        if match:
            name = match.group(1).strip().title()
            name = re.sub(r'\b(зовут|меня|я|мое|имя|это)\b', '', name, flags=re.IGNORECASE).strip()
            if len(name) > 1 and not name.isspace():
                return name
    
    return None

async def enhanced_user_info_extraction(prompt: str, response: str, history: List[Dict]) -> Dict[str, List[str]]:
    facts = []
    
    name = advanced_name_extraction(prompt)
    if name:
        facts.append(f"имя: {name}")
    
    location_matches = re.findall(r'(?:живу|город|город|в)\s+([а-яё\w\s]{3,}?(?=\s|\.|$|,))', prompt.lower())
    for location in location_matches[:1]:
        clean_location = re.sub(r'\b(в|городе|городу|живу)\b', '', location, flags=re.IGNORECASE).strip()
        if len(clean_location) > 2:
            facts.append(f"город: {clean_location.title()}")
    
    interest_patterns = [
        r'(?:интересуюсь|увлекаюсь|люблю|нравится)\s+([^.!?]+)',
        r'(?:хобби|увлечение)\s*[:\-]?\s*([^.!?]+)'
    ]
    
    for pattern in interest_patterns:
        matches = re.findall(pattern, prompt.lower())
        for match in matches:
            interests = match.strip()
            if len(interests) > 3:
                facts.append(f"интересы: {interests}")
    
    profession_match = re.search(r'(?:работаю|профессия|специальность)\s+([^.!?]+)', prompt.lower())
    if profession_match:
        facts.append(f"профессия: {profession_match.group(1).strip()}")
    
    return {"facts": facts}

def build_adaptive_system_prompt(user_facts: str, history: List[Dict], user_id: str, is_owner: bool, user_name: str = "") -> str:
    owner_name = state.get_owner_name()
    user_context = conversation_memory.get_user_context(user_id)
    
    if history and time.time() - user_context.last_updated > 3600:
        analysis = conversation_memory.analyze_conversation_patterns(history)
        user_context.facts.update(analysis)
        user_context.last_updated = time.time()
    
    parts = []
    parts.append("Ты - полезный ассистент. Отвечай естественно, по делу, учитывая контекст.")
    
    if is_owner:
        greeting = f"Общаешься с создателем {owner_name}." if owner_name else "Общаешься с создателем."
        parts.append(greeting)
    else:
        if user_facts:
            parts.append(f"Информация о собеседнике: {user_facts}")
        
        if user_context.facts.get('communication_style'):
            style = user_context.facts['communication_style']
            if style == "формальный":
                parts.append("Собеседник предпочитает формальное общение.")
            elif style == "неформальный":
                parts.append("Собеседник предпочитает неформальное общение.")
    
    knowledge_text = knowledge.knowledge_to_text()
    if knowledge_text:
        parts.append(f"База знаний: {knowledge_text}")
    
    if user_context.facts.get('frequent_topics'):
        topics = ", ".join(user_context.facts['frequent_topics'][:3])
        parts.append(f"Частые темы собеседника: {topics}")
    
    if user_context.facts.get('sentiment_trend'):
        sentiment = user_context.facts['sentiment_trend']
        if sentiment == "позитивный":
            parts.append("Собеседник в позитивном настроении.")
        elif sentiment == "негативный":
            parts.append("Собеседник в негативном настроении - будь особенно тактичен.")
    
    parts.extend([
        "Будь кратким и точным.",
        "Не придумывай информацию, если не уверен.",
        "Если не знаешь ответа - честно скажи об этом.",
        "Учитывай стиль общения собеседника."
    ])
    
    return "\n".join(parts)

async def analyze(prompt: str, user_id: str, timeout: float = OLLAMA_TIMEOUT, user_display_name: str = "") -> str:
    try:
        uid = user_id.split('_')[-1] if '_' in user_id else user_id
        is_owner_user = state.is_owner(uid)
        
        context_hash = hashlib.md5(f"{uid}_{is_owner_user}".encode()).hexdigest()[:8]
        cached = _check_cache(prompt, uid, context_hash)
        if cached:
            return cached
        
        prompt_clean = prompt.strip()
        if not prompt_clean or len(prompt_clean) < 1:
            return "Не понял ваш запрос."
        
        prompt_lower = prompt_clean.lower()
        
        if any(cmd in prompt_lower for cmd in ["как меня зовут", "мое имя", "кто я", "my name", "who am i"]):
            if is_owner_user:
                owner_name = state.get_owner_name()
                return f"Вы {owner_name}." if owner_name else "Не знаю вашего имени."
            else:
                user_name = get_user_name(uid)
                return f"Вас зовут {user_name}." if user_name else "Не знаю вашего имени."
        
        if any(cmd in prompt_lower for cmd in ["кто ты", "представься", "твое имя", "who are you", "introduce yourself"]):
            return "Я ассистент, готовый помочь."
        
        current_name = get_user_name(uid)
        if not current_name:
            extracted_name = advanced_name_extraction(prompt)
            if extracted_name:
                set_user_name(uid, extracted_name)
        
        handled_state, resp_state = state.process_state_command(prompt, uid)
        if handled_state:
            add_entry(uid, prompt, resp_state)
            return resp_state
        
        handled_cmd, resp_cmd = await commands.process_command(prompt, uid)
        if handled_cmd:
            add_entry(uid, prompt, resp_cmd)
            _add_to_cache(prompt, uid, resp_cmd, context_hash)
            return resp_cmd
        
        user_context = conversation_memory.get_user_context(uid)
        q, score, match_info = enhanced_local_match(prompt, user_context)
        
        if q and score >= 0.75:
            resp_text = faq_data.get(q, "")
            if resp_text:
                add_entry(uid, prompt, resp_text)
                _add_to_cache(prompt, uid, resp_text, context_hash)
                return resp_text
        
        try:
            history_entries = load_history(uid, max_entries=8)
            facts_data = load_facts(uid)
            facts_text = facts_to_text(facts_data)
            current_user_name = get_user_name(uid)
        except Exception as e:
            logger.warning(f"Error loading history/facts: {e}")
            history_entries = []
            facts_text = ""
            current_user_name = ""
        
        display_name = current_user_name or user_display_name
        system_prompt = build_adaptive_system_prompt(facts_text, history_entries, uid, is_owner_user, display_name)
        
        raw_response = await resilient_ollama_call(system_prompt, prompt, history_entries, timeout)
        resp_text = robust_clean_response(raw_response)
        
        if not resp_text or resp_text == "Не совсем понял. Можете переформулировать?":
            if score >= 0.6:
                resp_text = faq_data.get(q, "Не могу найти подходящий ответ.")
            else:
                resp_text = "Извините, не совсем понял вопрос. Можете переформулировать?"
        
        add_entry(uid, prompt, resp_text)
        _add_to_cache(prompt, uid, resp_text, context_hash)
        
        asyncio.create_task(enhanced_user_info_update(uid, prompt, resp_text, history_entries))
        
        return resp_text
    
    except Exception as e:
        logger.error(f"Critical error in analyze: {e}")
        return "Произошла внутренняя ошибка. Пожалуйста, попробуйте еще раз."
        
async def enhanced_user_info_update(uid, prompt, resp_text, history_entries):
    try:
        user_info = await enhanced_user_info_extraction(prompt, resp_text, history_entries)
        for fact in user_info.get("facts", []):
            if fact and len(fact) > 5:
                add_fact(uid, fact)
        
        user_context = conversation_memory.get_user_context(uid)
        if history_entries:
            analysis = conversation_memory.analyze_conversation_patterns(history_entries)
            user_context.facts.update(analysis)
            user_context.last_updated = time.time()
    except Exception as e:
        logger.debug(f"User info update error: {e}")

async def resilient_cleanup():
    global _session
    if _session and not _session.closed:
        try:
            await asyncio.wait_for(_session.close(), timeout=5.0)
        except asyncio.TimeoutError:
            pass
        except Exception as e:
            logger.debug(f"Session close error: {e}")

def register(client):
    return True