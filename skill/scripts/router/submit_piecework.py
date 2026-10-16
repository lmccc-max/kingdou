from __future__ import annotations
import time
from decimal import Decimal
from .feishu_client import FeishuClient
from .field_utils import now_str, code_of
from .reply_templates import submission_success
from .validators import employee_for_submit, name_of, reviewer_ids

def _get_record_with_retry(c: FeishuClient, app_token: str, table_id: str, rid: str, max_retries: int = 3) -> dict | None:
    """获取记录并重试，确保AutoNumber字段已生成"""
    for attempt in range(max_retries):
        wait_time = 0.3 * (attempt + 1)  # 递增等待时间: 0.3s, 0.6s, 0.9s
        time.sleep(wait_time)
        full = c.get_record(app_token, table_id, rid)
        if full and full.get('fields', {}).get('编码') is not None:
            return full
    return None

def handle_submit(chat_id, sender_id, text, decision, cfg, group, dry_run, send_reply):
    emp = employee_for_submit(sender_id, group, cfg)
    if not emp: return {'ok': False, 'executed': False, 'reason': 'sender_not_in_employee_list'}
    name = name_of(emp, cfg) or '未知'; price = decision.payload['unit_price']; qty = decision.payload['quantity']; amount = Decimal(price) * Decimal(qty)
    if dry_run: return {'ok': True, 'executed': True, 'reason': 'dry_run_no_write'}
    c = FeishuClient(); record = c.create_record(group['app_token'], group['table_id'], {'姓名': name, '单价': float(price), '数量': float(qty), '审核状态': '待审核'})
    rid = record.get('record_id', '')
    full = _get_record_with_retry(c, group['app_token'], group['table_id'], rid) if rid else None
    if full: record = full
    reviewers = reviewer_ids(group, cfg); rvid = reviewers[0] if reviewers else ''; rname = name_of(rvid, cfg) if rvid else ''
    at = f' {rname}' if rname else ''
    msg = submission_success(code=code_of(record), name=name, price=price, qty=qty, amount=f'{amount:.2f}', submitted_at=now_str(), reviewer_at=at)
    mid = c.send_text(chat_id, msg) if send_reply else ''
    return {'ok': True, 'executed': True, 'reason': 'submitted', 'message_id': mid, 'record_code': code_of(record)}
