#!/usr/bin/env python3
"""
Query today's piecework salary for a specific group.
Filters records by today's date and formats the output.

Usage:
  python3 query-today-salary.py <chat_id> [--send]

Example:
  python3 query-today-salary.py oc_example_group
  python3 query-today-salary.py oc_example_group --send
"""
import sys
import json
from pathlib import Path
from datetime import datetime
from decimal import Decimal

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from router.feishu_client import FeishuClient
from router.field_utils import field_str, money, code_of
from router.validators import name_of
from router.config_loader import load_config


def query_today_salary(chat_id: str, send: bool = False) -> dict:
    """
    Query today's piecework salary for a specific group.
    
    Args:
        chat_id: Feishu group chat ID
        send: Whether to send the message to the group
        
    Returns:
        dict with query results and formatted message
    """
    # Load config
    cfg = load_config()
    
    # Get group config
    group = cfg['groups'].get(chat_id)
    if not group:
        return {'ok': False, 'error': f'Group {chat_id} not found in config'}
    
    # Get employee info
    emp = (group.get('employee_list') or [''])[0]
    if not emp:
        return {'ok': False, 'error': 'No employee configured for this group'}
    
    emp_name = name_of(emp, cfg)
    
    # Get today's date
    today = datetime.now().strftime('%Y-%m-%d')
    
    # Query records
    c = FeishuClient()
    all_records = []
    for x in c.list_records(group['app_token'], group['table_id']):
        f = x.get('fields', {})
        if field_str(f.get('姓名')) == emp_name:
            all_records.append(x)
    
    # Filter today's records
    today_records = []
    for x in all_records:
        f = x.get('fields', {})
        date_time_val = f.get('日期/时间', '')
        if date_time_val:
            try:
                ts_ms = int(date_time_val)
                ts = ts_ms / 1000
                dt = datetime.fromtimestamp(ts)
                record_date = dt.strftime('%Y-%m-%d')
                if record_date == today:
                    today_records.append((x, dt.strftime('%Y-%m-%d %H:%M')))
            except (ValueError, TypeError):
                continue
    
    # Sort by submit time
    today_records.sort(key=lambda x: x[1])
    
    # Format output
    details = []
    total = Decimal('0')
    approved = pending = rejected = cancelled = 0
    
    for x, submit_time in today_records:
        f = x.get('fields', {})
        st = field_str(f.get('审核状态')) or '待审核'
        amt = money(f.get('金额'))
        
        if '通过' in st:
            approved += 1
            try:
                total += Decimal(amt)
            except Exception:
                pass
        elif '取消' in st:
            cancelled += 1
        elif '拒绝' in st:
            rejected += 1
        else:
            pending += 1
        
        details.append(f'- 📊编码：{code_of(x)} | 单价：{field_str(f.get("单价"))} | 数量：{field_str(f.get("数量"))} | 金额：{amt} | 状态：{st}')
    
    # Build message
    msg = '\n'.join([
        f'📊 {emp_name} 的计件统计（today）：',
        '',
        '\n'.join(details) if details else '暂无记录',
        '',
        f'💰 总计金额：{total:.2f} 元',
        f'✅ 已通过：{approved} 条',
        f'⏳ 待审核：{pending} 条',
        f'❌ 已拒绝：{rejected} 条'
    ])
    if cancelled:
        msg += f'\n🚫 已取消：{cancelled} 条'
    
    # Send if requested
    message_id = ''
    if send:
        message_id = c.send_text(chat_id, msg)
    
    return {
        'ok': True,
        'chat_id': chat_id,
        'employee_name': emp_name,
        'date': today,
        'total_records': len(all_records),
        'today_records': len(today_records),
        'approved': approved,
        'pending': pending,
        'rejected': rejected,
        'cancelled': cancelled,
        'total_amount': float(total),
        'message': msg,
        'message_id': message_id
    }


def main():
    if len(sys.argv) < 2:
        print("Usage: python3 query-today-salary.py <chat_id> [--send]")
        sys.exit(1)
    
    chat_id = sys.argv[1]
    send = '--send' in sys.argv
    
    result = query_today_salary(chat_id, send)
    
    if not result['ok']:
        print(f"Error: {result['error']}")
        sys.exit(1)
    
    # Print summary
    print(f"Query completed for {result['employee_name']}")
    print(f"Date: {result['date']}")
    print(f"Total records: {result['total_records']}")
    print(f"Today records: {result['today_records']}")
    print(f"Approved: {result['approved']}")
    print(f"Pending: {result['pending']}")
    print(f"Rejected: {result['rejected']}")
    print(f"Cancelled: {result['cancelled']}")
    print(f"Total amount: {result['total_amount']:.2f} 元")
    
    if send:
        print(f"Message sent: {result['message_id']}")
    else:
        print("\n--- Message Preview ---")
        print(result['message'])


if __name__ == '__main__':
    main()
