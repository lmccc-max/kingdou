from __future__ import annotations
import json, time
from pathlib import Path
from typing import Any
CONFIG_PATH = Path(__file__).resolve().parents[2] / 'configs' / 'piecework-groups.json'
_CONFIG_CACHE: tuple[float, dict[str, Any]] | None = None
def load_config(force: bool = False) -> dict[str, Any]:
    global _CONFIG_CACHE
    now = time.time()
    if not force and _CONFIG_CACHE and now - _CONFIG_CACHE[0] < 300:
        return _CONFIG_CACHE[1]
    with CONFIG_PATH.open('r', encoding='utf-8') as f:
        cfg = json.load(f)
    _CONFIG_CACHE = (now, cfg)
    return cfg
def get_group(chat_id: str, cfg: dict[str, Any] | None = None) -> dict[str, Any] | None:
    cfg = cfg or load_config()
    return (cfg.get('groups') or {}).get(chat_id)
