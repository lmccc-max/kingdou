from __future__ import annotations
"""员工取消自己的计件记录（发错记录时使用）。

触发：`取消 001` / `取消001` / `撤销 001-003` / `取消全部`（仅审核员/管理员）
规则：
- 员工只能取消「本人姓名」且状态为「待审核」的记录
- 审核员/管理员可取消本群任意待审核记录，并可 `取消全部`
- 已通过/已拒绝的纪录不可取消（需审核员用「拒绝」处理）
- 取消为软取消：状态改「已取消 <时间>」、数量清0（金额公式随之归零）、备注=操作人姓名（留痕）
"""
from .feishu_client import FeishuClient
from .field_utils import field_str, code_of, now_str
from .reply_templates import cancel_success, cancel_batch_header, cancel_item_failed
from .validators import employee_for_submit, is_reviewer, name_of


def _pending(status: str) -> bool:
    """待审核（含状态为空的旧记录）"""
    return (not status) or ('待审核' in status)


def _cancelled(status: str) -> bool:
    return '取消' in status


def _finalised(status: str) -> bool:
    return ('通过' in status) or ('拒绝' in status)


def _find(c: FeishuClient, group: dict, code: str) -> dict | None:
    """按编码查找记录；兼容用户输入 001 / 1 / 56 等与表内编码（如 056）不一致的写法。"""
    app_token, table_id = group['app_token'], group['table_id']
    item = c.search_by_code(app_token, table_id, code)
    if item is None and str(code).isdigit():
        item = c.search_by_code(app_token, table_id, str(int(code)))
    if item is None and str(code).isdigit():
        want = int(code)
        for x in c.list_records(app_token, table_id):
            v = field_str(x.get('fields', {}).get('编码')).strip()
            if v.isdigit() and int(v) == want:
                item = x
                break
    return item


def _cancel_record(c: FeishuClient, group: dict, item: dict, actor: str) -> dict:
    """软取消：审核状态=已取消+时间，数量清0（金额公式随之归零），备注=发送命令的员工名字。

    金额为公式字段（单价×数量），无法直接写入；数量置 0 即令金额归零。
    单价保留原值不动。
    """
    fields = {
        '审核状态': f'已取消 {now_str()}',
        '审核人': actor,
        '备注': actor,
        '数量': 0,
    }
    c.update_record(group['app_token'], group['table_id'], item.get('record_id'), fields)
    return item


def _send(c: FeishuClient, chat_id: str, msg: str, send_reply: bool) -> str:
    return c.send_text(chat_id, msg) if send_reply else ''


def _fmt_amount(v) -> str:
    try:
        return f'{float(field_str(v)):.2f}'
    except (TypeError, ValueError):
        return '0.00'


def handle_cancel(chat_id, sender_id, text, decision, cfg, group, dry_run, send_reply):
    is_rev = is_reviewer(sender_id, group, cfg)
    emp = employee_for_submit(sender_id, group, cfg)
    if not emp and not is_rev:
        return {'ok': False, 'executed': False, 'reason': 'sender_not_in_employee_list'}

    codes = list(decision.payload.get('codes') or [])
    actor = name_of(sender_id, cfg) or (name_of(emp, cfg) if emp else '')

    if not codes:
        msg = cancel_item_failed('cancel_no_code')
        mid = _send(FeishuClient(), chat_id, msg, send_reply)
        return {'ok': True, 'executed': True, 'reason': 'cancel_no_code', 'message_id': mid}

    if codes == ['ALL']:
        if not is_rev:
            return {'ok': False, 'executed': False, 'reason': 'cancel_all_requires_reviewer'}
    elif dry_run:
        return {'ok': True, 'executed': True, 'reason': 'dry_run_no_api', 'codes': codes, 'operator': actor}

    c = FeishuClient()
    targets: list[tuple[str, dict]] = []
    failures: list[tuple[str, str]] = []

    if codes == ['ALL']:
        for x in c.list_records(group['app_token'], group['table_id']):
            if _pending(field_str(x.get('fields', {}).get('审核状态'))):
                targets.append((code_of(x), x))
        if not targets:
            failures.append(('ALL', 'no_pending'))
    else:
        for code in codes:
            item = _find(c, group, code)
            if not item:
                failures.append((code, 'not_found')); continue
            f = item.get('fields', {}) or {}
            status = field_str(f.get('审核状态'))
            owner = field_str(f.get('姓名'))
            if _cancelled(status):
                failures.append((code, 'already_cancelled')); continue
            if _finalised(status) or not _pending(status):
                failures.append((code, 'already_reviewed')); continue
            if not is_rev and actor and owner and owner != actor:
                failures.append((code, 'not_owner')); continue
            targets.append((code_of(item), item))

    if dry_run:
        return {'ok': True, 'executed': False, 'reason': 'dry_run_no_api',
                'codes': codes, 'targets': [t[0] for t in targets], 'failures': failures}

    cancelled: list[dict] = []
    for code, item in targets:
        rec = _cancel_record(c, group, item, actor)
        rec.setdefault('fields', {})['编码'] = rec.get('fields', {}).get('编码') or code
        cancelled.append(rec)

    if not cancelled and not failures:
        msg = '当前没有待审核记录可取消。'
    elif len(codes) == 1 and len(cancelled) == 1 and not failures:
        r = cancelled[0]; f = r.get('fields', {}) or {}
        msg = cancel_success(
            code=code_of(r), name=field_str(f.get('姓名')) or actor,
            price=field_str(f.get('单价')), qty=field_str(f.get('数量')),
            amount=_fmt_amount(f.get('金额')), cancelled_at=now_str(), operator=actor,
        )
    elif not cancelled and failures == [('ALL', 'no_pending')]:
        msg = '当前没有待审核记录可取消。'
    else:
        lines = []
        for r in cancelled:
            f = r.get('fields', {}) or {}
            lines.append(f'- ✅ 编码：{code_of(r)} | 姓名：{field_str(f.get("姓名")) or "-"} | 已取消')
        for code, reason in failures:
            lines.append(f'- ❌ 编码：{code} | {cancel_item_failed(reason)}')
        msg = cancel_batch_header(cancelled=len(cancelled), failed=len(failures)) + '\n' + '\n'.join(lines)

    mid = _send(c, chat_id, msg, send_reply)
    return {'ok': True, 'executed': True,
            'reason': 'cancelled' if cancelled else (failures[0][1] if failures else 'nothing_to_do'),
            'message_id': mid, 'count': len(cancelled), 'failed': len(failures)}
