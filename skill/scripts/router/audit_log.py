from __future__ import annotations
import json
from datetime import datetime
from pathlib import Path
from typing import Any
LOG_DIR = Path.home() / '.hermes' / 'logs' / 'kingdou'
LOG_DIR.mkdir(parents=True, exist_ok=True)
def log_event(name: str, payload: dict[str, Any]) -> None:
    payload = {'ts': datetime.now().isoformat(timespec='seconds'), **payload}
    with (LOG_DIR / name).open('a', encoding='utf-8') as f:
        f.write(json.dumps(payload, ensure_ascii=False, default=str) + '\n')
def _log(name: str, payload: dict[str, Any]) -> None:
    log_event(name, payload)
