---
name: kingdou
description: 飞书群计件提交、审核、待审核查询、工资查询，脚本优先拦截 AI。
version: 1.1.0
author: lmccc-max, Hermes Agent
license: MIT
platforms: [linux]
metadata:
  hermes:
    tags: [feishu, lark, bitable, piecework, payroll, gateway-hook]
---

# Kingdou 计件工资系统

飞书群里的计件数据（提交 / 审核 / 取消 / 待审核查询 / 工资统计）先由 `scripts/router/` 的脚本处理：
网关插件在消息进入 AI 之前调用 router，脚本处理成功就拦下这条消息；AI 只负责脚本管不了的部分
（权限不足的解释、群未配置、脚本异常）。业务规则全部在本目录内，不依赖外部文档。

> **本文档与 `references/` 里的人员姓名、群名、chat_id / app_token / table_id / view_id / field_id /
> 租户域名 / app_id / open_id 全部是占位符**（形如 `员工<01>`、`管理员<01>`、`oc_<redacted-01>`、
> `app_<redacted-02>`），不是真实值，照抄进配置不会生效。真实值在飞书后台、各群的 URL 和实际消息里取。

> **「全新安装 / 不保留具体 id / 不保留某人某物」= 按最彻底的理解执行**：一次把业务内容（群、群名、
> chat_id、app_token、table_id、fields_detail）与人员信息（open_id、姓名、含人名的群名）全部清掉，
> 只留 schema。用户点到的那项是**下限不是上限** —— 分几轮被纠正比一次做到位贵得多。
> 完整步骤与验证见 `references/backup-restore-install.md`。

## When to Use

- 飞书群里出现 `0.12 103`（两个数字）、`通过123` / `拒绝123` / `同意全部`、`取消 001` / `取消全部`、
  `待审核`、`查工资` / `今天工资` 这类消息
- 用户要新增计件群、登记员工/管理员、改配置
- 用户要验证、排查、重装或从备份恢复 kingdou
- 用户问「这个 skill/备份能不能传 GitHub / 缺什么格式」或要做可发布版 → 加载 `hermes-agent-skill-authoring`，走它的「导出成独立仓库」一节（敏感扫描清单、路径归一化、install.sh 验收都在那）
- 不适用：非飞书平台、与计件无关的对话 —— 不要为了「保险」去跑脚本

## Prerequisites

- Hermes Agent 网关已接飞书：`FEISHU_APP_ID` / `FEISHU_APP_SECRET` 在 `~/.hermes/.env`
  （`scripts/router/feishu_client.py` 自己读；不要打印或写进日志）
- 解释器：Hermes 运行时环境自带 `requests`。Hermes 会话里就是 `python3`；
  从普通 shell 跑请显式指定：`KINDOU_PY=<hermes 运行时 venv>/bin/python`
- 中央配置：`~/.hermes/skills/kingdou/configs/piecework-groups.json`。本仓库是空模板 `groups: {}`：
  群/员工登记之前系统处于空载（不写库、不发消息、不拦截 AI）
- 网关插件：`~/.hermes/plugins/kingdou/`（钩子 `pre_gateway_dispatch`）
- 日志目录：`~/.hermes/logs/kingdou/`

## How to Run

```bash
KINDOU_PY=${KINDOU_PY:-python3}
S="$HOME/.hermes/skills/kingdou/scripts"

# 安全预览：不写 Bitable、不发消息（验证路由/权限，日常首选）
PYTHONPATH=$S $KINDOU_PY -m router.router <chat_id> <sender_openid> '<message>' --execute --dry-run --no-send

# 生产执行：写 Bitable + 脚本自己发飞书消息
PYTHONPATH=$S $KINDOU_PY -m router.router <chat_id> <sender_openid> '<message>' --execute

# 只看分类，不执行（影子）
PYTHONPATH=$S $KINDOU_PY -m router.router <chat_id> <sender_openid> '<message>'
```

插件与网关：

```bash
hermes plugins enable kingdou / hermes plugins disable kingdou   # 启用/停用（会热加载）
systemctl --user restart hermes-gateway        # 必须在网关进程之外的 shell 里执行
```

环境开关 `ENABLE_KINGDOU_GATEWAY_MODE`：`execute`（默认，成功后拦截 AI）/ `shadow`（只观察）/
`off`（关闭前置路由）。

## Procedure

1. 按 How to Run 跑一次（能预览就带 `--dry-run`），拿到 JSON：`route` / `ok` / `executed` / `reason`。
2. `ok=true && executed=true` → 脚本已自行发过飞书群消息：**AI 不再发任何群消息**，会话里只给最简确认。
3. `ok=false` → 脚本没发消息、网关没拦截 → AI 按 `reason` 回复：
   `sender_not_in_reviewer_list`（员工误用审核，模板见 `references/review-permission-denied.md`）、
   `sender_not_in_employee_list`（非本群员工）、`group_not_configured`（群未登记）、
   `record_not_found`（编码不存在）等。
4. 需要改动（新增群/员工、改配置）→ 走 `references/onboarding-new-group.md`。
5. 完成判据：路由 JSON 的 `route`/`reason` 符合预期，且没有计划外的写入或消息。


## 运行时架构

飞书网关前置调用 Kingdou Router：

- 网关集成点：`~/.hermes/plugins/kingdou/__init__.py`（Hermes 插件，钩子 `pre_gateway_dispatch`）
  - 旧版是直接改 `gateway/platforms/feishu.py` 里的 `_run_kingdou_gateway_router()`；当前 Hermes 已把飞书拆成
    插件（`plugins/platforms/feishu/adapter.py`），且 core 提供官方钩子，因此改用插件形态（`hermes update` 不会冲掉）。
  - 插件只做转发，业务规则全部在本 skill 内，日志标记沿用 `[KingdouScript]` / `[KingdouShadow]`。
- Kingdou 独立运行时：`~/.hermes/skills/kingdou/scripts/router/`
- 配置文件：`~/.hermes/skills/kingdou/configs/piecework-groups.json`
- 日志目录：`~/.hermes/logs/kingdou/`
- 文档资料：`~/.hermes/skills/kingdou/references/`
- 解释器：`$KINDOU_PY` —— Hermes 运行时环境的 venv（含 `requests`，网关进程用的就是它）。
  Hermes 会话里不设也行，`python3` 就是它；从普通 shell 跑请显式 export。

网关调用逻辑：

- `plugins/kingdou/__init__.py::_on_pre_gateway_dispatch()` → `skills/kingdou/scripts/router/router.py`
- 环境开关：`ENABLE_KINGDOU_GATEWAY_MODE`
  - `execute`（默认）：生产模式，脚本成功后拦截 AI（钩子返回 `{"action": "skip"}`），避免重复回复
  - `shadow`：只观察分类，不写飞书、不发消息、不拦截 AI
  - `off`：关闭 Kingdou 前置路由
- 插件启停：`hermes plugins enable kingdou` / `hermes plugins disable kingdou`（enabling 会热加载插件；
  改插件源码或要彻底重载时重启网关）
- 重启网关：`systemctl --user restart hermes-gateway`（必须在网关进程之外的 shell 里执行）


## 独立模块结构

`~/.hermes/skills/kingdou/scripts/router/` 已按模块化结构拆分：

- `router.py`：统一入口，提供 `Router` / `DispatchResult`，兼容飞书网关 `from router.router import Router`
- `config_loader.py`：读取并缓存 `configs/piecework-groups.json`
- `message_parser.py`：识别 submit / review / cancel / pending_review / query / unknown
- `validators.py`：员工、管理员、审核员权限判断
- `audit_log.py`：写入 `shadow-router.log` 和错误日志
- `feishu_client.py`：飞书 tenant token、消息发送、Bitable 创建/查询/更新
- `field_utils.py`：飞书字段解析、金额、编码、时间格式
- `reply_templates.py`：标准回复模板
- `submit_piecework.py`：计件提交处理
- `review_piecework.py`：审核通过/拒绝处理
- `cancel_piecework.py`：员工取消自己的计件记录（`取消 001`）
- `tests/test_cancel_piecework.py`：取消功能回归测试（假 FeishuClient，不碰生产数据）
- `tests/verify_cancel_real_readonly.py`：真实 Bitable 只读验证（写操作被桩替换）
- `tests/test_gateway_plugin.py`：网关插件接线自测（`pre_gateway_dispatch` 放行/拦截/开关/fail-open 契约，全部用桩，不碰生产）
- `scripts/register_group.py`：新群/新员工入职登记（见 `references/onboarding-new-group.md`）
- `scripts/scrub_restore_identifiers.py`：去标识化工具（标识符 + 姓名 → 稳定占位符，幂等，
  退出码 1 = 还有残留），从备份恢复时按 `references/backup-restore-install.md` 第 6 步用
- `scripts/make_clean_backup.py`：打干净备份包（先跑上面的去标识化脚本当预检，再组装 + 打包 + 验证，
  用法见 `references/backup-restore-install.md`「备份包约定」）
- `query_pending_reviews.py`：待审核查询
- `query_salary.py`：工资统计查询（✅ 已修复，自动按今日日期过滤）
- `query-today-salary.py`：今日工资专用查询脚本（详细版本，包含逐条记录展示）
- `idempotency.py`：幂等辅助
- `rate_limit.py`：频率限制辅助


## Quick Reference（业务触发与权限）

计件提交：

- 格式：两个数字，例如 `0.12 103`
- 普通提交：发送者必须是本群员工
- 管理员代提交：管理员发送时使用本群第一个员工

审核：

- 通过：`通过123`、`同意 123`、`approve123`
- 拒绝：`拒绝123`、`不同意 123`、`reject123`
- 批量：`同意全部`、`全部同意`、`全部通过`、`全部拒绝`、`通过123 124 125`、`同意279-289`

待审核：

- `待审核`
- `查看待审核`
- `未审核`

取消（员工撤销自己发错的记录）：

- `取消 001`、`取消001`、`撤销 5`、`作废 1-3`（多编码/区间同样支持）
- `取消全部` / `全部取消`（**仅审核员/管理员**可用，取消本群所有待审核记录）
- 语义与红线见 `references/cancel-operations.md`


## 工资查询：

- `查工资`
- `工资查询`
- `今天工资`
- `本月工资`
- `历史工资`
- `昨天工资`

**重要**：`handle_query` 函数不自动按日期过滤，返回该员工所有记录。要查询今日工资，使用专用脚本：
```bash
# 预览今日工资（不发送）
PYTHONPATH=~/.hermes/skills/kingdou/scripts \
$KINDOU_PY \
~/.hermes/skills/kingdou/scripts/query-today-salary.py <chat_id>

# 查询并发送到群
PYTHONPATH=~/.hermes/skills/kingdou/scripts \
$KINDOU_PY \
~/.hermes/skills/kingdou/scripts/query-today-salary.py <chat_id> --send
```


## 首要原则

处理计件相关请求（提交、审核、查询、配置）时，**必须首先加载此 skill**，而不是尝试直接读取本地配置文件或手动处理。此 skill 包含完整的业务逻辑和脚本调用方式。


## 常见陷阱

### ⚠️ `--no-send` ≠ dry-run（静默写入陷阱）
`--no-send` 只抑制飞书消息发送，**不阻止 Bitable 写入操作**。审核/提交等修改操作仍会执行。

| 标志组合 | 效果 |
|----------|------|
| `--execute --dry-run --no-send` | 完全模拟，不写 Bitable、不发消息 ✅ 安全 |
| `--execute --no-send`（无 `--dry-run`）| **写入 Bitable** 但不发飞书消息 ⚠️ 静默修改 |
| `--execute` | 写入 Bitable + 发飞书消息（生产模式）|

**教训**（2026-07-09）：对"全部同意"使用 `--no-send` 预览时实际批准了2条记录，再次运行返回 `record_not_found`，只能手动构建确认消息。**安全检查必须同时带 `--dry-run`。**

### Python 缓存
修改脚本后必须清理缓存，否则会执行旧代码：
```bash
find ~/.hermes/skills/kingdou/scripts -name "*.pyc" -delete
find ~/.hermes/skills/kingdou/scripts -name "__pycache__" -type d -exec rm -rf {} +
```


## 关键红线

1. 脚本成功处理后必须拦截 AI，禁止 AI 二次回复。
2. 飞书群里的标准确认消息只能由脚本发送。
3. 严禁跨群读取或泄露其他群计件数据。
4. 审核人必须来自配置映射：会话 sender OpenID → `openid_name_mapping`；禁止从消息正文猜审核人。
5. 不要恢复 `piecework-cron-guard` 这类并行提交路径，避免重复记录。
6. 修改脚本后必须编译验证并重启飞书网关。


## Verification

最小验证（不碰生产数据）：

```bash
S="$HOME/.hermes/skills/kingdou/scripts"; KINDOU_PY=${KINDOU_PY:-python3}
PYTHONPATH=$S $KINDOU_PY -m py_compile $S/router/*.py $HOME/.hermes/plugins/kingdou/__init__.py
PYTHONPATH=$S $KINDOU_PY $S/tests/test_cancel_piecework.py   # 31 项取消回归
PYTHONPATH=$S $KINDOU_PY $S/tests/test_gateway_plugin.py     # 9 项插件接线
python3 -m json.tool $HOME/.hermes/skills/kingdou/configs/piecework-groups.json > /dev/null
hermes plugins list | grep -i kingdou
systemctl --user is-active hermes-gateway
```

空配置下路由返回 `group_not_configured`、群已登记而员工未登记返回 `sender_not_in_employee_list`
—— 两者都是预期的空载态，不是故障。全量清单见 `references/verification-checklist.md`。

## 参考文档

细节都在 `references/`，按需加载：

| 文件 | 内容 |
|------|------|
| `backup-restore-install.md` | 从备份安装/恢复、去标识化、备份包约定 |
| `onboarding-new-group.md` | 新增计件群 / 登记员工与管理员（`scripts/register_group.py`） |
| `configuration-guide.md` | 配置结构、字段模板、JSON 陷阱、缓存、独立群配置 |
| `piecework-submission-workflow.md` | 计件提交完整流程与配置体系 |
| `cancel-operations.md` | 取消功能：触发、软取消语义、权限 |
| `review-permission-denied.md` | 员工误用审核 → 路由器契约与 AI 回复模板 |
| `pending-review-operations.md` | 待审核查询 |
| `batch-operations.md` | 批量审核 |
| `manual-routing-pattern.md` | 手动路由与消息发送的责任边界 |
| `verification-checklist.md` | 全功能验证清单与常用命令 |
| `feishu-api-patterns.md` | 飞书 API 调用模式（token / Bitable / 错误码） |
| `feishu-direct-message.md` | 主动私聊能力边界、可用范围、错误码 |
| `feishu-gateway-routing-detailed.md` | 网关路由调试 |
| `feishu-session-context-fix-patches.md` | 会话上下文注入修复 |
| `gateway-integration-architecture.md` | 网关集成演进与生产切换 |
| `script-architecture-evolution.md` | 脚本架构演进 |
| `architecture-and-deployment.md` | 系统架构与部署 |
| `admin-replenishment-guide.md` | 管理员补录 |
| `today-salary-query.md` | 工资查询处理模式 |
| `api-data-parsing.md` / `bitable-field-type-mapping.md` | Bitable 数据解析与字段类型 |
| `autonumber-encoding-fix.md` | AutoNumber 编码字段 |
| `integration-guide.md` / `performance-optimization-guide.md` / `rate-limit-templates.md` / `lessons-learned.md` | 集成 / 性能 / 限流 / 历史教训 |
