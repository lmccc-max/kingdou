# 计件数据提交完整工作流程

## 概述

本文档记录计件工资数据从用户消息到飞书Bitable的完整提交流程，包括API调用顺序、字段处理、状态更新和确认回复。

## 工作流程图

```
用户消息 (0.12 103)
    ↓
解析单价和数量
    ↓
加载群聊配置 (piecework-groups.json)
    ↓
获取 tenant_access_token
    ↓
创建Bitable记录 (姓名、单价、数量、日期/时间)
    ↓
更新审核状态 → "待审核"
    ↓
查询确认记录 (获取编码、金额)
    ↓
回复用户确认信息
```

## 完整代码示例

```python
import json
import requests
from datetime import datetime
import os

# 1. 加载群聊配置
config_path = os.path.expanduser("~/.hermes/skills/kingdou/configs/piecework-groups.json")
with open(config_path, 'r') as f:
    config = json.load(f)

# 根据当前会话确定群聊ID
current_chat_id = "oc_<redacted-06>"  # 员工<11>计件群
group_config = config['groups'].get(current_chat_id)

# 2. 获取飞书访问令牌
app_id = os.environ.get('FEISHU_APP_ID')
app_secret = os.environ.get('FEISHU_APP_SECRET')

token_url = "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal"
token_resp = requests.post(token_url, json={"app_id": app_id, "app_secret": app_secret})
token_data = token_resp.json()
tenant_token = token_data['tenant_access_token']

# 3. 创建计件记录
unit_price = 0.12    # 从用户消息解析
quantity = 103       # 从用户消息解析
employee_name = "员工<11>"  # 根据群配置确定
current_timestamp = int(datetime.now().timestamp() * 1000)  # 毫秒级时间戳

record_data = {
    "fields": {
        "姓名": employee_name,
        "单价": unit_price,
        "数量": quantity,
        "日期/时间": current_timestamp
    }
}

api_url = f"https://open.feishu.cn/open-apis/bitable/v1/apps/{group_config['app_token']}/tables/{group_config['table_id']}/records"
headers = {"Authorization": f"Bearer {tenant_token}", "Content-Type": "application/json"}

create_resp = requests.post(api_url, headers=headers, json=record_data)
create_data = create_resp.json()
record_id = create_data['data']['record']['record_id']

# 4. 更新审核状态为"待审核"
update_data = {"fields": {"审核状态": "待审核"}}
update_url = f"{api_url}/{record_id}"
requests.put(update_url, headers=headers, json=update_data)

# 5. 查询确认记录（获取系统生成的编码和自动计算的金额）
query_resp = requests.get(update_url, headers=headers)
query_data = query_resp.json()
fields = query_data['data']['record']['fields']

code = fields.get('编码', 'N/A')
amount_field = fields.get('金额', 0)
if isinstance(amount_field, dict):
    amount = amount_field.get('value', 0)
else:
    amount = amount_field

# 6. 回复用户确认信息
print(f"""
==================================================
✅ 数据提交成功！
==================================================
📋 提交详情:
   • 编码: {code}
   • 姓名: {employee_name}
   • 单价: ¥{unit_price}
   • 数量: {quantity}
   • 金额: ¥{round(float(amount), 2) if amount else 0}
   • 状态: ⏳ 待审核
   • 时间: {datetime.now().strftime('%Y-%m-%d %H:%M')}
==================================================
""")
```

## 关键要点

### 1. 字段名称 vs 字段ID

创建记录时必须使用**字段名称**（如"姓名"），不能使用字段ID（如"fld_<redacted-02>"）。

```python
# ✅ 正确
"姓名": "员工<11>"

# ❌ 错误 - 会导致 FieldNameNotFound 错误
"fld_<redacted-02>": "员工<11>"
```

### 2. 时间戳格式

日期/时间字段需要**毫秒级 Unix 时间戳**（乘以1000）：

```python
current_timestamp = int(datetime.now().timestamp() * 1000)
```

### 3. 金额自动计算

金额字段是飞书公式字段，根据"单价 × 数量"自动计算。创建记录时不需要提供金额，查询时从返回数据中提取。

### 4. 编码自动生成

编码字段是 AutoNumber 类型，由系统自动生成。创建记录后需要查询获取系统分配的编码。

### 5. 审核状态必须单独更新

创建记录时设置审核状态可能不生效，需要创建后单独调用更新接口：

```python
# 创建后更新审核状态
update_data = {"fields": {"审核状态": "待审核"}}
requests.put(f"{api_url}/{record_id}", headers=headers, json=update_data)
```

## 群聊配置映射

每个计件群有独立的配置，通过 `chat_id` 映射：

```json
{
  "groups": {
    "oc_<redacted-06>": {
      "name": "员工<11>计件群",
      "app_token": "app_<redacted-05>",
      "table_id": "tbl_<redacted-04>",
      "employee_list": ["ou_<redacted-02>"]
    }
  }
}
```

## 标准回复模板

```
✅ 数据提交成功！

📋 提交详情:
   • 编码: {code}
   • 姓名: {employee_name}
   • 单价: ¥{unit_price}
   • 数量: {quantity}
   • 金额: ¥{amount}
   • 状态: ⏳ 待审核
   • 时间: {timestamp}

🔔 提醒审核员: 有新的计件记录待审核，请尽快处理。
```

## 零废话原则

根据技能规范，员工提交计件数据后**直接执行**，不询问确认，不加多余对话：

- ❌ 禁止说"我帮您提交"、"请确认"等多余话语
- ✅ 直接执行：收到 `0.12 103` → 立即创建记录 → 回复确认信息（含编码）
- ⛔ **红线**：通过 `feishu-send-message.py` 发送确认后，agent 自身回复必须为空或最简。额外对话文本会成为群内第二条消息，触发用户不满，且可能被网关重复路由导致二次处理产生重复记录。已发生：2026-05-11 消息"0.02 3"被处理两次产生编码101和102。修复：删除重复记录，禁止额外对话输出。

---

## 计件提交完整流程

### 工作流程

1. **验证用户授权** — 检查发送者是否在当前群的 `allowed_submitters` 列表中
2. **检查配置** — 确认群组在中央配置 (`configs/piecework-groups.json`) 中有有效配置
3. **验证提交格式** — 确保价格和数量是有效数字（格式：`价格 数量`，如 `0.12 103`）
4. **处理提交** — 路由器分发到 `submit_piecework.py`，生成编码并写入 Bitable
5. **发送确认** — 脚本通过 `feishu_client.py` 自动发送飞书确认消息

### 配置体系

系统使用**多层配置源**，中央配置为权威：

| 配置源 | 路径 | 说明 |
|--------|------|------|
| 中央配置（权威） | `~/.hermes/skills/kingdou/configs/piecework-groups.json` | 所有群配置、global_admins、openid_name_mapping、fields_detail |
| 独立群配置 | `~/.hermes/piecework/groups/<chat_id>/config.json` | 基础群信息（部分群存在） |
| 旧版中央配置 | `~/.hermes/piecework_groups/group_configs.json` | 旧版，非权威，仅包含部分群 |

### 常见提交问题

- **路由返回 `unknown/no_match`**：检查发送者是否在 `employee_list` 中，非员工无法提交
- **新群无法提交**：需要先通过入职配置流程完成群组配置
- **编码字段缺失**：AutoNumber 字段不在 create_record 响应中返回，需等待后重新获取
- **`sender_not_in_employee_list` 首次失败后重试成功**：已观察到首次提交返回此错误，但立即重试相同的 chat_id + OpenID + 消息却成功的情况（2026-07-04，员工<07>计件群）。可能原因：配置缓存加载时序问题、中央配置与独立配置同步延迟。**处理方式**：遇到此错误时自动重试一次，若重试成功则继续，不需告知用户首次失败。同时检查中央配置和独立配置中该群的 `allowed_submitters` 是否包含该 OpenID。
- **验证时 sender_id 必须正确**：运行 `router.router` 测试时，必须使用实际发送者的 OpenID。审核操作用审核人的 OpenID，提交操作用员工的 OpenID。用错 sender_id 会导致 `sender_not_in_reviewer_list` 或 `sender_not_in_employee_list` 等权限错误。
