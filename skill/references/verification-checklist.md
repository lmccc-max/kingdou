# 全功能验证清单与常用命令

---

## 全功能验证清单

当用户要求“验证 kingdou.skill / Kingdou 技能全部功能是否正常”时，按以下顺序执行，优先使用 dry-run / no-send，避免污染生产数据和飞书群消息：

1. 结构与配置：确认 `SKILL.md`、`configs/piecework-groups.json`、`scripts/router/*.py`、`~/.hermes/plugins/kingdou/` 存在；解析 JSON 并报告群数量；确认核心 router 模块无缺失。
2. 编译：运行 `py_compile` 覆盖 `~/.hermes/plugins/kingdou/__init__.py` 和 `~/.hermes/skills/kingdou/scripts/router/*.py`。
3. 网关集成：检查插件 `__init__.py` 包含 `pre_gateway_dispatch`、`ENABLE_KINGDOU_GATEWAY_MODE`、`from router.router import Router`、`KingdouScript`、`KingdouShadow`；`hermes plugins list` 中 kingdou 为 `enabled`。
4. 网关运行：`systemctl --user is-active hermes-gateway` 必须为 `active`；查看近期 journal 中飞书 websocket 是否连接成功。
5. cron 冲突：执行 cron job 列表检查，确认没有 `piecework-cron-guard` 或其他独立并行提交路径；保留飞书网关心跳任务是正常的。
6. 路由功能：用已登记的群 + 员工 open_id 验证 `submit`、`pending_review`、`query`、`review approve/reject/batch/range`、`unknown`；执行模式使用 `--execute --dry-run --no-send`。空配置（`groups: {}`）下全部返回 `group_not_configured`；群已登记而员工/管理员未登记时返回 `sender_not_in_employee_list` / `sender_not_in_reviewer_list` —— 两者都是预期的空载态，不是故障。
7. API 只读验证：对待审核和工资查询可执行 `--execute --no-send`，验证真实 Bitable 读取能力但不发送飞书消息。注意 `--no-send` 不等于 dry-run（见 SKILL.md 的「常见陷阱」）。
8. 错误日志：检查 `~/.hermes/logs/kingdou/*errors*.log` 最近 15 分钟是否有新增错误；历史错误可以注明为旧记录，不应误判为当前故障。
9. 最终结论必须明确列出：正常项、异常项、是否执行真实写入/审核/发消息；默认不要做真实写入。



`~/.hermes/skills/kingdou/references/`

重要文档：

- `script-architecture-evolution.md` — 脚本架构演进（合并自 router-migration、led-migration、first-upgrade）
- `gateway-integration-architecture.md` — 网关集成架构（合并自 pre-intercept、script-first-production、chatid-limitation）
- `standard-reply-template.md` — 标准回复模板
- `piecework-submission-workflow.md` — 计件提交完整工作流程
- `pending-review-operations.md` — 待审核查询操作指南（合并自 manual-query、script-workflow、query-recipes）
- `batch-operations.md` — 批量操作指南（合并自 review-guide、review-limitations、submission-pattern）
- `feishu-api-patterns.md` — 飞书 API 调用模式参考
- `feishu-direct-message.md` — 机器人主动私聊(open_id)能力边界、错误码对照、诊断流程
- `scripts/check-dm-capability.py` — 私聊可达性探针（按姓名/`--open-id`/`--self` 测试并解读错误码）
- `lessons-learned.md` — 历史教训与经验总结
- `configuration-guide.md` — 配置管理完整指南（合并自 config-structure、template、update-guide、update-notes）
- `feishu-gateway-routing-detailed.md` — 飞书网关路由调试指南
- `feishu-session-context-fix-patches.md` — 会话上下文注入修复补丁
- `architecture-and-deployment.md` — 系统架构与部署
- `performance-optimization-guide.md` — 性能优化实施指南
- `autonumber-encoding-fix.md` — AutoNumber 编码字段问题（技术参考）
- `today-salary-query.md` — 工资查询处理模式
- `api-data-parsing.md` — 飞书 Bitable API 数据解析指南
- `bitable-field-type-mapping.md` — Bitable API 字段类型映射
- `integration-guide.md` — Kingdou 集成指南
- `rate-limit-templates.md` — 频率限制提示模板
- `admin-replenishment-guide.md` — 管理员补录操作指南
- `manual-routing-pattern.md` — 手动路由模式
- `review-permission-denied.md` — 员工发送「拒绝/通过」被权限拒绝时的路由器契约与 AI 回复模板
- `backup-restore-install.md` — 从备份 tar / 旧机目录安装或恢复 kingdou 的完整步骤（清空身份、残留扫描、验证）

---

## 常用验证命令

```bash
$KINDOU_PY -m py_compile \
  ~/.hermes/plugins/kingdou/__init__.py \
  ~/.hermes/skills/kingdou/scripts/router/*.py
```

影子分类验证（把 `<chat_id>` / `<员工open_id>` 换成 `configs/piecework-groups.json` 里已登记的群与身份。
当前是空配置：未登记的群一律返回 `group_not_configured`，只有群登记了而员工没登记才是 `sender_not_in_employee_list`）：

```bash
PYTHONPATH=~/.hermes/skills/kingdou/scripts \
$KINDOU_PY -m router.router \
  <chat_id> <员工open_id> '0.12 103'
```

执行 dry-run，不写飞书、不发消息：

```bash
PYTHONPATH=~/.hermes/skills/kingdou/scripts \
$KINDOU_PY -m router.router \
  <chat_id> <员工open_id> '0.12 103' --execute --dry-run --no-send
```

检查网关集成（插件形态）：

```bash
python3 - <<'PY'
from pathlib import Path
p = Path('~/.hermes/plugins/kingdou/__init__.py')
t = p.read_text(errors='ignore')
for needle in ['pre_gateway_dispatch','ENABLE_KINGDOU_GATEWAY_MODE','from router.router import Router','KingdouScript','KingdouShadow']:
    print(needle, needle in t)
print('plugin.yaml', Path('~/.hermes/plugins/kingdou/plugin.yaml').exists())
PY
hermes plugins list | grep -i kingdou
```

重启网关（本机是 **user** 单元；必须在网关进程之外的 shell 里执行——
在 Hermes 会话内执行会被 `terminal_tool_guards` 拦下，因为网关会先杀掉这条命令）：

```bash
systemctl --user restart hermes-gateway
systemctl --user is-active hermes-gateway
```
