# Kingdou 脚本架构演进

## 脚本优先升级方案



When upgrading Kingdou from AI-handled operations to scripts, use a staged script-first architecture:

1. Shadow router first
   - Build a Python package under `~/.hermes/skills/kingdou/scripts/router/`.
   - Start with no writes and no Feishu sends.
   - Implement config loading, message parsing, validation, and audit logging.
   - Verify route decisions with `python3`, not `python` if `python` is unavailable.

2. Submission script second
   - Keep AI out of the normal `price quantity` path.
   - Implement `submit_piecework.py` with dry-run/no-send flags before live writes.
   - Read `~/.hermes/.env` for Feishu credentials.
   - Use Bitable field names for record creation.
   - Update status with PUT after record creation.
   - Re-read record to verify code and formula amount.
   - Apply idempotency only for real writes, not dry-run, otherwise tests poison the duplicate cache.

3. Query script third
   - Implement pagination in the Feishu client (`list_records`).
   - Add rate limiting in `~/.openclaw/workspace/cache/kingdou-rate-limit.json`.
   - Parse formula fields, rich text fields, and millisecond timestamps defensively.
   - Filter by current employee name from `openid_name_mapping` and by current group config.
   - `历史工资/以前工资` can start as current-month fallback but should be extended with month parsing before production use.

4. Review script fourth
   - Implement review after submit/query if the user asks for numbered step 2 as query or explicitly says query.
   - Search by visible `编码` to get internal `record_id`; never PUT `/records/{编码}`.
   - Reviewer name must come from `openid_name_mapping`, not message text or hard-coded defaults.

5. Router execution mode last
   - After dry-run validation, add real dispatch mode to `router.py`.
   - Keep feature flags for shadow/routing/fallback.
   - Normal messages should not enter AI; exceptions can fall back to AI.

## Implemented file pattern

Recommended files under `~/.hermes/skills/kingdou/scripts/router/`:

- `config_loader.py` — load `piecework-groups.json` and return group config.
- `message_parser.py` — classify review/query/submit/unknown.
- `validators.py` — group enabled, employee, reviewer checks.
- `audit_log.py` — JSONL logs under `~/.hermes/logs/kingdou/`.
- `feishu_client.py` — token cache, Bitable create/update/get/search/list.
- `idempotency.py` — duplicate submit guard.
- `reply_templates.py` — fixed submit/query/error templates.
- `submit_piecework.py` — dry-run/no-send capable submission flow.
- `rate_limit.py` — query quota cache.
- `field_utils.py` — parse Feishu field values.
- `query_salary.py` — dry-run/no-send capable salary query flow.

## Commands

Syntax check:

```bash
PYTHONPATH=~/.hermes/skills/kingdou/scripts python3 -m py_compile ~/.hermes/skills/kingdou/scripts/router/*.py
```

Shadow route test:

```bash
PYTHONPATH=~/.hermes/skills/kingdou/scripts python3 -m router.router \
  oc_<redacted-06> \
  ou_<redacted-02> \
  '0.12 103'
```

Submit dry-run:

```bash
PYTHONPATH=~/.hermes/skills/kingdou/scripts python3 -m router.submit_piecework \
  oc_<redacted-06> \
  ou_<redacted-02> \
  '0.12 103' --dry-run --no-send
```

Query dry-run:

```bash
PYTHONPATH=~/.hermes/skills/kingdou/scripts python3 -m router.query_salary \
  oc_<redacted-06> \
  ou_<redacted-02> \
  '今天工资' --dry-run --no-send
```

## Pitfalls

- The environment may not have `python`; use `python3`.
- Do not return an empty assistant response after tool calls in CLI sessions. Summarize the tool result and continue the task.
- `search_files` may not list files reliably in hidden skill directories; use `/usr/bin/find` from terminal to verify created files.
- Do not let dry-run consume idempotency or query quotas.
- Do not send Feishu replies during shadow mode or dry-run.


## 脚本主导迁移方案



用户要求将 kingdou 计件工资流程从 AI 主导升级为脚本主导，目标是：常规提交、审核、查询不再依赖 AI 判断；AI 只在异常、配置缺失、字段变更、新群接入等场景兜底。

## 推荐模式

采用 B+C 混合方案：

- B 底线：纯脚本主导，AI 不参与常规流程。
- C 主方案：脚本执行主流程，AI 只做异常兜底。

最终状态：

- 计件提交：纯脚本
- 审核：纯脚本
- 查询：纯脚本
- 新群接入：AI 辅助
- 异常修复：AI 兜底

## 实施顺序

1. 影子模式，只读不写
   - 实现 router.py、config_loader.py、message_parser.py、validators.py、audit_log.py
   - 只记录脚本判断结果，不创建记录、不发送群消息

2. 计件提交脚本化
   - 实现 submit_piecework.py
   - 解析纯“单价 数量”消息
   - 读取 piecework-groups.json
   - 校验员工身份
   - 创建 Bitable 记录
   - 更新审核状态为“待审核”
   - 查询确认编码和金额
   - 通过 feishu-send-message.py 发送确认
   - 加入幂等保护：chat_id + sender_id + message_text + 时间窗

3. 审核脚本化
   - 实现 review_piecework.py
   - 校验审核员权限
   - 查询编码记录
   - 审核通过：状态设为“已通过 YYYY-MM-DD HH:mm”，审核人来自 openid_name_mapping
   - 审核拒绝：清空单价、数量、金额，状态设为“已拒绝 YYYY-MM-DD HH:mm”，编码保留
   - 审核后重新查询验证

4. 查询脚本化
   - 实现 query_salary.py
   - 支持今天工资、本月工资、历史工资
   - 读取频率限制缓存 ~/.openclaw/workspace/cache/kingdou-rate-limit.json
   - 只查询当前群当前员工，只统计已通过记录
   - 金额需做多路验证

5. 统一 router.py 接管入口
   - 输入：chat_id、sender_id、message_id、message_text、receive_time
   - 路由优先级：review > query > submit > ignore/fallback
   - 开关：ENABLE_SCRIPT_ROUTING、ENABLE_AI_FALLBACK、ENABLE_SHADOW_MODE

6. 灰度上线
   - 先 ENABLE_SHADOW_MODE=true，只观察
   - 再只启用员工<11>计件群：oc_<redacted-06>
   - 先切提交，再切审核，最后切查询

7. 回滚
   - ENABLE_SCRIPT_ROUTING=false 可一键关闭脚本路由
   - group.enabled=false 可关闭单群
   - group.features.submit/review/query=false 可关闭单功能

## 验收标准

- 计件消息“0.12 103”能创建记录，返回编码，状态待审核，金额由飞书公式计算，不重复提交。
- 审核员可通过/拒绝，非审核员不可操作；审核后必须重新查询验证。
- 查询受频率限制，只查本人本群，不跨群泄露。
- 所有操作记录日志，可定位、可回滚。

## 执行纪律

实现时不要只创建一个空目录或微小脚手架后停下来询问。用户偏好直接推进到可验证里程碑：至少完成影子模式核心模块并跑通样例测试后再汇报。


## 路由脚本迁移记录



将 kingdou 计件工资流程从 AI 主判断迁移到脚本主判断时使用。目标是：正常提交/审核/查询由脚本处理，AI 只做异常兜底。

## 已实现脚本结构

路径：`~/.hermes/skills/kingdou/scripts/router/`

- `router.py`：统一入口；默认影子模式，只分类不执行；`--execute` 后分发业务脚本。
- `config_loader.py`：读取 `configs/piecework-groups.json`，按 `chat_id` 获取群配置。
- `message_parser.py`：识别 submit/review/query/unknown。
- `validators.py`：群启用、员工、审核员权限校验。
- `audit_log.py`：写入 `~/.hermes/logs/kingdou/shadow-router.log` 和 errors log。
- `feishu_client.py`：tenant token、Bitable 创建/更新/查询/分页列表/按编码搜索。
- `idempotency.py`：提交幂等；key = `chat_id|sender_id|message_text`，默认 60 秒。
- `reply_templates.py`：提交/查询错误和成功模板。
- `submit_piecework.py`：计件提交脚本，支持 `--dry-run --no-send`。
- `review_piecework.py`：审核脚本，按“编码”搜索真实 `record_id`，PUT 更新，审核后 GET 验证。
- `query_salary.py`：工资查询脚本，支持频率限制和 `--dry-run --no-send`。
- `rate_limit.py`：今天查询每天 3 次；自定义/本月/历史每天 1 次、每周 3 次。
- `field_utils.py`：解析飞书字段、公式金额、毫秒时间戳、审核状态。

## 统一入口用法

默认影子模式，只判断：

```bash
PYTHONPATH=~/.hermes/skills/kingdou/scripts python3 -m router.router \
  <chat_id> <sender_open_id> '0.12 103'
```

执行模式 dry-run，不写飞书、不发送消息：

```bash
PYTHONPATH=~/.hermes/skills/kingdou/scripts python3 -m router.router \
  <chat_id> <sender_open_id> '0.12 103' \
  --execute --dry-run --no-send
```

真实执行时去掉 `--dry-run` 和/或 `--no-send`。上线前必须先灰度。

## 网关前置影子调用

已在 Hermes Feishu adapter 中加入观察型前置调用：

文件：`hermes-agent 的 gateway/platforms/feishu.py（旧版布局，现在已不存在）`

位置：`_process_inbound_message()` 中，收到飞书消息后、进入正常 AI 流程前调用：

```python
self._run_kingdou_shadow_router(chat_id=chat_id, sender_id=str(sender_primary), text=text, message_id=message_id)
```

该调用只做观察：

- 不拦截
- 不写 Bitable
- 不发飞书消息
- 不影响原 AI 流程
- 写 gateway 日志 `[KingdouShadow] ...`
- 写 kingdou shadow-router JSON log

关闭开关：

```bash
ENABLE_KINGDOU_GATEWAY_SHADOW=false
```

## 关键验证命令

检查语法：

```bash
$KINDOU_PY -m py_compile \
  hermes-agent 的 gateway/platforms/feishu.py（旧版布局，现在已不存在） \
  ~/.hermes/skills/kingdou/scripts/router/*.py
```

重启网关：

```bash
sudo systemctl restart hermes-gateway
sleep 8
hermes gateway status
```

注意：`hermes gateway restart` 在该环境中可能只是触发 reload/USR1，不一定重新加载 Python 代码。改动 gateway 源码后优先用 `sudo systemctl restart hermes-gateway` 确保 PID 更新。

观察日志：

```bash
grep -i 'Inbound .*message received' ~/.hermes/logs/gateway.log | tail -20
grep -i 'KingdouShadow' ~/.hermes/logs/gateway.log | tail -20
tail -20 ~/.hermes/logs/kingdou/shadow-router.log
```

## 已验证 dry-run 结果

- submit：`0.12 103` → `route_type=submit`，execute dry-run 返回 `dry_run_no_write`。
- review：`审核通过 RF2026040005` → `route_type=review`，审核员可通过 dry-run，非审核员返回 `sender_not_in_reviewer_list`。
- query：`今天工资` → `route_type=query`，execute dry-run 返回 `dry_run_no_api`。

## 注意事项

1. 网关前置当前只是 shadow，不要误认为已经拦截 AI。
2. 真正切执行前必须解决“AI 仍会处理同一消息”的重复提交风险。
3. 审核人必须从 `openid_name_mapping` 取，禁止从消息内容解析或写死默认值。
4. 创建 Bitable 记录使用字段名称；更新记录用 PUT；用户给的是“编码”，更新前必须搜索获取真实 `record_id`。
5. 飞书日期时间是毫秒时间戳，解析时要除以 1000。

