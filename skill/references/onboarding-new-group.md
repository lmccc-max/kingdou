# 添加新计件群 / 员工（入职配置）

---

## 添加新计件群/员工（新员工入职配置）

### 输入要求

用户必须提供：
- `chat_id`: 新员工计件群的群聊ID (格式: oc_xxx)
- `employee_name`: 员工姓名
- `employee_openid`: 员工的OpenID (格式: ou_xxx)
- `piecework_table`: 计件表格的完整URL (可为空字符串)

### 执行步骤

#### 1. 解析表格URL获取 app_token 和 table_id

支持两种 URL 格式，token 提取方式相同：
- Wiki: `https://tenant_<redacted-01>.feishu.cn/wiki/app_<redacted-03>?table=tbl_<redacted-02>`
- Base: `https://tenant_<redacted-01>.feishu.cn/base/app_<redacted-03>`

提取：`app_token` = `/wiki/` 或 `/base/` 后的部分，`table_id` = `table=` 参数值（如有）。

示例：`https://tenant_<redacted-01>.feishu.cn/wiki/app_<redacted-03>?table=tbl_<redacted-02>&view=vew_<redacted-01>`
- app_token = `app_<redacted-03>`
- table_id = `tbl_<redacted-02>`

如果 URL 没有 `table=` 参数，调用 `GET /bitable/v1/apps/{app_token}/tables` 列出所有表，选择正确的 table_id。

#### 2. 获取表格字段信息

```bash
cd ~/.hermes/skills/kingdou/scripts && \
PYTHONPATH=. $KINDOU_PY << 'EOF'
import requests
from router.feishu_client import FeishuClient
client = FeishuClient()
token = client.token()
headers = {'Authorization': f'Bearer {token}', 'Content-Type': 'application/json; charset=utf-8'}
url = f'https://open.feishu.cn/open-apis/bitable/v1/apps/{app_token}/tables/{table_id}/fields'
r = requests.get(url, headers=headers)
data = r.json()
if data.get('code') == 0:
    for field in data['data']['items']:
        print(f"{field['field_name']}: {field['field_id']} ({field['type']})")
EOF
```

#### 3. 更新中央配置文件

更新 `~/.hermes/skills/kingdou/configs/piecework-groups.json`：
- 添加 OpenID 映射到 `openid_name_mapping`
- 添加群组配置到 `groups`，包含 `fields_detail`（field_id 必须与步骤2一致）

#### 4. 创建独立配置文件

```bash
mkdir -p ~/.hermes/piecework/groups/{chat_id}
```

写入 `config.json`：`group_name`, `employee_openid`, `employee_name`, `piecework_table`, `allowed_submitters`

#### 5. 验证

```bash
python3 -m json.tool ~/.hermes/skills/kingdou/configs/piecework-groups.json > /dev/null
```

运行 dry-run 测试：
```bash
cd ~/.hermes/skills/kingdou/scripts && \
PYTHONPATH=. $KINDOU_PY -m router.router \
  {chat_id} {employee_openid} '0.12 103' --execute --dry-run --no-send
```

预期输出包含 `"route": "submit"` 和对应的群名。

#### 关键陷阱

- **必须更新中央配置文件**：仅创建独立配置文件不够，路由器读取的是中央配置。
- **字段ID必须匹配**：从API获取的field_id必须正确填入fields_detail。
- **JSON尾部逗号**：中央配置文件最后一个元素后不能有逗号。
- **`employee_list` 必须是 OpenID 字符串的扁平数组**：`validators.py` 的 `employee_for_submit` 用 `if sender_id in employees` 检查，`employees` 是 `group.get('employee_list')`。如果写成 `[{"name": "员工<10>", "openid": "ou_..."}]` 对象数组，`in` 操作符永远匹配不到，返回 `sender_not_in_employee_list`。正确格式：`["ou_<redacted-04>"]`。
- **`/base/` URL 同样适用**：飞书 `/base/{app_token}` 格式的 URL 也能直接用 app_token 调用 Bitable API，不仅限于 `/wiki/` 格式。如果用户分享的是 `/base/` 链接，直接提取 URL 路径中的 token 即可。不知道 table_id 时，先调用 `GET /bitable/v1/apps/{app_token}/tables` 列出所有表。
