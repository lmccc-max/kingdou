from __future__ import annotations
from decimal import Decimal
from datetime import datetime
from .feishu_client import FeishuClient
from .field_utils import field_str, money
from .validators import is_reviewer, name_of
def handle_query(chat_id, sender_id, text, decision, cfg, group, dry_run, send_reply):
    emp = (group.get('employee_list') or [''])[0]
    if sender_id != emp and not is_reviewer(sender_id, group, cfg): return {'ok': False, 'executed': False, 'reason': 'query_permission_denied'}
    if dry_run: return {'ok': True, 'executed': True, 'reason': 'dry_run_no_api'}
    c = FeishuClient(); emp_name = name_of(emp, cfg)
    today = datetime.now().strftime('%Y-%m-%d')
    total = Decimal('0'); approved = pending = rejected = cancelled = 0
    for x in c.list_records(group['app_token'], group['table_id']):
        f = x.get('fields', {})
        if field_str(f.get('姓名')) != emp_name: continue
        date_time_val = f.get('日期/时间', '')
        if not date_time_val: continue
        try:
            ts_ms = int(date_time_val)
            dt = datetime.fromtimestamp(ts_ms / 1000)
            if dt.strftime('%Y-%m-%d') != today: continue
        except (ValueError, TypeError): continue
        st = field_str(f.get('审核状态')) or '待审核'; amt = money(f.get('金额'))
        if '通过' in st:
            approved += 1
            try: total += Decimal(amt)
            except Exception: pass
        elif '取消' in st: cancelled += 1
        elif '拒绝' in st: rejected += 1
        else: pending += 1
    tail = f'\n🚫 已取消：{cancelled} 条' if cancelled else ''
    msg = f'📊 {emp_name} 今日计件统计：\n\n💰 总计金额：{total:.2f} 元\n✅ 已通过：{approved} 条\n⏳ 待审核：{pending} 条\n❌ 已拒绝：{rejected} 条' + tail
    mid = c.send_text(chat_id, msg) if send_reply else ''
    return {'ok': True, 'executed': True, 'reason': 'query_done', 'message_id': mid, 'cancelled': cancelled}
