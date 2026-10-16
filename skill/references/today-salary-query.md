# 工资查询处理模式（今日/昨日/本月）

## 场景描述

用户发送"今天我得多少钱"、"今天工资"、"昨天工资"、"本月工资"等查询指令，需要返回指定时间段所有计件记录的详细统计。

## 触发词

| 触发词 | 示例 |
|--------|------|
| `今天我得多少钱` | 今天我得多少钱 |
| `今天工资` | 今天工资 |
| `昨天工资` | 昨天工资 |
| `本月工资` | 本月工资 |
| `查工资` | 查工资 |
| `工资查询` | 工资查询 |
| `历史工资` | 历史工资 |

## 配置来源优先级

1. **中央配置**：`~/.hermes/skills/kingdou/configs/piecework-groups.json`
2. **独立群配置**：`~/.hermes/piecework/groups/<chat_id>/config.json`
   - 包含 `piecework_table` URL，格式：`https://xxx.feishu.cn/wiki/<wiki_token>?table=<table_id>`
   - **wiki_token 可直接用作 app_token**，无需转换

## ⚠️ 重要发现（2026-06-03）

`query_salary.py` 中的 `handle_query` 函数**不自动按日期过滤**，返回该员工所有记录。要查询今日工资，必须：
1. 手动获取所有记录
2. 按日期字段过滤
3. 格式化输出

推荐使用专用脚本：`scripts/query-today-salary.py`

## 处理流程

```
1. 识别查询意图
   - 匹配触发词
   - 确定时间段（today/yesterday/month）

2. 加载群配置
   - 先查中央配置
   - 不存在则查独立群配置文件
   - 从 piecework_table URL 解析 wiki_token（用作 app_token）和 table_id

3. 获取目标日期
   - today: datetime.now().strftime('%Y-%m-%d')
   - yesterday: (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')
   - month: 筛选当月所有记录

4. 查询所有记录
   - 调用飞书 Bitable API 获取表格所有记录
   - 分页查询（page_size=500）
   - API: GET /bitable/v1/apps/{wiki_token}/tables/{table_id}/records

5. 筛选目标日期记录
   - 解析每条记录的「日期/时间」字段
   - 毫秒时间戳转换为秒：ts_ms / 1000
   - 格式化为 YYYY-MM-DD
   - 匹配目标日期

6. 解析记录详情
   - 编码：AutoNumber 字段
   - 单价/数量：直接获取数值
   - 金额：公式字段结果
   - 审核状态：字符串，格式如「已通过 2026-06-03 01:26」
     - 包含状态和审核时间，用空格分隔
     - 判断状态用 `if '已通过' in status`

7. 统计汇总
   - 已通过记录数及金额
   - 待审核记录数及金额
   - 已拒绝记录数及金额
   - 总计金额（仅计算已通过）

8. 生成回复
   - 列表格式展示明细
   - 显示统计汇总
   - 标注每条记录的状态
```

## 推荐使用方式

使用专用脚本查询今日工资：

```bash
# 预览今日工资（不发送到群）
PYTHONPATH=~/.hermes/skills/kingdou/scripts \
$KINDOU_PY \
~/.hermes/skills/kingdou/scripts/query-today-salary.py oc_xxx

# 查询并发送到群
PYTHONPATH=~/.hermes/skills/kingdou/scripts \
$KINDOU_PY \
~/.hermes/skills/kingdou/scripts/query-today-salary.py oc_xxx --send
```

脚本输出包含：
- 查询摘要（员工、日期、记录数）
- 各状态统计（已通过/待审核/已拒绝）
- 总金额
- 预览或发送的消息内容

## 代码示例

```python
import os
import requests
from datetime import datetime

def query_today_salary(app_token, table_id, employee_name):
    # 获取token
    token = get_tenant_token()
    
    # 查询所有记录
    query_url = f"https://open.feishu.cn/open-apis/bitable/v1/apps/{app_token}/tables/{table_id}/records"
    headers = {"Authorization": f"Bearer {token}"}
    
    all_records = []
    page_token = None
    
    while True:
        params = {"page_size": 500}
        if page_token:
            params["page_token"] = page_token
        
        resp = requests.get(query_url, headers=headers, params=params)
        result = resp.json()
        
        if result.get("code") != 0:
            break
        
        items = result["data"].get("items", [])
        all_records.extend(items)
        
        page_token = result["data"].get("page_token")
        if not page_token:
            break
    
    # 获取今日日期
    today = datetime.now().strftime('%Y-%m-%d')
    
    # 筛选今日记录
    today_records = []
    for record in all_records:
        fields = record.get("fields", {})
        
        # 解析日期时间
        date_time_val = fields.get('日期/时间', '')
        if date_time_val:
            try:
                ts_ms = int(date_time_val)
                ts = ts_ms / 1000
                dt = datetime.fromtimestamp(ts)
                record_date = dt.strftime('%Y-%m-%d')
                submit_time = dt.strftime('%Y-%m-%d %H:%M')
            except:
                continue
        else:
            continue
        
        # 只统计今天的记录
        if record_date == today:
            code = parse_field(fields.get('编码', ''))
            unit_price = fields.get('单价', 0)
            quantity = fields.get('数量', 0)
            amount = parse_amount(fields.get('金额', 0))
            status = parse_field(fields.get('审核状态', ''))
            
            today_records.append({
                'code': code,
                'unit_price': unit_price,
                'quantity': quantity,
                'amount': amount,
                'status': status,
                'submit_time': submit_time
            })
    
    # 按提交时间排序
    today_records.sort(key=lambda x: x['submit_time'])
    
    # 统计
    approved = [r for r in today_records if '已通过' in r['status']]
    pending = [r for r in today_records if '待审核' in r['status'] or not r['status']]
    rejected = [r for r in today_records if '已拒绝' in r['status']]
    
    approved_amount = sum(r['amount'] for r in approved)
    pending_amount = sum(r['amount'] for r in pending)
    rejected_amount = sum(r['amount'] for r in rejected)
    total_amount = approved_amount + pending_amount
    
    return {
        'records': today_records,
        'approved_count': len(approved),
        'pending_count': len(pending),
        'rejected_count': len(rejected),
        'approved_amount': approved_amount,
        'pending_amount': pending_amount,
        'rejected_amount': rejected_amount,
        'total_amount': total_amount
    }
```

## 回复模板

```
📊 {employee_name} {today} 计件统计：

今日共 {total_count} 条记录：

| 编码 | 单价 | 数量 | 金额 | 时间 | 状态 |
|------|------|------|------|------|------|
| {code1} | {price1}元 | {qty1}件 | {amount1}元 | {time1} | {status1} |
| {code2} | {price2}元 | {qty2}件 | {amount2}元 | {time2} | {status2} |
| ... | ... | ... | ... | ... | ... |

💰 金额统计：
- ✅ 已通过：{approved_count}条，金额 {approved_amount:.2f}元
- ⏳ 待审核：{pending_count}条，金额 {pending_amount:.2f}元
- ❌ 已拒绝：{rejected_count}条，金额 {rejected_amount:.2f}元

💵 总计金额：{total_amount:.2f}元
```

## 状态图标映射

| 状态 | 图标 |
|------|------|
| 已通过 | ✅ |
| 待审核/空 | ⏳ |
| 已拒绝 | ❌ |

## 注意事项

1. **时间戳处理**：飞书返回毫秒级时间戳，必须除以1000转换为秒
2. **金额解析**：公式字段可能返回字典或数组，需要特殊处理
3. **状态判断**：空字符串也视为待审核状态
4. **排序**：按提交时间升序排列，便于用户查看时间线
5. **频率限制**：当日查询每日限额3次/人
6. **重要：handle_query 不按日期过滤**：`query_salary.py` 中的 `handle_query` 函数返回该员工所有记录，不自动按日期过滤。要查询今日工资，必须手动过滤或使用专用脚本 `scripts/query-today-salary.py`