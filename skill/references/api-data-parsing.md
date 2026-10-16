# 飞书 Bitable API 数据解析指南

## 字段值返回格式

飞书Bitable API返回的字段值有多种格式，需要根据字段类型正确解析。

### 1. 文本字段（姓名、审核状态、审核人等）

**返回格式**: 富文本数组
```json
[
  {"text": "员工<02>", "type": "text"}
]
```

**解析代码**:
```python
def parse_text_field(field_value):
    """解析文本字段"""
    if isinstance(field_value, list) and len(field_value) > 0:
        if isinstance(field_value[0], dict) and 'text' in field_value[0]:
            return field_value[0]['text']
    return str(field_value) if field_value else ''

# 使用示例
name = parse_text_field(fields.get('姓名'))
status = parse_text_field(fields.get('审核状态'))
reviewer = parse_text_field(fields.get('审核人'))
```

### 2. 数字字段（单价、数量）

**返回格式**: 直接数值
```json
0.36
```

**解析代码**:
```python
price = fields.get('单价', 0)
quantity = fields.get('数量', 0)
```

### 3. 公式字段（金额）

**返回格式**: 对象包含类型和值
```json
{
  "type": 2,
  "value": [11.16]
}
```

**解析代码**:
```python
def parse_formula_field(field_value):
    """解析公式字段（金额）"""
    if isinstance(field_value, dict) and 'value' in field_value:
        values = field_value['value']
        if isinstance(values, list) and len(values) > 0:
            return values[0]
    return field_value if isinstance(field_value, (int, float)) else 0

# 使用示例
amount = parse_formula_field(fields.get('金额'))
```

### 4. 日期时间字段

**返回格式**: 毫秒级Unix时间戳
```json
1777960675000
```

**解析代码**:
```python
from datetime import datetime

def parse_datetime_field(field_value):
    """解析日期时间字段"""
    if isinstance(field_value, (int, float)):
        ts = field_value / 1000  # 转换为秒
        return datetime.fromtimestamp(ts)
    return None

# 使用示例
dt = parse_datetime_field(fields.get('日期/时间'))
if dt:
    date_str = dt.strftime('%Y-%m-%d %H:%M')
```

### 5. 编码字段（AutoNumber）

**返回格式**: 不同群格式不同

**示例**:
- 员工<01>计件群: `"RF2026050281"` (带RF前缀)
- 员工<02>计件群: `"281"` (纯数字)

**解析代码**:
```python
code = fields.get('编码', '')
# 不要预设格式，直接获取字符串值
```

## 完整解析示例

```python
def parse_record_fields(fields):
    """完整解析一条记录的字段"""
    result = {}
    
    # 文本字段
    for field_name in ['姓名', '审核状态', '审核人', '备注']:
        value = fields.get(field_name)
        if isinstance(value, list) and len(value) > 0:
            result[field_name] = value[0].get('text', '')
        else:
            result[field_name] = str(value) if value else ''
    
    # 数字字段
    result['单价'] = fields.get('单价', 0)
    result['数量'] = fields.get('数量', 0)
    
    # 公式字段
    amount_field = fields.get('金额', {})
    if isinstance(amount_field, dict) and 'value' in amount_field:
        result['金额'] = amount_field['value'][0] if amount_field['value'] else 0
    else:
        result['金额'] = amount_field if isinstance(amount_field, (int, float)) else 0
    
    # 编码字段
    result['编码'] = fields.get('编码', '')
    
    # 日期时间字段
    dt_field = fields.get('日期/时间')
    if isinstance(dt_field, (int, float)):
        result['日期/时间'] = datetime.fromtimestamp(dt_field / 1000)
    else:
        result['日期/时间'] = None
    
    return result
```

## 常见错误

### 错误1: 直接访问数组元素
```python
# ❌ 错误
name = fields['姓名'][0]  # 可能IndexError

# ✅ 正确
name_field = fields.get('姓名', [])
if isinstance(name_field, list) and len(name_field) > 0:
    name = name_field[0].get('text', '')
```

### 错误2: 预设编码格式
```python
# ❌ 错误
target_codes = ['RF2026050281']  # 可能找不到

# ✅ 正确
if '281' in str(code):  # 灵活匹配
```

### 错误3: 忽略时间戳单位
```python
# ❌ 错误
dt = datetime.fromtimestamp(timestamp)  # 年份会错误

# ✅ 正确
dt = datetime.fromtimestamp(timestamp / 1000)
```
