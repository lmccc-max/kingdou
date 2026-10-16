#!/usr/bin/env python3
"""取消功能回归测试：使用内存假 FeishuClient，不触碰生产数据、不发飞书消息。

运行：
  cd ~/.hermes/skills/kingdou/scripts && \
  PYTHONPATH=. $KINDOU_PY tests/test_cancel_piecework.py
"""
from __future__ import annotations
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from router import cancel_piecework as cp
from router.message_parser import RouteType, parse_message

EMP = 'ou_emp'
OTHER_EMP = 'ou_other'
ADMIN = 'ou_admin'

CFG = {
    'global_admins': [ADMIN],
    'openid_name_mapping': {EMP: '员工<11>', OTHER_EMP: '员工<12>', ADMIN: '管理员<03>'},
}
GROUP = {
    'name': '测试计件群',
    'app_token': 'app_x', 'table_id': 'tbl_x',
    'employee_list': [EMP],
    'independent_admins': [],
}


class FakeClient:
    """内存 Bitable 替身"""
    def __init__(self):
        self.records = [
            {'record_id': 'rec1', 'fields': {'编码': 1, '姓名': '员工<11>', '单价': 0.12, '数量': 100, '金额': 12.0, '审核状态': '待审核'}},
            {'record_id': 'rec2', 'fields': {'编码': 2, '姓名': '员工<12>', '单价': 1.0, '数量': 5, '金额': 5.0, '审核状态': '待审核'}},
            {'record_id': 'rec3', 'fields': {'编码': 3, '姓名': '员工<11>', '单价': 0.5, '数量': 10, '金额': 5.0, '审核状态': '已通过 2026-09-13 10:00'}},
            {'record_id': 'rec4', 'fields': {'编码': 4, '姓名': '员工<11>', '单价': 0.3, '数量': 2, '金额': 0.6, '审核状态': '已取消 2026-09-13 09:00'}},
        ]
        self.sent = []
        self.updates = []

    def search_by_code(self, app_token, table_id, code):
        for r in self.records:
            if str(r['fields'].get('编码')) == str(code):
                return dict(r, fields=dict(r['fields']))
        return None

    def list_records(self, app_token, table_id):
        return [dict(r, fields=dict(r['fields'])) for r in self.records]

    def update_record(self, app_token, table_id, record_id, fields):
        for r in self.records:
            if r['record_id'] == record_id:
                r['fields'].update(fields)
                self.updates.append((record_id, fields))
                return dict(r, fields=dict(r['fields']))
        raise AssertionError('record not found: ' + str(record_id))

    def get_record(self, app_token, table_id, record_id):
        for r in self.records:
            if r['record_id'] == record_id:
                return dict(r, fields=dict(r['fields']))
        return None

    def send_text(self, chat_id, text):
        self.sent.append(text)
        return 'msg_fake'


PASS, FAIL = [], []


def check(name, cond, detail=''):
    (PASS if cond else FAIL).append(name)
    print(f'{"✅" if cond else "❌"} {name}{"" if cond else " | " + str(detail)}')


def run(sender, text, dry_run=False):
    fake = FakeClient()
    cp.FeishuClient = lambda: fake
    d = parse_message(text, GROUP['name'])
    res = cp.handle_cancel('oc_x', sender, text, d, CFG, GROUP, dry_run, True)
    return fake, res, d


def rec(fake, rid):
    return next(r for r in fake.records if r['record_id'] == rid)


# ---------- 1. 解析 ----------
for text, codes in [('取消001', ['001']), ('取消 001', ['001']), ('撤销 5', ['5']),
                    ('作废 1-3', ['1', '2', '3']), ('取消全部', ['ALL']), ('全部取消', ['ALL'])]:
    d = parse_message(text, 'g')
    check(f'解析 {text} → cancel {codes}', d.route_type == RouteType.CANCEL and d.payload['codes'] == codes,
          f'{d.route_type} {d.payload}')
d = parse_message('取消', 'g')
check('解析「取消」无编码 → cancel []', d.route_type == RouteType.CANCEL and d.payload['codes'] == [])
d = parse_message('取消的话这个月怎么算', 'g')
check('自然语言「取消…」不误拦截 → unknown', d.route_type == RouteType.UNKNOWN, str(d))
d = parse_message('通过123', 'g')
check('回归：通过123 → review approve', d.route_type == RouteType.REVIEW and d.payload['action'] == 'approve', str(d))
d = parse_message('拒绝 9', 'g')
check('回归：拒绝 9 → review reject', d.route_type == RouteType.REVIEW and d.payload['action'] == 'reject', str(d))
d = parse_message('0.12 103', 'g')
check('回归：0.12 103 → submit', d.route_type == RouteType.SUBMIT, str(d))
d = parse_message('待审核', 'g')
check('回归：待审核 → pending_review', d.route_type == RouteType.PENDING_REVIEW, str(d))

# ---------- 2. 员工取消本人待审核记录 ----------
fake, res, d = run(EMP, '取消 001')
r1 = rec(fake, 'rec1')
check('员工取消本人待审核 → ok', res['ok'] and res['executed'] and res['reason'] == 'cancelled', res)
check('  → 审核状态=已取消+时间', str(r1['fields']['审核状态']).startswith('已取消 ') and len(str(r1['fields']['审核状态'])) > 5, r1['fields'])
check('  → 数量清0（金额公式归零）', r1['fields']['数量'] == 0, r1['fields'])
check('  → 单价保留原值不动', r1['fields']['单价'] == 0.12, r1['fields'])
check('  → 审核人=操作人 / 备注=发送命令的员工名字', r1['fields']['审核人'] == '员工<11>' and r1['fields']['备注'] == '员工<11>', r1['fields'])
check('  → 已发飞书消息且含编码', len(fake.sent) == 1 and '编码：1' in fake.sent[0] and '已取消' in fake.sent[0] and '12.00' in fake.sent[0], fake.sent)
check('  → 消息被网关拦截(ok&executed)', bool(res['ok'] and res['executed']))

# ---------- 3. 员工取消他人记录 ----------
fake, res, d = run(EMP, '取消 002')
check('员工取消他人记录 → 拒绝', not fake.updates and '只能取消本人' in fake.sent[0], (res, fake.sent))

# ---------- 4. 已通过/已取消 ----------
fake, res, d = run(EMP, '取消 003')
check('取消已通过记录 → 提示已审核', not fake.updates and '已审核' in fake.sent[0], fake.sent)
fake, res, d = run(EMP, '取消 004')
check('重复取消 → 提示已取消', not fake.updates and '无需重复取消' in fake.sent[0], fake.sent)

# ---------- 5. 不存在的编码 / 无编码 ----------
fake, res, d = run(EMP, '取消 999')
check('取消不存在编码 → 提示未找到', not fake.updates and '未找到' in fake.sent[0], fake.sent)
fake, res, d = run(EMP, '取消')
check('取消无编码 → 提示带编码且被拦截', res['ok'] and '例如' in fake.sent[0], (res, fake.sent))

# ---------- 6. 管理员权限 ----------
fake, res, d = run(ADMIN, '取消 002')
check('管理员取消他人记录 → 成功', '已取消' in str(rec(fake, 'rec2')['fields']['审核状态']), rec(fake, 'rec2')['fields'])
fake, res, d = run(ADMIN, '取消 003')
check('管理员取消已通过记录也拒绝(需用拒绝)', not fake.updates and '已审核' in fake.sent[0], fake.sent)

# ---------- 7. 批量 / 全部 ----------
fake, res, d = run(EMP, '取消 001 002')
check('批量部分失败 → 汇总消息', res['ok'] and res['count'] == 1 and res['failed'] == 1 and '成功 1 条' in fake.sent[0], (res, fake.sent))
fake, res, d = run(EMP, '取消全部')
check('员工「取消全部」→ 拒绝且不写入', not fake.updates and not res['ok'], (res, fake.sent))
fake, res, d = run(ADMIN, '取消全部')
check('管理员「取消全部」→ 仅取消待审核', rec(fake, 'rec1')['fields']['审核状态'].startswith('已取消')
      and rec(fake, 'rec2')['fields']['审核状态'].startswith('已取消')
      and rec(fake, 'rec3')['fields']['审核状态'].startswith('已通过')
      and res['count'] == 2, (res, [r['fields']['审核状态'] for r in fake.records]))

# ---------- 8. 无权限用户 ----------
fake, res, d = run('ou_stranger', '取消 001')
check('无关用户 → 拒绝且不发送', not fake.updates and not fake.sent and res['reason'] == 'sender_not_in_employee_list', res)

# ---------- 9. dry-run 不写入 ----------
fake, res, d = run(EMP, '取消 001', dry_run=True)
check('dry-run → 不写 Bitable 不发消息', not fake.updates and not fake.sent and res['reason'] == 'dry_run_no_api', res)

print(f'\n通过 {len(PASS)} / 失败 {len(FAIL)}')
if FAIL:
    print('失败项：' + ', '.join(FAIL))
sys.exit(1 if FAIL else 0)
