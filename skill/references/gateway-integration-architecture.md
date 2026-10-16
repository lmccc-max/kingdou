# Kingdou 网关集成架构

## 前置拦截架构（Shadow Hook）

：Feishu gateway shadow hook 已可加载

旧记录称 feishu.py 前置拦截“从未生效/已放弃”。本次迁移中采用更保守的 **shadow hook**，不是拦截：

- 修改点：`hermes-agent 的 gateway/platforms/feishu.py（旧版布局，现在已不存在）`
- 新方法：`_run_kingdou_shadow_router(...)`
- 调用位置：`_process_inbound_message()` 收到消息后、进入正常 AI 流程前
- 效果：只调用 `~/.hermes/skills/kingdou/scripts/router/router.py` 的 `Router(shadow_only=True).route(...)`
- 不写 Bitable、不发消息、不拦截 AI，只在日志中写 `[KingdouShadow]` 和 `~/.hermes/logs/kingdou/shadow-router.log`
- 关闭：`ENABLE_KINGDOU_GATEWAY_SHADOW=false`

关键经验：`hermes gateway restart` 在该环境中可能只是 reload/USR1，未必重新加载 Python 源码；改 gateway 源码后用：

```bash
sudo systemctl restart hermes-gateway
sleep 8
hermes gateway status
```

确认 PID 更新后再观察：

```bash
grep -i 'KingdouShadow' ~/.hermes/logs/gateway.log | tail -20
tail -20 ~/.hermes/logs/kingdou/shadow-router.log
```

仍需注意：当前只是 shadow 观察，不解决“AI 同时处理导致重复提交”的根问题。真正切执行前必须增加跳过 AI 或幂等拦截策略。

## 实际工作架构（2026-05-10 最终定论）

### 现状：独立守护进程（唯一生效方案）✅ 已就绪

**feishu.py 前置拦截从未生效** — Gateway 代码修改因 Python 字节码缓存问题始终无法加载，已放弃此方案。

**独立守护进程（当前唯一工作方案）**：
- **脚本**：`scripts/piecework_interceptor.py`（守护进程）✅ 已创建 (2026-05-10 22:41)
- **提交脚本**：`scripts/submit_piecework.py`（计件数据提交）✅ 已创建 (2026-05-10 22:41)
- **方式**：监控 `~/.hermes/logs/gateway.log`，正则匹配 `Inbound group message received` 日志行
- **优势**：完全独立于 Gateway 代码，不受 Python 字节码缓存影响
- **已实测验证**：2026-05-10 22:02:59 成功拦截 "0.1 1" → 创建编码108（员工<11>表）
- **启动命令**：`cd ~/.hermes/skills/kingdou && python3 -u scripts/piecework_interceptor.py`

### ⚠️ 已知缺陷：双重记录问题

守护进程无法阻止 AI 同时处理同一消息，导致一条消息产生两条记录：
- 守护进程创建的记录（status="待审核"）
- AI 创建的重复记录（status 为空）

**影响**：实测 "0.1 1" 产生 4 条记录（编码106-109），其中仅108是守护进程写入的正确记录。

**临时应对**：手动删除 AI 创建的重复记录。

**根本解决方向**（待实现）：
1. Gateway 标记机制：守护进程处理后通过某种方式通知 Gateway 跳过 AI 处理
2. 或在 Gateway 层添加消息去重（检测同一 message_id 已被守护进程处理）

### 历史方案（已废弃）

**feishu.py 前置拦截**：修改 `_handle_message_event_data` 在消息到达时直接调用 `submit_piecework.py`。
废弃原因：Python 字节码缓存导致代码修改始终不生效，多次重启+清缓存无效。

## Python 字节码缓存陷阱

修改 `gateway/platforms/feishu.py` 后必须清除缓存：
```bash
rm -rf ~/.hermes/hermes-agent/gateway/__pycache__
rm -rf ~/.hermes/hermes-agent/gateway/platforms/__pycache__
```
⚠️ **实际经验表明清除缓存也不一定生效** — 推荐使用独立守护进程方案。

## Session 隔离修复
- gateway/run.py: session context 注入到 AI system prompt
- gateway/session.py: build_session_key 兜底，user_id 为空时不共享 session
- feishu.py: _resolve_sender_profile 兜底，user_id/open_id 都为空时使用哈希 fallback


## 生产环境切换记录



Kingdou normal business messages are handled before the AI pipeline by the Feishu gateway front-door.

Production path:

```text
hermes-agent 的 gateway/platforms/feishu.py（旧版布局，现在已不存在）
  -> _run_kingdou_gateway_router(...)
  -> ~/.hermes/skills/kingdou/scripts/router/router.py
     -> submit_piecework.py | review_piecework.py | query_salary.py
```

## Runtime behavior

- `ENABLE_KINGDOU_GATEWAY_MODE=execute` or unset: execute router in production mode.
- `ENABLE_KINGDOU_GATEWAY_MODE=shadow`: observe only; no write, no send, no AI intercept.
- `ENABLE_KINGDOU_GATEWAY_MODE=off`: disable the Kingdou gateway front-door.
- Only successful executed script results should intercept/skip the AI pipeline.
- Unknown messages, permission failures, configuration gaps, and script exceptions should continue to AI/human fallback rather than being hard-blocked.
- Replies for handled business messages must be sent by `feishu-send-message.py`; the AI must not send an extra confirmation.

## Verification commands

```bash
$KINDOU_PY -m py_compile \
  hermes-agent 的 gateway/platforms/feishu.py（旧版布局，现在已不存在） \
  ~/.hermes/skills/kingdou/scripts/router/*.py

sudo systemctl restart hermes-gateway
sleep 8
hermes gateway status

grep -i "Kingdou" ~/.hermes/logs/gateway.log | tail -50
tail -50 ~/.hermes/logs/kingdou/shadow-router.log
tail -50 ~/.hermes/logs/kingdou/shadow-router-errors.log
```

Expected gateway status after restart:

```text
Active: active (running)
Feishu websocket connected
```

## Production smoke test

In a configured Kingdou group, send from a configured employee OpenID:

```text
0.1 1
```

Expected:

1. Router classifies as `submit`.
2. Script creates a Bitable record in the group-specific table.
3. Script reads back the created record and sends confirmation via `feishu-send-message.py`.
4. Gateway logs `[KingdouScript] ... intercepted ... skipping AI pipeline`.
5. No second AI-generated group reply appears.

If the sender is not in that group's employee list, expected result is `sender_not_in_employee_list`; this should not be treated as a script bug.

## Rollback

Set:

```bash
ENABLE_KINGDOU_GATEWAY_MODE=shadow
sudo systemctl restart hermes-gateway
```

This keeps observability while preventing writes/sends/intercepts. Use `off` only if the front-door itself is suspected to be breaking unrelated gateway processing.

## Pitfalls

- The host may not have a `python` binary; use `python3` or `$KINDOU_PY`.
- Do not restore cron jobs such as `piecework-cron-guard`; gateway log polling can duplicate submissions.
- Do not log Feishu credentials or tenant tokens. Treat all tokens/secrets as `[REDACTED]`.


## chat_id 注入限制



Hermes 网关正确路由消息到群聊，但**不会将当前会话的 chat_id 注入 AI 的 system prompt**。这导致 AI 无法直接获取当前群聊的 chat_id。

## 影响

- AI 从环境变量（`FEISHU_HOME_CHANNEL` / `HERMES_SESSION_KEY`）获取的是 Home Channel 回退地址（私聊窗口 ID），不是实际群聊 ID
- AI 误将 Home Channel ID 当作群聊 ID 去匹配配置 → 匹配失败 → 回退到默认逻辑 → 数据写入错误的群
- 严重违反数据隔离原则

## 解决方案

### 从网关日志提取 chat_id

```bash
# 获取最近一条 inbound message 的 chat_id
grep "Inbound.*message received" ~/.hermes/logs/gateway.log | tail -1 | grep -oP 'chat_id=\K[^ ]+'
```

### 日志证据

```
# 网关日志（正确）：
2026-05-10 13:17:53,175 INFO gateway.platforms.feishu: [Feishu] Inbound group message received: id=om_xxx type=text chat_id=oc_<redacted-04> sender=user:ou_xxx text='0.4 40' media=0

# AI 错误使用的 ID（Home Channel）：
FEISHU_HOME_CHANNEL=oc_<redacted-05>  ← 这是私聊窗口 ID！
```

## 错误案例

**场景**: 用户在管理员<04>计件群（`oc_<redacted-04>`）发送 "0.4 40"

**AI 错误行为**:
1. 使用 `FEISHU_HOME_CHANNEL`（`oc_<redacted-05>`）去匹配配置
2. 配置中找不到该 ID
3. 回退到默认逻辑，使用员工<03>计件群的配置
4. 数据被记录到员工<03>计件群的表格中

**正确行为**:
1. 从网关日志提取 chat_id：`oc_<redacted-04>`
2. 在配置中找到管理员<04>计件群
3. 数据被记录到管理员<04>计件群的表格中

## 根本原因

这是 Hermes 网关的设计限制，不是配置错误或模型问题：
- 网关正确路由了消息（日志证明）
- 但网关没有将 `chat_id` 注入到 AI 的 system prompt 中
- AI 无法直接获取当前会话的群聊 ID

## 相关配置

```yaml
# ~/.hermes/config.yaml
group_sessions_per_user: true  # 已启用，但不影响 chat_id 注入
```

## 修复状态

- ✅ 已更新 kingdou 技能：从网关日志提取 chat_id
- ✅ 已添加防错检查清单
- ⏳ 等待 Hermes 网关支持 chat_id 注入（如未来版本支持）

