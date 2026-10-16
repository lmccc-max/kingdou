from __future__ import annotations
from typing import Any
def name_of(openid: str, cfg: dict[str, Any]) -> str:
    return (cfg.get('openid_name_mapping') or {}).get(openid, '')
def is_admin(openid: str, cfg: dict[str, Any]) -> bool:
    return openid in set(cfg.get('global_admins') or [])
def is_reviewer(openid: str, group: dict[str, Any], cfg: dict[str, Any]) -> bool:
    return is_admin(openid, cfg) or openid in set(group.get('independent_admins') or [])
def reviewer_ids(group: dict[str, Any], cfg: dict[str, Any]) -> list[str]:
    ids = list(group.get('independent_admins') or [])
    return ids or list(cfg.get('global_admins') or [])
def employee_for_submit(sender_id: str, group: dict[str, Any], cfg: dict[str, Any]) -> str | None:
    employees = list(group.get('employee_list') or [])
    if sender_id in employees: return sender_id
    if is_admin(sender_id, cfg) and employees: return employees[0]
    return None
