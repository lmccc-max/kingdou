from __future__ import annotations
import hashlib, json, time
from pathlib import Path
from typing import Any
CACHE_PATH = Path.home() / '.hermes' / 'logs' / 'kingdou' / 'idempotency.json'
CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
def make_key(chat_id: str, sender_id: str, text: str) -> str:
    return hashlib.sha256(f'{chat_id}|{sender_id}|{text}'.encode('utf-8')).hexdigest()
def seen_recently(chat_id: str, sender_id: str, text: str, ttl: int = 60) -> bool:
    key = make_key(chat_id, sender_id, text); now = time.time(); data: dict[str, Any] = {}
    if CACHE_PATH.exists():
        try: data = json.loads(CACHE_PATH.read_text())
        except Exception: data = {}
    data = {k:v for k,v in data.items() if now - float(v) < ttl}; hit = key in data; data[key] = now
    CACHE_PATH.write_text(json.dumps(data), encoding='utf-8'); return hit
