# 待审核查询操作指南

## 触发词与使用场景



- `待审核`
- `查看待审核`
- `待审核记录`

## 查询流程

### 1. 获取 Access Token

```bash
TOKEN=$(curl -s -X POST "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal" \
  -H "Content-Type: application/json" \
  -d "{
    \"app_id\": \"$FEISHU_APP_ID\",
    \"app_secret\": \"$FEISHU_APP_SECRET\"
  }" | grep -o '"tenant_access_token":"[^"]*"' | cut -d'"' -f4)
```

### 2. 查询表格记录

```bash
APP_TOKEN="<群的app_token>"
TABLE_ID="<群的table_id>"

curl -s -X GET "https://open.feishu.cn/open-apis/bitable/v1/apps/${APP_TOKEN}/tables/${TABLE_ID}/records?page_size=500" \
  -H "Authorization: Bearer ${TOKEN}"
```

### 3. 筛选待审核记录

**待审核状态判断逻辑**:
- 审核状态字段为空
- 审核状态包含"待审核"
- 审核状态包含"未审核"

**注意**: 不包含"已通过"或"已拒绝"的记录。

### 4. 字段解析

**编码字段** (AutoNumber):
```python
code_field = fields.get('编码', '')
if isinstance(code_field, list) and len(code_field) > 0:
    code = code_field[0].get('text', '') if isinstance(code_field[0], dict) else str(code_field[0])
else:
    code = str(code_field) if code_field else 'N/A'
```

**姓名字段** (Text):
```python
name_field = fields.get('姓名', [])
if isinstance(name_field, list) and len(name_field) > 0:
    name = name_field[0].get('text', '') if isinstance(name_field[0], dict) else str(name_field[0])
else:
    name = str(name_field) if name_field else '未知'
```

**数字字段** (单价/数量):
```python
qty = fields.get('数量', 0)
if isinstance(qty, dict):
    qty = qty.get('value', 0)

price = fields.get('单价', 0)
if isinstance(price, dict):
    price = price.get('value', 0)
```

**金额字段** (Formula):
```python
amount = fields.get('金额', 0)
if isinstance(amount, dict):
    amount = amount.get('value', 0)
elif isinstance(amount, list) and len(amount) > 0:
    amount = amount[0].get('text', '0') if isinstance(amount[0], dict) else str(amount[0])
    try:
        amount = float(amount)
    except:
        amount = 0
```

**日期时间字段** (CreatedTime):
```python
date_time = fields.get('日期/时间', 0)
if isinstance(date_time, (int, float)) and date_time > 1000000000000:
    # 毫秒时间戳，需要除以1000
    dt = datetime.fromtimestamp(date_time / 1000)
    submit_time = dt.strftime('%Y-%m-%d %H:%M')
else:
    submit_time = '未知'
```

## 标准回复格式

```
⏳ {group_name}待审核记录：

📋 待审核详情：
{pending_details}

💰 待审核总计金额：{total_amount} 元
📝 共 {pending_count} 条记录等待审核 @审核员
```

**pending_details 格式** (每条记录一行):
```
- 📊编码：{code} | 数量：{qty}件 | 单价：{price}元 | 金额：{amount}元 | 提交时间：{submit_time}
```

## 示例输出

```
⏳ 管理员<04>计件群待审核记录：

📋 待审核详情：
- 📊编码：198 | 数量：32件 | 单价：0.18元 | 金额：5.76元 | 提交时间：2025-05-05 13:21
- 📊编码：199 | 数量：32件 | 单价：0.80元 | 金额：25.60元 | 提交时间：2025-05-05 18:19
- 📊编码：200 | 数量：150件 | 单价：0.28元 | 金额：42.00元 | 提交时间：2025-05-05 18:21
- 📊编码：201 | 数量：50件 | 单价：0.80元 | 金额：40.00元 | 提交时间：2025-05-05 18:42

💰 待审核总计金额：113.36 元
📝 共 4 条记录等待审核 @审核员
```

## Python 完整示例

```python
import requests
import json
from datetime import datetime

def parse_field_value(field_value, default=''):
    """解析飞书Bitable字段值，处理富文本格式"""
    if isinstance(field_value, list) and len(field_value) > 0:
        if isinstance(field_value[0], dict) and 'text' in field_value[0]:
            return field_value[0]['text']
    return str(field_value) if field_value else default

def parse_number_field(field_value):
    """解析数字字段"""
    if isinstance(field_value, dict):
        return field_value.get('value', 0)
    try:
        return float(field_value)
    except:
        return 0

def parse_datetime_field(field_value):
    """解析日期时间字段（毫秒时间戳）"""
    if isinstance(field_value, (int, float)) and field_value > 1000000000000:
        dt = datetime.fromtimestamp(field_value / 1000)
        return dt.strftime('%Y-%m-%d %H:%M')
    return '未知'

def query_pending_records(app_token, table_id, tenant_access_token):
    """查询待审核记录"""
    url = f"https://open.feishu.cn/open-apis/bitable/v1/apps/{app_token}/tables/{table_id}/records"
    headers = {"Authorization": f"Bearer {tenant_access_token}"}
    
    response = requests.get(url, headers=headers, params={"page_size": 500})
    result = response.json()
    
    if result.get('code') != 0:
        return None, result.get('msg')
    
    items = result.get('data', {}).get('items', [])
    pending_records = []
    
    for item in items:
        fields = item.get('fields', {})
        
        # 检查审核状态
        status = parse_field_value(fields.get('审核状态', []), '')
        if '已通过' in status or '已拒绝' in status:
            continue
        
        # 解析字段
        record = {
            'code': parse_field_value(fields.get('编码', ''), 'N/A'),
            'name': parse_field_value(fields.get('姓名', []), '未知'),
            'qty': parse_number_field(fields.get('数量', 0)),
            'price': parse_number_field(fields.get('单价', 0)),
            'amount': parse_number_field(fields.get('金额', 0)),
            'submit_time': parse_datetime_field(fields.get('日期/时间', 0))
        }
        pending_records.append(record)
    
    total_amount = sum(r['amount'] for r in pending_records)
    return pending_records, total_amount

# 生成标准格式回复
def format_pending_reply(group_name, records, total_amount):
    lines = [f"⏳ {group_name}待审核记录：", "", "📋 待审核详情："]
    
    for rec in records:
        lines.append(f"- 📊编码：{rec['code']} | 数量：{rec['qty']}件 | 单价：{rec['price']}元 | 金额：{rec['amount']:.2f}元 | 提交时间：{rec['submit_time']}")
    
    lines.append("")
    lines.append(f"💰 待审核总计金额：{total_amount:.2f} 元")
    lines.append(f"📝 共 {len(records)} 条记录等待审核 @审核员")
    
    return "\n".join(lines)
```

## 注意事项

1. **时间戳单位**: 飞书返回的是毫秒级时间戳，必须除以1000转换为秒
2. **字段格式**: 文本字段可能返回富文本数组 `[{"text":"...","type":"text"}]`，需要提取text值
3. **金额精度**: 使用 `round(amount, 2)` 保留2位小数
4. **空值处理**: 所有字段都需要处理空值或缺失值的情况
5. **分页**: 如果记录超过500条，需要处理分页（使用page_token）


## 脚本工作流



## 手动查询方式（旧版）


The `pending_review` route in the kingdou router is not fully implemented. When users request "待审核", "查看待审核", or "待审核记录", the system returns:
```
{"route_type": "unknown", "reason": "group_not_configured: pending_review", "group_name": null, "shadow_only": true}
```

This is because the `query_pending_reviews.py` script does not exist in the router directory.

## Manual Query Approach
Until the automated pending review functionality is implemented, use the following manual approach:

### 1. Get Feishu App Access Token
```bash
curl -s -X POST "https://open.feishu.cn/open-apis/auth/v3/app_access_token/internal/" \
  -H "Content-Type: application/json" \
  -d '{"app_id":"YOUR_APP_ID","app_secret":"YOUR_APP_SECRET"}'
```

Extract the `app_access_token` from the response.

### 2. Query All Records
Since the Bitable API has issues with the `isEmpty` filter operator, query all records first:
```bash
curl -s -X POST "https://open.feishu.cn/open-apis/bitable/v1/apps/{app_token}/tables/{table_id}/records/search" \
  -H "Authorization: Bearer {access_token}" \
  -H "Content-Type: application/json" \
  -d '{"field_names": ["编码", "姓名", "单价", "数量", "金额", "日期/时间", "审核状态"]}'
```

### 3. Filter Pending Reviews Locally
Records are pending review when:
- The "审核状态" field is empty (null or empty array)
- OR the "审核状态" field contains an empty string

Process the JSON response to identify these records programmatically.

## API Filtering Issues Encountered
- `isEmpty` operator requires a `value` parameter but rejects empty values
- `is_empty` is not a valid operator name (correct name is `isEmpty`)
- The API validation is inconsistent between documentation and actual behavior

## Recommended Implementation
When implementing the proper `query_pending_reviews.py` script:
1. Use the manual query approach above as fallback
2. Consider using server-side filtering with `"审核状态": {"operator": "is", "value": ""}` if supported
3. Always include proper error handling for API validation failures
4. Format results using the standard reply template from `references/standard-reply-template.md`

## 完整操作指南


