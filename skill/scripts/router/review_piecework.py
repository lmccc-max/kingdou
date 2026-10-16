from __future__ import annotations
from .feishu_client import FeishuClient
from .field_utils import field_str, field_num, money, now_str, code_of
from .validators import is_reviewer, name_of
def handle_review(chat_id, sender_id, text, decision, cfg, group, dry_run, send_reply):
    if not is_reviewer(sender_id, group, cfg): return {'ok': False, 'executed': False, 'reason': 'sender_not_in_reviewer_list'}
    action = decision.payload['action']; codes = decision.payload['codes']
    if dry_run: return {'ok': True, 'executed': True, 'reason': 'dry_run_no_api', 'action': action, 'codes': codes}
    c = FeishuClient(); targets = []
    if codes == ['ALL']:
        targets = [x for x in c.list_records(group['app_token'], group['table_id']) if '待审核' in field_str(x.get('fields', {}).get('审核状态')) or not field_str(x.get('fields', {}).get('审核状态'))]
    else:
        for code in codes:
            item = c.search_by_code(group['app_token'], group['table_id'], code)
            if item: targets.append(item)
    if not targets: return {'ok': False, 'executed': False, 'reason': 'record_not_found'}
    reviewer = name_of(sender_id, cfg) or ''; updated = []
    for item in targets:
        rid = item.get('record_id'); fields = {'审核状态': f'{"已通过" if action == "approve" else "已拒绝"} {now_str()}', '审核人': reviewer}
        if action == 'reject': fields.update({'单价': None, '数量': None})
        c.update_record(group['app_token'], group['table_id'], rid, fields)
        import time; time.sleep(0.5)
        rec = c.get_record(group['app_token'], group['table_id'], rid) or item; updated.append(rec)
    title = '✅ 计件记录已审核通过！' if action == 'approve' else '❌ 计件记录审核未通过！'
    lines = []
    for r in updated:
        f = r.get('fields', {})
        p = field_num(f.get('单价')); q = field_num(f.get('数量')); a = field_num(f.get('金额'))
        price_s = f'{p}' if p is not None else ''
        qty_s = f'{q}' if q is not None else ''
        amt_s = f'{a:.2f}' if a is not None else (f'{p * q:.2f}' if p is not None and q is not None else '未计算')
        lines.append(f'- 📊编码：{code_of(r)} | 单价：{price_s} 元 | 数量：{qty_s} 件 | 金额：{amt_s} 元 | 审核时间：{now_str()} | 审核人：{reviewer}')
    msg = title + '\n\n📋 审核详情：\n' + '\n'.join(lines)
    mid = c.send_text(chat_id, msg) if send_reply else ''
    return {'ok': True, 'executed': True, 'reason': action + 'd', 'message_id': mid, 'count': len(updated)}
