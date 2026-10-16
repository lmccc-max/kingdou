#!/usr/bin/env python3
"""真实 Bitable 只读验证：走真实 FeishuClient 读取，但把 update_record/send_text 替换为
内存桩，绝不写入生产数据、不发飞书消息。用于确认 search_by_code、字段名、消息模板在真实数据上可用。

运行：
  cd ~/.hermes/skills/kingdou/scripts && \
  PYTHONPATH=. $KINDOU_PY tests/verify_cancel_real_readonly.py
"""
from __future__ import annotations
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from router import cancel_piecework as cp
from router.config_loader import load_config
from router.feishu_client import FeishuClient
from router.field_utils import field_str, code_of
from router.message_parser import parse_message

Real = FeishuClient
captured_sends = []
captured_updates = []


class ReadOnlyClient(Real):
    """继承真实 token/读取能力，屏蔽一切写操作与发送"""
    def update_record(self, app_token, table_id, record_id, fields):
        captured_updates.append({'record_id': record_id, 'fields': fields})
        return {'record_id': record_id, 'fields': fields}

    def send_text(self, chat_id, text):
        captured_sends.append(text)
        return 'STUB_MESSAGE_ID'


cp.FeishuClient = ReadOnlyClient
cfg = load_config()

for chat_id, group in (cfg.get('groups') or {}).items():
    emp = (group.get('employee_list') or [''])[0]
    if not emp:
        continue
    try:
        rows = Real().list_records(group['app_token'], group['table_id'])
    except Exception as e:
        print(f'{group.get("name") or chat_id}: 读取失败 {e}')
        continue
    pending = [r for r in rows if '待审核' in field_str(r.get('fields', {}).get('审核状态')) or not field_str(r.get('fields', {}).get('审核状态'))]
    print(f'== {group.get("name") or chat_id} | 总记录 {len(rows)} | 待审核 {len(pending)}')

    if not pending:
        continue
    target = pending[0]
    code = code_of(target)
    decision = parse_message(f'取消 {code}', group.get('name', ''))

    captured_sends.clear(); captured_updates.clear()
    res = cp.handle_cancel(chat_id, emp, f'取消 {code}', decision, cfg, group, False, True)
    owner = field_str(target.get('fields', {}).get('姓名'))
    emp_name = (cfg.get('openid_name_mapping') or {}).get(emp)
    print(f'   解析: {decision.route_type.value} codes={decision.payload.get("codes")}')
    print(f'   记录编码={code} 姓名={owner} 员工姓名={emp_name} → 结果 {res["reason"]}')
    if captured_updates:
        f = captured_updates[0]['fields']
        print(f'   将写入字段: 审核状态={f["审核状态"]!r} 单价={f["单价"]} 数量={f["数量"]} 备注={f["备注"]!r}')
        print(f'   消息预览:\n' + '\n'.join('     ' + ln for ln in captured_sends[0].splitlines()))
    else:
        print(f'   未写入（无权限/记录状态不符），提示：{captured_sends[0] if captured_sends else "(无消息)"}')

print('\n注意：以上为只读验证，未写入任何数据、未发送任何飞书消息。')
