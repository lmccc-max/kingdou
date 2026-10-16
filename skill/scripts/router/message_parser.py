from __future__ import annotations
import re
from dataclasses import dataclass
from decimal import Decimal
from enum import Enum
from typing import Any
class RouteType(Enum):
    SUBMIT = 'submit'
    REVIEW = 'review'
    PENDING_REVIEW = 'pending_review'
    CANCEL = 'cancel'
    QUERY = 'query'
    UNKNOWN = 'unknown'
@dataclass
class RouteDecision:
    route_type: RouteType
    reason: str
    group_name: str = ''
    payload: dict[str, Any] | None = None
_NUM = r'(?:\d+(?:\.\d+)?|\.\d+)'
_SUBMIT_RE = re.compile(rf'^\s*({_NUM})\s+({_NUM})\s*$')
_REVIEW_RE = re.compile(r'^\s*(同意|通过|审核通过|approve|拒绝|不同意|审核拒绝|reject)\s*(全部|all|[A-Za-z]*\d+(?:\s*[-,，、\s]\s*[A-Za-z]*\d+)*)?\s*(.*)$', re.I)
_REVIEW_REVERSE_RE = re.compile(r'^\s*(全部|all)\s*(同意|通过|审核通过|approve|拒绝|不同意|审核拒绝|reject)\s*(.*)$', re.I)
_RANGE_RE = re.compile(r'^(\D*?)(\d+)\s*-\s*(\D*?)(\d+)$')
_CANCEL_RE = re.compile(r'^\s*(取消|撤销|作废|撤回)\s*(.*)$')
_CANCEL_REVERSE_RE = re.compile(r'^\s*(全部|all)\s*(取消|撤销|作废|撤回)\s*(.*)$')
def codes_from_text(s: str | None) -> list[str]:
    if not s: return []
    s = s.strip()
    if s.lower() == 'all' or s == '全部': return ['ALL']
    m = _RANGE_RE.match(s)
    if m and m.group(1) == m.group(3):
        a, b = int(m.group(2)), int(m.group(4))
        if 0 <= b - a <= 100: return [f'{m.group(1)}{i}' for i in range(a, b + 1)]
    return re.findall(r'[A-Za-z]*\d+', s)
def parse_message(text: str, group_name: str = '') -> RouteDecision:
    raw = (text or '').strip()
    m = _SUBMIT_RE.match(raw)
    if m:
        price = Decimal(m.group(1)); qty = Decimal(m.group(2))
        if price > 0 and qty > 0:
            return RouteDecision(RouteType.SUBMIT, 'two_numbers', group_name, {'unit_price': str(price), 'quantity': str(qty)})
        return RouteDecision(RouteType.UNKNOWN, 'non_positive_submit', group_name)
    if re.search(r'(待审核|查看待审核|未审核|待处理)', raw):
        return RouteDecision(RouteType.PENDING_REVIEW, 'pending_keyword', group_name, {})
    m = _CANCEL_RE.match(raw)
    if not m:
        m = _CANCEL_REVERSE_RE.match(raw)
    if m:
        reverse = m.re is _CANCEL_REVERSE_RE
        rest = ((m.group(3) if reverse else m.group(2)) or '').strip()
        codes = codes_from_text(rest)
        if reverse and not codes: codes = ['ALL']
        # 仅当确为取消指令（带编码 / 全部 / 光秃秃的「取消」）才拦截，
        # 其它以「取消…」开头的自然语言（如「取消的话怎么办」）放行给 AI。
        if codes or not rest:
            return RouteDecision(RouteType.CANCEL, 'cancel_keyword', group_name, {'codes': codes})
    m = _REVIEW_RE.match(raw)
    if m:
        word = m.group(1).lower(); codes = codes_from_text(m.group(2)); reason = (m.group(3) or '').strip()
        if codes:
            action = 'reject' if word in {'拒绝', '不同意', '审核拒绝', 'reject'} else 'approve'
            return RouteDecision(RouteType.REVIEW, 'review_keyword', group_name, {'action': action, 'codes': codes, 'reason': reason})
    m = _REVIEW_REVERSE_RE.match(raw)
    if m:
        word = m.group(2).lower(); codes = codes_from_text(m.group(1)); reason = (m.group(3) or '').strip()
        if codes:
            action = 'reject' if word in {'拒绝', '不同意', '审核拒绝', 'reject'} else 'approve'
            return RouteDecision(RouteType.REVIEW, 'review_keyword', group_name, {'action': action, 'codes': codes, 'reason': reason})
    if re.search(r'(查工资|工资查询|今天工资|本月工资|历史工资|昨日工资|昨天工资)', raw):
        period = 'today'
        if '本月' in raw: period = 'month'
        elif '历史' in raw: period = 'history'
        elif '昨天' in raw or '昨日' in raw: period = 'yesterday'
        return RouteDecision(RouteType.QUERY, 'query_keyword', group_name, {'period': period})
    return RouteDecision(RouteType.UNKNOWN, 'no_match', group_name)
_codes = codes_from_text
