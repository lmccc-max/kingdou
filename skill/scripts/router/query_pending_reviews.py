from __future__ import annotations
from .feishu_client import FeishuClient
from .field_utils import field_str, money, code_of
from .validators import is_reviewer
def handle_pending(chat_id, sender_id, text, decision, cfg, group, dry_run, send_reply):
    if not is_reviewer(sender_id, group, cfg): return {'ok': False, 'executed': False, 'reason': 'sender_not_in_reviewer_list'}
    if dry_run: return {'ok': True, 'executed': True, 'reason': 'dry_run_no_api'}
    c = FeishuClient(); rows = [x for x in c.list_records(group['app_token'], group['table_id']) if '待审核' in field_str(x.get('fields', {}).get('审核状态')) or not field_str(x.get('fields', {}).get('审核状态'))]
    if rows:
        lines = [f'- 📊编码：{code_of(x)} | 姓名：{field_str(x.get("fields", {}).get("姓名"))} | 单价：{field_str(x.get("fields", {}).get("单价"))} 元 | 数量：{field_str(x.get("fields", {}).get("数量"))} 件 | 金额：{money(x.get("fields", {}).get("金额"))} 元' for x in rows[:30]]
        msg = '⏳ 待审核计件记录：\n' + '\n'.join(lines)
    else: msg = '当前没有待审核计件记录。'
    mid = c.send_text(chat_id, msg) if send_reply else ''
    return {'ok': True, 'executed': True, 'reason': 'pending_listed', 'message_id': mid, 'count': len(rows)}
