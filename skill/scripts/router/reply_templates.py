from __future__ import annotations
def submission_success(*, code: str, name: str, price: str, qty: str, amount: str, submitted_at: str, reviewer_at: str = '') -> str:
    return '\n'.join([
        '✅ 计件数据已成功提交！', '', '📋 提交详情：', f'- 📊编码：{code}', f'- 姓名：{name}', f'- 单价：{price} 元', f'- 数量：{qty} 件', f'- 金额：{amount} 元', f'- 提交时间：{submitted_at}', '', f'📝 当前状态：待审核{reviewer_at}', '🔔 审核员将在工作时间内处理您的申请。'
    ])

_CANCEL_FAIL_TEXT = {
    'not_found': '未找到该编码的记录，请核对编码后重试',
    'already_cancelled': '该记录已是「已取消」状态，无需重复取消',
    'already_reviewed': '该记录已审核（通过/拒绝），无法取消，请联系审核员处理',
    'not_owner': '只能取消本人提交的记录，如需处理请联系审核员',
    'no_pending': '当前没有待审核记录可取消',
    'cancel_no_code': '请带上要取消的编码，例如「取消 001」',
}
def cancel_item_failed(reason: str) -> str:
    return _CANCEL_FAIL_TEXT.get(reason, '取消失败，请稍后重试或联系管理员')
def cancel_success(*, code: str, name: str, price: str, qty: str, amount: str, cancelled_at: str, operator: str = '') -> str:
    return '\n'.join([
        '🚫 计件记录已取消！', '', '📋 取消详情：',
        f'- 📊编码：{code}',
        f'- 姓名：{name}',
        f'- 单价：{price or "-"} 元',
        f'- 数量：{qty or "-"} 件',
        f'- 金额：{amount or "0.00"} 元',
        f'- 取消时间：{cancelled_at}',
        f'- 操作人：{operator or name}',
        '', '📝 该记录已标记为「已取消」，不再计入工资统计，请重新提交正确的记录。',
    ])
def cancel_batch_header(*, cancelled: int, failed: int) -> str:
    head = '🚫 取消操作完成！' if cancelled else '❌ 取消操作未执行！'
    return '\n'.join([head, '', f'📋 处理结果：成功 {cancelled} 条 | 失败 {failed} 条'])
