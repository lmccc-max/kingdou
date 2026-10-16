# 飞书 API 调用模式参考

## 认证流程

### 1. 获取 Tenant Access Token

```python
import requests

# 应用凭证（从 ~/.hermes/.env 读取）
app_id = "cli_xxxxxxxxxxxxxxxx"
app_secret = "xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"

# 获取 token
token_url = "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal"
token_payload = {
    "app_id": app_id,
    "app_secret": app_secret
}

response = requests.post(token_url, json=token_payload, timeout=10)
token_data = response.json()

if token_data.get("code") == 0:
    access_token = token_data["tenant_access_token"]
    # token 有效期通常为 2 小时，可缓存复用
else:
    raise Exception(f"获取token失败: {token_data}")
```

### 2. 调用 Bitable API

```python
# 群配置（从 piecework-groups.json 读取）
app_token = "app_<redacted-04>"  # 多维表格 app_token
table_id = "tbl_<redacted-03>"               # 表格 ID

# 查询记录
records_url = f"https://open.feishu.cn/open-apis/bitable/v1/apps/{app_token}/tables/{table_id}/records"
headers = {
    "Authorization": f"Bearer {access_token}",
    "Content-Type": "application/json; charset=utf-8"
}

response = requests.get(
    records_url, 
    headers=headers, 
    params={"page_size": 500},  # 最大 500 条/页
    timeout=10
)

data = response.json()
if data.get("code") == 0:
    items = data.get("data", {}).get("items", [])
    for item in items:
        fields = item.get("fields", {})
        # 处理记录...
```

### 3. 筛选待审核记录

```python
pending_records = []
for item in items:
    fields = item.get("fields", {})
    status = fields.get("审核状态", "")
    # 待审核状态：空字符串、"待审核"、或包含"待审核"
    if status == "" or status == "待审核" or "待审核" in str(status):
        pending_records.append({
            "编码": fields.get("编码", "N/A"),
            "提交人": fields.get("提交人", "N/A"),
            "数量": fields.get("数量", "N/A"),
            "单价": fields.get("单价", "N/A"),
            "金额": fields.get("金额", "N/A"),
            "record_id": item.get("record_id", "")  # 用于更新记录
        })
```

### 4. 创建记录

**重要：使用字段名称而非字段ID**

飞书Bitable API在创建记录时，必须使用**字段名称**（如"姓名"）而不是字段ID（如"fld_<redacted-02>"）。这与查询/更新操作不同。

```python
# 创建记录 - 使用字段名称
from datetime import datetime

create_url = f"https://open.feishu.cn/open-apis/bitable/v1/apps/{app_token}/tables/{table_id}/records"
create_payload = {
    "fields": {
        "姓名": "员工<01>",           # ✅ 使用字段名称
        "单价": 0.05,              # ✅ 使用字段名称
        "数量": 99,                # ✅ 使用字段名称
        "日期/时间": int(datetime.now().timestamp() * 1000)  # 毫秒时间戳
    }
}

response = requests.post(create_url, headers=headers, json=create_payload)
```

**常见错误：**
- ❌ 使用字段ID：`"fld_<redacted-02>": "员工<01>"` → 报错 `FieldNameNotFound`
- ✅ 使用字段名称：`"姓名": "员工<01>"` → 成功

### 5. 更新记录（审核通过/拒绝）

**⚠️ 关键：必须使用 PUT 方法，PATCH 返回 404！**

```python
# 审核通过
update_url = f"https://open.feishu.cn/open-apis/bitable/v1/apps/{app_token}/tables/{table_id}/records/{record_id}"
update_payload = {
    "fields": {
        "审核状态": f"已通过 {datetime.now().strftime('%Y-%m-%d %H:%M')}",
        "审核人": "审核员姓名"
    }
}

# ✅ 正确：使用 PUT
response = requests.put(update_url, headers=headers, json=update_payload)

# ❌ 错误：PATCH 返回 404 Not Found
# response = requests.patch(update_url, headers=headers, json=update_payload)
```

**curl 示例**：
```bash
curl -X PUT "https://open.feishu.cn/open-apis/bitable/v1/apps/{app_token}/tables/{table_id}/records/{record_id}" \
  -H "Authorization: Bearer {access_token}" \
  -H "Content-Type: application/json" \
  -d '{"fields": {"审核状态": "已通过 2026-05-09 10:10", "审核人": "管理员<03>"}}'
```

**API端点验证结果**：
| 方法 | 端点 | 结果 |
|------|------|------|
| GET | `/records/{record_id}` | ✅ 200 - 获取单条记录 |
| PUT | `/records/{record_id}` | ✅ 200 - 更新记录 |
| PATCH | `/records/{record_id}` | ❌ 404 - 不支持 |
| POST | `/records/{record_id}` | ❌ 404 - 不支持 |
| POST | `/records/batchUpdate` | ❌ 404 - 不支持 |

## 5. 字段验证与映射

```python
# 获取表格所有字段信息
fields_url = f"https://open.feishu.cn/open-apis/bitable/v1/apps/{app_token}/tables/{table_id}/fields"
headers = {
    "Authorization": f"Bearer {access_token}",
    "Content-Type": "application/json; charset=utf-8"
}

response = requests.get(fields_url, headers=headers, timeout=10)
fields_data = response.json()

if fields_data.get("code") == 0:
    items = fields_data.get("data", {}).get("items", [])
    field_mapping = {}
    for item in items:
        field_name = item.get("field_name", "")
        field_id = item.get("field_id", "")
        field_type = item.get("type", "")
        field_mapping[field_name] = field_id
        # 打印字段信息用于调试
        print(f"{field_name} | {field_id} | {field_type}")
```

### 字段类型代码对照表

| 类型代码 | 类型名称 | 说明 |
|---------|---------|------|
| 1 | Text | 文本字段 |
| 2 | Number | 数字字段 |
| 5 | SingleSelect | 单选 |
| 7 | MultiSelect | 多选 |
| 11 | Phone | 电话 |
| 13 | Url | 链接 |
| 15 | Attachment | 附件 |
| 17 | Checkbox | 复选框 |
| 18 | Person | 人员 |
| 20 | Formula | 公式字段（自动计算） |
| 1001 | DateTime | 日期时间 |
| 1002 | CreateTime | 创建时间（系统） |
| 1003 | ModifyTime | 修改时间（系统） |
| 1004 | CreateUser | 创建人（系统） |
| 1005 | AutoNumber | 自动编号（系统生成） |
| 1006 | ModifyUser | 修改人（系统） |

## 6. 时间戳处理（重要！）

飞书 Bitable 的日期时间字段返回的是 **毫秒级 Unix 时间戳**，不是秒级！

```python
from datetime import datetime

# 错误做法（会导致 year out of range 错误）
ts = int(date_time_val)  # 1777882736000
 dt = datetime.fromtimestamp(ts)  # ValueError: year 58308 is out of range

# 正确做法（除以 1000 转换为秒）
ts_ms = int(date_time_val)  # 1777882736000
ts = ts_ms / 1000  # 1777882736.0
dt = datetime.fromtimestamp(ts)  # 正确的日期
```

### 日期筛选示例

```python
from datetime import datetime, timedelta

# 计算昨天的时间戳范围（毫秒）
yesterday = datetime.now() - timedelta(days=1)
yesterday_start = datetime(yesterday.year, yesterday.month, yesterday.day, 0, 0, 0)
yesterday_end = datetime(yesterday.year, yesterday.month, yesterday.day, 23, 59, 59)

# 转换为毫秒时间戳
yesterday_start_ms = int(yesterday_start.timestamp() * 1000)
yesterday_end_ms = int(yesterday_end.timestamp() * 1000)

# 筛选记录
for item in items:
    fields = item.get("fields", {})
    date_time_val = fields.get("日期/时间", 0)
    if date_time_val:
        ts = int(date_time_val)
        if yesterday_start_ms <= ts <= yesterday_end_ms:
            # 这是昨天的记录
            dt = datetime.fromtimestamp(ts / 1000)
            print(f"记录日期: {dt.strftime('%Y-%m-%d %H:%M:%S')}")
```

## ⚠️ record_id vs 编码（关键！）

**飞书Bitable的 `record_id`（内部ID）与 `编码`（显示字段）是两个完全不同的概念！**

| 概念 | 示例 | 说明 |
|------|------|------|
| `编码` | `298` | 用户看到的AutoNumber字段值，用户操作时使用 |
| `record_id` | `recvjbWwQtqxg5` | 飞书内部记录ID，API更新/删除操作时使用 |

**问题场景**：用户说"拒绝 298"，298是编码字段的值，不是record_id。直接使用 `PUT /records/298` 会返回 `RecordIdNotFound` 错误。

**正确流程**：
```python
# 1. 先通过编码搜索记录，获取内部record_id
search_url = f"https://open.feishu.cn/open-apis/bitable/v1/apps/{app_token}/tables/{table_id}/records/search"
search_payload = {
    "filter": {
        "conjunction": "and",
        "conditions": [
            {
                "field_name": "编码",
                "operator": "is",
                "value": ["298"]  # 用户提供的编码
            }
        ]
    },
    "page_size": 10
}
response = requests.post(search_url, headers=headers, json=search_payload)
record_id = response.json()["data"]["items"][0]["record_id"]  # 获取内部record_id

# 2. 使用record_id更新/删除记录
update_url = f"https://open.feishu.cn/open-apis/bitable/v1/apps/{app_token}/tables/{table_id}/records/{record_id}"
requests.put(update_url, headers=headers, json=update_payload)
```

**关键规则**：
- ✅ 搜索/查询时：使用 `编码` 字段值（如 `298`）
- ✅ 更新/删除时：使用 `record_id`（如 `recvjbWwQtqxg5`）
- ❌ 禁止直接用编码值调用 PUT/DELETE `/records/{编码}` → 返回 `RecordIdNotFound`

**错误示例**：
```
PUT /records/298 → ❌ RecordIdNotFound (298是编码，不是record_id)
PUT /records/recvjbWwQtqxg5 → ✅ 成功
```

## 常见错误码

| 错误码 | 含义 | 处理 |
|--------|------|------|
| 99991661 | Missing access token | 重新获取 tenant_access_token |
| 99991663 | Access token expired | token 过期，重新获取 |
| 99991664 | Invalid access token | 检查 app_id/app_secret |
| 99991672 | Access denied (scope required) | 应用缺少所需权限，需到飞书开放平台申请 |
| 1254045 | FieldNameNotFound | 创建记录时使用了字段ID而非字段名称，改用字段名称 |
| 1254043 | RecordIdNotFound | 使用了编码值而非内部record_id，需先搜索获取record_id |

## 群成员管理

### 获取群成员列表

```python
# 获取群成员（返回 open_id 列表）
chat_id = "oc_<redacted-02>"
members_url = f"https://open.feishu.cn/open-apis/im/v1/chats/{chat_id}/members"
headers = {
    "Authorization": f"Bearer {access_token}",
    "Content-Type": "application/json; charset=utf-8"
}

response = requests.get(
    members_url,
    headers=headers,
    params={"member_id_type": "open_id", "page_size": 100},
    timeout=10
)

data = response.json()
if data.get("code") == 0:
    members = data.get("data", {}).get("items", [])
    for member in members:
        member_id = member.get("member_id", "")
        print(f"用户 ID: {member_id}")
```

### 获取用户详细信息（需要权限）

**注意**：获取用户详细信息需要 `contact:user.id:readonly` 或 `contact:user.department:readonly` 权限。

```python
# 单个查询（可能因权限不足失败）
user_url = f"https://open.feishu.cn/open-apis/contact/v3/users/{user_id}"
response = requests.get(
    user_url,
    headers=headers,
    params={"user_id_type": "open_id"},
    timeout=10
)

# 批量查询（同样受权限限制）
batch_url = "https://open.feishu.cn/open-apis/contact/v3/users/batch_get_id"
payload = {
    "user_id_type": "open_id",
    "open_ids": member_ids
}
response = requests.post(batch_url, headers=headers, json=payload, timeout=10)
```

### 权限不足时的替代方案

当应用没有 `contact:user.id:readonly` 权限时：

1. **从会话上下文获取**：当前发送消息的用户 ID 会在会话中提供
2. **手动配置映射**：在 `piecework-groups.json` 中手动维护 `admin_name_mapping`
3. **通过消息交互确认**：让用户主动确认身份

```json
// piecework-groups.json 中的 name mapping 示例
"admin_name_mapping": {
  "ou_<redacted-09>": "管理员<03>",
  "ou_<redacted-05>": "管理员<01>"
}
```

**⚠️ 配置字段命名注意**：配置文件中实际使用的字段名是 `openid_name_mapping`（不是 `admin_name_mapping` 或 `openid_name_map`）。查询审核人时必须使用正确的字段名。

## 环境变量

凭证存储位置：`~/.hermes/.env`

```bash
FEISHU_APP_ID=cli_xxxxxxxxxxxxxxxx
FEISHU_APP_SECRET=xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
```
