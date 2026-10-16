# 飞书机器人主动私聊（DM by open_id）

金豆应用（`cli_<redacted-01>`）能否**主动**给员工发消息，取决于目标：

| 场景 | 接口 | 是否受限制 |
|------|------|-----------|
| 群消息 | `receive_id_type=chat_id` | 只要机器人在群里就能发，**不受可用范围影响** |
| 1v1 私聊 | `receive_id_type=open_id` | 仅限**在本应用「可用范围」内**的用户 |

`router/feishu_client.py` 的 `send_text()` **只支持 chat_id**。私聊必须自己拼 open_id 请求。

## 发送方式

```python
import sys, json
sys.path.insert(0, '~/.hermes/skills/kingdou/scripts')
from router.feishu_client import FeishuClient

client = FeishuClient()
url = f"{client.base}/im/v1/messages?receive_id_type=open_id"
payload = {"receive_id": "<ou_xxx>", "msg_type": "text",
           "content": json.dumps({"text": "..."}, ensure_ascii=False)}
d = client.session.post(url, headers=client.headers(), json=payload, timeout=10).json()
# code == 0 → 已送达，d["data"]["message_id"] 是送达凭据
```

可直接跑探针脚本（见 `scripts/check-dm-capability.py`），无需手写代码。

## 错误码对照

| code | msg | 含义 | 处理 |
|------|-----|------|------|
| `0` | success | 送达 | 记 `data.message_id` 作凭据 |
| `230013` | Bot has NO availability to this user | 用户**不在应用「可用范围」**内 | 开放平台 → 应用 → 版本管理与发布 → **可用范围**加入成员/部门 → 发布新版本 |
| `99992361` | open_id cross app | 该 open_id **属于另一个应用**，本应用无权使用 | ID 无效，必须换成本应用下的真实 open_id |
| `99991672` | — | 应用缺少 `contact:user.id:readonly` 权限 | 无法按姓名/手机号反查 open_id |

**关键区分**：`230013` = ID 有效但人不在范围（可修）；`99992361` = ID 本身就不可用（必须换）。

## 诊断流程（先隔离，再下结论）

1. **先给应用创建者本人发** —— 成功即证明私聊通道本身可用，其余失败都是个体问题（范围 or 跨应用）。
   金豆应用 creator = `ou_<redacted-03>`（管理员<02>）。
   `GET /open-apis/application/v6/applications/{app_id}?lang=zh_cn` 返回 `app_name` / `online_version_id` / `creator_id`。
2. 再逐个测目标用户，按错误码区分「范围不足」与「ID 无效」。
3. 反查本应用下的**真实** open_id：让目标用户在本应用所在的群里发一条消息，然后
   ```bash
   grep -oP 'sender=user:\Kou_[0-9a-f]{32}' ~/.hermes/logs/gateway.log | sort -u
   ```
   出现过的才是**本应用内有效**的 open_id。

## 陷阱

- **不要把「@提及文本里的 open_id」当作有效 ID**。它只是消息正文，不是事件发送者，可能来自其它应用——
  实测 `ou_<redacted-05>`（管理员<01>）在日志中**只**以 @提及形式出现，从未作为 sender 出现过，用 API 发私聊即报 `99992361`。
- **同一 `openid_name_mapping` 里两条不同 OpenID ≠ 同一人**。用户口头说「A 也就是 B」时，先核对配置，两条不同 `ou_` 通常是两个独立账号，不要默认合并。
- **可用范围无法通过 API 修改**，必须去飞书开放平台控制台操作并**发布新版本**才生效。
- **验证私聊必然产生真实消息**。要零噪音验证脚本/链路，就选一个**预期失败**的目标（如已确认跨应用的 ID）来跑，失败即不投递。

## 会话实例（2026-09-11）

需求：「私聊验证权限，发给管理员<01> 也就是管理员<01>」。

| 目标 | open_id | 结果 |
|------|---------|------|
| 管理员<02>（本人/应用创建者） | `ou_<redacted-03>` | `code=0` ✅ 送达 |
| 管理员<01> | `ou_<redacted-10>` | `230013` ❌ 不在可用范围 |
| 管理员<01> | `ou_<redacted-05>` | `99992361` ❌ 跨应用，ID 无效 |

结论：**通道可用，两人均不可达，原因不同**。且配置里「管理员<01>」与「管理员<01>」是**两个不同账号**，并非同一人。

---

## 机器人主动私聊（1v1 DM by open_id）

群消息和私聊是**两套不同权限**：

- **群消息**（`receive_id_type=chat_id`）：只要机器人在群里就能发，不受可用范围限制。
- **私聊**（`receive_id_type=open_id`）：仅限**在本应用「可用范围」内**的用户。

`feishu_client.py` 的 `send_text()` 只支持 chat_id。私聊需自己拼 open_id 请求，或直接用探针脚本：

```bash
PYTHONPATH=~/.hermes/skills/kingdou/scripts \
$KINDOU_PY \
  ~/.hermes/skills/kingdou/scripts/check-dm-capability.py --self
```

**错误码速查**（判定用户是否可达）：

| code | 含义 | 处理 |
|------|------|------|
| `0` | 送达 | 记 `data.message_id` 作凭据 |
| `230013` | 不在应用「可用范围」 | 开放平台 → 版本管理与发布 → 可用范围加入成员 → 发布新版本（**无法用 API 改**） |
| `99992361` | open_id 跨应用，本应用无权使用 | ID 本身无效，必须换成本应用下的真实 open_id |
| `99991672` | 缺少 contact 权限 | 无法按姓名/手机号反查 open_id |

**诊断顺序**：先给应用创建者本人（`ou_<redacted-03>` 管理员<02>）发一条 —— 成功即证明通道可用，其余失败都是个体问题。再逐个测目标，按错误码区分「范围不足(230013)」与「ID 无效(99992361)」。

**反查本应用真实 open_id**：让目标用户在本应用所在的群里发一条消息，然后
`grep -oP 'sender=user:\Kou_[0-9a-f]{32}' ~/.hermes/logs/gateway.log | sort -u`
—— 只在消息正文 **@提及文本**里出现过的 open_id **不算**，那可能来自其它应用。

⚠️ 用户口头说「A 也就是 B」时，先核对配置：`openid_name_mapping` 里两条不同的 `ou_` 通常是**两个独立账号**，不要默认合并。

详见 `references/feishu-direct-message.md`（含完整诊断流程与会话实例）。

---

### 机器人主动私聊权限（可用范围）

金豆主动给员工发**私聊**时，员工必须在应用「可用范围」内，否则报错：

| 错误码 | 含义 | 处理 |
|--------|------|------|
| `230013` | Bot has NO availability to this user → 用户不在应用可用范围 | 控制台把该成员/部门加入可用范围并发布新版本 |
| `99992361` | open_id cross app → 该 open_id 属于**其他应用**，本应用不可用 | 该 ID 是废的，必须替换为本应用下的真实 open_id |

**只读诊断**（可查看每个版本的可用范围，无需额外权限）：
```bash
GET /open-apis/application/v6/applications/{app_id}/app_versions?lang=zh_cn&page_size=10
# 看 items[].remark.visibility.visible_list.open_ids
```

**改可用范围的 API**（存在但默认不可用）：
```
PATCH /open-apis/application/v6/applications/{app_id}/app_versions/{version_id}
      ?lang=zh_cn&user_id_type=open_id&operator_id=<操作人openid>
# user_id_type / operator_id 必须走 query 参数，放 header 无效
# 需要权限 application:application.app_version，默认未开通 → 实际只能在控制台改
```

**控制台路径**：飞书开放平台 → 应用「金豆」→ 应用发布 → 版本管理与发布 → 编辑版本 → 可用范围 → 添加成员 → 发布新版本。

**关键事实**：`可用范围` 只限制**主动私聊**，**群消息不受影响**（员工不在可用范围内，仍能正常在群里提交计件并收到脚本回复）。

**识别无效 open_id 的方法**：在网关历史日志里搜该 open_id 是否作为 `sender=` 出现过。从未出现过 → 大概率是外部抄录的废 ID。
```bash
grep -oP 'ou_[0-9a-f]{32}' ~/.hermes/logs/gateway.log | sort -u
```
