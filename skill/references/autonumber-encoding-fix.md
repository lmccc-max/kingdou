# AutoNumber 编码字段问题

## 问题描述

飞书 Bitable 的 AutoNumber 类型字段（如"编码"）在 `create_record` API 响应中**不会返回**，只返回 `record_id`。

## 影响

- 创建记录后立即读取 `fields.编码` 会得到 `None`
- 如果不处理，`code_of()` 函数会回退到使用 `record_id`（如 `recvlnPH6tewX6`）

## 解决方案

在 `submit_piecework.py` 中，创建记录后需要：

```python
c = FeishuClient()
record = c.create_record(app_token, table_id, fields)
record_id = record.get('record_id', '')

# 等待 AutoNumber 生成
time.sleep(0.3)

# 重新查询获取完整记录
if record_id:
    record = c.get_record(app_token, table_id, record_id) or record
```

## 验证

```bash
PYTHONPATH=~/.hermes/skills/kingdou/scripts \
$KINDOU_PY -c "
from router.feishu_client import FeishuClient
from router.field_utils import code_of
import time

c = FeishuClient()
record = c.create_record('app_token', 'table_id', {'姓名': '测试', '单价': 0.01, '数量': 1})
rid = record.get('record_id')
print(f'创建返回编码: {record.get(\"fields\", {}).get(\"编码\")}')  # None

time.sleep(0.3)
full = c.get_record('app_token', 'table_id', rid)
print(f'查询返回编码: {full.get(\"fields\", {}).get(\"编码\")}')  # 实际编号
print(f'code_of: {code_of(full)}')
"
```

## 测试记录清理

测试后记得删除记录：
```python
c.update_record(app_token, table_id, record_id, {'审核状态': '已删除'})
```

## 时间戳

- 2026-06-02: 发现并修复，0.3 秒等待足够

---

### AutoNumber 编码字段
飞书 Bitable 的 AutoNumber 字段**不会在 create_record 响应中返回**，需要：
1. 创建记录后获取 `record_id`
2. 等待 0.3 秒（确保自增编号生成）
3. 调用 `get_record` 获取完整记录（包含编码字段）
