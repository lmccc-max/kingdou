from __future__ import annotations
import json, time
import tempfile
from pathlib import Path
CACHE_PATH = Path(tempfile.gettempdir()) / 'kingdou-rate-limit.json'
def check_rate_limit(key: str, limit: int, window_seconds: int) -> bool:
    now = time.time(); data = {}
    if CACHE_PATH.exists():
        try: data = json.loads(CACHE_PATH.read_text())
        except Exception: data = {}
    vals = [float(x) for x in data.get(key, []) if now - float(x) < window_seconds]
    if len(vals) >= limit:
        data[key] = vals; CACHE_PATH.write_text(json.dumps(data), encoding='utf-8'); return False
    vals.append(now); data[key] = vals; CACHE_PATH.write_text(json.dumps(data), encoding='utf-8'); return True
