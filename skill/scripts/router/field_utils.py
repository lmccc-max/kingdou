from __future__ import annotations
from datetime import datetime
from decimal import Decimal
from typing import Any
def field_str(v: Any) -> str:
    if isinstance(v, list): return field_str(v[0]) if len(v) == 1 else ','.join(field_str(x) for x in v)
    if isinstance(v, dict):
        for k in ('text', 'name', 'value'):
            if k in v: return field_str(v[k])
    return '' if v is None else str(v)
def field_num(v: Any) -> float | int | None:
    """从飞书字段值中提取真实数值，失败返回 None"""
    if v is None: return None
    if isinstance(v, (int, float)): return v
    if isinstance(v, dict):
        for k in ('value', 'number', 'text'):
            if k in v: return field_num(v[k])
    if isinstance(v, list):
        return field_num(v[0]) if v else None
    if isinstance(v, str):
        v = v.strip()
        if not v: return None
        try: return int(v)
        except ValueError:
            try: return float(v)
            except ValueError: return None
    return None

def money(v: Any) -> str:
    try: return f'{Decimal(field_str(v)):.2f}'
    except Exception: return '未计算'
def now_str() -> str: return datetime.now().strftime('%Y-%m-%d %H:%M')
def code_of(record: dict[str, Any]) -> str:
    # 处理AutoNumber字段，可能是数字或字符串
    编码 = record.get('fields', {}).get('编码')
    if 编码 is not None:
        # AutoNumber字段返回数字，转换为字符串
        if isinstance(编码, (int, float)):
            return str(int(编码))
        # 如果是字符串，直接返回
        s = field_str(编码)
        if s:
            return s
    # 回退到record_id
    return field_str(record.get('record_id'))
