# 审核权限不足 / 员工误用「拒绝」的处理

路由器对审核指令做权限闸门：`validators.py::is_reviewer(openid, group, cfg)`
= `openid in global_admins` **或** `openid in group.independent_admins`。

员工（在 `group.employee_list` 中）不满足该条件 → `sender_not_in_reviewer_list`。

## 路由器行为契约

| 场景 | route | ok | 脚本发消息? | 网关拦截 AI? | 谁回复 |
|------|-------|----|------------|-------------|--------|
| 管理员/审核员 拒绝/通过 | review | true | ✅ | ✅ | 脚本 |
| **员工** 发送 拒绝/通过 | review | **false** | ❌ | ❌ | **AI** |
| 本群无关用户 发送 拒绝/通过 | review | false | ❌ | ❌ | AI |

审计日志形如（`~/.hermes/logs/kingdou/shadow-router.log`）：

```json
{"ts":"2026-09-26T19:00:19","chat_id":"oc_<redacted-01>",
 "sender_id":"ou_<redacted-07>","route":"review",
 "reason":"review_keyword","group":"员工<02>计件群","ok":false,"executed":false}
{"ts":"2026-09-26T19:00:19","chat_id":"...","sender_id":"...","route":"review",
 "reason":"sender_not_in_reviewer_list","group":"员工<02>计件群","ok":false,"executed":false}
```

注意两条：第一条只是分类（`review_keyword`），第二条才是权限拒绝。

## 正确处置（会话实例 2026-09-26）

发送者 `ou_<redacted-07>`（员工<02>，本群唯一员工）
发送 `拒绝810和811`。810（0.15×196）、811（0.12×195）均为员工<02>本人、状态「待审核」。

1. 读中央配置确认权限：本群 `independent_admins: []`，`global_admins` 才是审核员。
2. dry-run 复现：`--execute --dry-run --no-send` → `sender_not_in_reviewer_list`。
3. 只读查 Bitable 确认 810/811 的 `姓名` 与 `审核状态`（确认是本人待审核记录）。
4. dry-run 验证 `取消 810 811` → `{"ok": true, "route": "cancel", "data": {"codes": ["810","811"], "operator": "员工<02>"}}`。
5. 回复（AI 回复，群里此前无任何脚本消息）：说明无审核权限 + 给出 `取消 810 811` 建议 + 提示可转告审核员。

**不要**做的：不要因为「反正都是不计入工资」就自行执行取消或伪造拒绝。
「已拒绝」与「已取消」在表里是两种状态、留痕字段不同（审核人 vs 备注），
语义需用户明确；员工侧的合法路径只有 `取消`。

## 相关群配置（2026-09 快照）

员工<02>计件群 `oc_<redacted-01>`
- app_token `app_<redacted-04>`, table_id `tbl_<redacted-03>`
- employee_list `["ou_<redacted-07>"]`（员工<02>）
- independent_admins `[]` → 审核员 = global_admins
- global_admins: `ou_<redacted-10>`(管理员<01>)、
  `ou_<redacted-03>`(管理员<02>)、`ou_<redacted-06>`(管理员<03>)

多数单员工群（员工<03>、员工<04>、员工<05>、员工<06>、员工<07>、员工<08>、员工<09>、员工<10>）
的 `independent_admins` 同样为空 → 审核一律落到 global_admins。
只有 员工<01>计件群 有独立审核员 `ou_<redacted-11>`。

---

### 审核权限不足（员工发送「拒绝/通过」）—— 必须由 AI 回复

审核权限 = `global_admins` ∪ 本群 `independent_admins`（见 `validators.py::is_reviewer`）。
**员工（在 `employee_list` 中）不是审核员。** 员工发送「拒绝810和811」时路由器返回：

```json
{"ok": false, "executed": false, "reason": "sender_not_in_reviewer_list", "route": "review"}
```

`ok=false` → **脚本不发飞书消息、网关不拦截 AI** → 由 AI 负责回复。

标准回复（简洁、零废话，先判权限再给可行路径）：

```
⚠️ 拒绝（审核）是管理员操作，你是本群员工（<姓名>），无审核权限，系统已拦截该请求。

810、811 都是你本人提交的「待审核」记录，如需作废，请发送：

**取消 810 811**

（如需由管理员执行拒绝，请转告审核员：管理员<03> / 管理员<02> / 管理员<01>）
```

要点与红线：

- **绝不**替员工伪造审核人执行「拒绝」——审核人必须来自 `openid_name_mapping` + 权限列表（红线 #4）。
- 员工想作废**自己**的待审核记录 → 引导走 `取消`（`cancel_piecework.py` 对员工本人记录合法可用）。
- 给出建议命令前，先 dry-run 验证该路由对该发送者可用：
  `PYTHONPATH=. python -m router.router <chat_id> <sender_openid> '取消 810 811' --execute --dry-run --no-send`
  期望 `{"ok": true, "route": "cancel", "data": {"codes": ["810","811"], "operator": "<姓名>"}}`。
- 诊断顺序：读中央配置本群 entry（`employee_list` / `independent_admins`）→ 查 `global_admins` → dry-run 路由器确认 route/reason。
- 会话实例与群配置见 `references/review-permission-denied.md`。
