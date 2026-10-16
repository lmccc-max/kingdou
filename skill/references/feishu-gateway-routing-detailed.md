# 飞书网关路由调试指南（详细版）

## 问题现象

用户在群里发送计件消息，但回复出现在私聊窗口。

## 排查步骤

### 1. 检查网关日志

```bash
# 查看最近的发送记录
grep -i "Sending response\|response ready" ~/.hermes/logs/gateway.log | tail -20

# 查看 inbound 消息路由
grep -i "Inbound.*message" ~/.hermes/logs/gateway.log | tail -20

# 查看回退/错误记录
grep -i "failed\|fallback\|error\|withdrawn\|230011" ~/.hermes/logs/gateway.log | tail -20
```

**关键日志格式**：
```
Sending response (XXX chars) to oc_xxx  ← 回复发送到的 chat_id
Inbound group message received: chat_id=oc_xxx  ← 消息来源 chat_id
Inbound dm message received: chat_id=oc_xxx  ← 私聊消息
```

### 2. 检查环境变量

```bash
env | grep -i "FEISHU\|HERMES_SESSION"
```

**关键变量**：
| 变量 | 说明 | 示例 |
|------|------|------|
| `HERMES_SESSION_KEY` | 当前会话标识 | `agent:main:feishu:group:oc_xxx:user_yyy` |
| `FEISHU_HOME_CHANNEL` | 默认回退频道 | `oc_xxx`（私聊 chat_id） |

### 3. 检查 Hermes 配置

```bash
grep -i "group_sessions_per_user\|FEISHU_HOME_CHANNEL" ~/.hermes/config.yaml
```

**关键配置**：
- `group_sessions_per_user: true` — 启用按群分组会话
- `FEISHU_HOME_CHANNEL` — 无法确定路由时的回退频道

### 4. 检查会话文件

```bash
# 查看活跃会话
hermes sessions list

# 查看会话文件中的 chat_id
grep -o 'oc_[a-f0-9]\+' ~/.hermes/sessions/session_*.json | sort -u
```

## 可能原因

### 原因1：消息撤回回退

**现象**：网关尝试回复原消息失败（`code 230011 — message withdrawn/missing`），回退到发送新消息。

**日志特征**：
```
WARNING [Feishu] Reply to om_xxx failed (code 230011 — message withdrawn/missing); falling back to new message in chat oc_xxx
```

**解决**：
- 确保用户不撤回原消息
- 网关会自动回退到群聊（不是私聊）

### 原因2：会话路由配置问题

**现象**：`group_sessions_per_user` 未启用或配置未生效。

**解决**：
1. 确认配置：`group_sessions_per_user: true`
2. 重启网关：`hermes gateway restart`
3. 验证：`hermes status` 查看 PID 是否更新

### 原因3：AI 会话上下文问题

**现象**：AI 使用了私聊会话而不是群聊会话。

**解决**：
1. 在群里发送 `/reset` 命令，创建新的群聊会话
2. 检查 `HERMES_SESSION_KEY` 是否包含 `group:oc_xxx`

### 原因4：飞书应用权限问题

**现象**：飞书应用没有权限在群里发送消息。

**解决**：
1. 检查飞书开放平台的应用权限
2. 确保应用已加入目标群聊

### 原因5：AI 系统提示未包含当前会话 chat_id（核心架构问题）

**现象**：用户在群A发送消息，AI 却使用了群B的配置（如错误地使用了 Home Channel 的配置）。

**日志特征**：
```
Inbound group message received: chat_id=oc_<redacted-04>  ← 消息来源群
Sending response (XXX chars) to oc_<redacted-05>          ← 却回复到了 Home Channel
```

**根本原因**：
- 网关正确识别了消息来源（chat_id=oc_<redacted-04>）
- 网关将 chat_id 存储到 session_context（`HERMES_SESSION_CHAT_ID`）
- **但 AI 的 system prompt 中没有包含这个 chat_id**
- AI 只能通过 `send_message` 工具的 `home channel` 配置获取 chat_id
- 当 AI 尝试发送消息时，使用的是 Home Channel ID（而非当前群的 chat_id）

**代码证据**：
1. `gateway/session_context.py` - 使用 ContextVar 存储 session 变量
2. `gateway/run.py` - 调用 `set_session_vars()` 设置 chat_id
3. `tools/send_message_tool.py` - 使用 `config.get_home_channel(platform)` 获取 home channel（这是静态配置，不是动态的当前会话 chat_id）

**解决（已实现）**：
在 `gateway/run.py` 的 `_run_agent_for_session` 方法中，调用 agent 前从 `session_context` 读取当前会话的 `chat_id`、`chat_name`、`user_id`、`user_name`、`platform`，并注入到 `combined_ephemeral` system prompt 中：

```python
# gateway/run.py (circa line 12516-12542)
from gateway.session_context import get_session_env
session_chat_id = get_session_env("HERMES_SESSION_CHAT_ID", "")
session_chat_name = get_session_env("HERMES_SESSION_CHAT_NAME", "")
session_user_id = get_session_env("HERMES_SESSION_USER_ID", "")
session_user_name = get_session_env("HERMES_SESSION_USER_NAME", "")
session_platform = get_session_env("HERMES_SESSION_PLATFORM", "")

if session_chat_id:
    session_context_info = [
        "",
        "<!-- Session Context -->",
        f"[Current Conversation ID: {session_chat_id}]",
    ]
    if session_chat_name:
        session_context_info.append(f"[Current Conversation Name: {session_chat_name}]")
    if session_user_id or session_user_name:
        session_context_info.append(f"[Current User: {session_user_name or session_user_id}]")
    if session_platform:
        session_context_info.append(f"[Current Platform: {session_platform}]")
    combined_ephemeral = (combined_ephemeral + "\n\n" + "\n".join(session_context_info)).strip()
```

效果：AI 的 system prompt 中将包含当前会话的 chat_id，技能可以直接根据 chat_id 区分不同的群聊。

**验证注入是否生效**：
```bash
grep -i "SESSION_CONTEXT" ~/.hermes/logs/gateway.log | tail -5
```

## 验证修复

```bash
# 1. 在群里发送测试消息（如 "0.1 10"）
# 2. 检查网关日志
grep -i "Sending response" ~/.hermes/logs/gateway.log | tail -5
# 应该看到：Sending response (XXX chars) to oc_xxx（群聊 chat_id）
```

### 原因6：用户ID隔离失效（`user_id: None` → 上下文污染）

**现象**：多个不同用户在同一个群聊中发送消息，但 AI 混淆了群配置（如把管理员<04>的数据写到员工<03>的表格）。

**日志特征**：
```
会话ID: 20260510_132946_6a476cdf
user_id: None ← 问题！
source: feishu
消息数: 6
```

**根本原因**：
1. `group_sessions_per_user: true` 已配置，但会话的 `user_id` 是 `None`
2. `build_session_key()` 在没有有效的 `participant_id` 时不附加用户 ID 到 session key
3. 导致所有用户共享同一个 session key → 上下文污染

**代码路径**：
1. `feishu.py` `_resolve_sender_profile()` — 飞书事件中 `sender.sender_id` 可能只有 `open_id`，没有 `user_id`
2. `session.py` `build_session_key()` — 当 `participant_id = source.user_id_alt or source.user_id` 为 `None` 时，即使 `group_sessions_per_user=True` 也不会隔离

**解决（已实现 — 双层兜底）**：

**层1**：`feishu.py` `_resolve_sender_profile()` — 当 `user_id` 和 `open_id` 都为 `None` 时使用确定性 hash fallback：
```python
# gateway/platforms/feishu.py (circa line 3546)
if not primary_id:
    primary_id = f"anon-{hash(str(sender_id)) & 0xFFFFFFFF:08x}"
    logger.warning("[Feishu] No user_id or open_id found; using fallback %s", primary_id)
```

**层2**：`session.py` `build_session_key()` — 当 `group_sessions_per_user=True` 但 `participant_id=None` 时使用确定性 fallback：
```python
# gateway/session.py (circa line 658)
elif isolate_user and not participant_id:
    fallback = f"anon-session-{hash(key_parts[-1]) & 0xFFFFFFFF:08x}"
    key_parts.append(fallback)
    logger.warning("build_session_key: user_id both None; using fallback %s", fallback)
```

**层3**：`feishu.py` `_process_inbound_message()` — 调试日志，追踪 `user_id` 为 `None` 的来源：
```python
if not sender_profile.get("user_id"):
    logger.warning("[Feishu] sender_profile user_id is None! chat_id=%s sender_id=%r", chat_id, sender_id)
```

**验证修复**：
```bash
# 检查是否有 user_id=None 的警告
grep -i "user_id.*None" ~/.hermes/logs/gateway.log | tail -10
# 应看到 build_session_key 的 WARNING（如果有的话，说明兜底已生效）

# 查看 session key 是否区分了用户
hermes sessions list
```

## 相关配置

- **网关配置**：`~/.hermes/config.yaml`
- **会话文件**：`~/.hermes/sessions/`
- **网关日志**：`~/.hermes/logs/gateway.log`
- **环境变量**：`env | grep FEISHU`

## 注意事项

- 网关重启后需要等待几分钟让所有会话重新建立
- 每次配置变更后必须重启网关
- 飞书群 ID 可能因群迁移等原因变化，需要定期验证
- **网关卡在 `activating (auto-restart)`**：systemd RestartSec 退避等待中。绕过：`sudo systemctl stop hermes-gateway && sudo systemctl reset-failed hermes-gateway && sudo systemctl start hermes-gateway`
- **心跳监控**：已部署 `~/.hermes/scripts/feishu-gateway-monitor.py` + cron 每30分钟检测，自动重启挂掉的网关。详见 `hermes-agent` 技能 → Gateway issues