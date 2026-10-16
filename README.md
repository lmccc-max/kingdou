# Kingdou 计件工资系统（飞书 + Hermes Agent）

飞书群里的计件数据由脚本先行处理：Hermes 网关在消息进入 AI 之前调用 router，脚本处理成功就
拦下这条消息（脚本自己发群消息），AI 只负责脚本管不了的部分——避免脚本与 AI 双重回复。

| 业务 | 群里发什么 | 谁能用 |
|------|-----------|--------|
| 计件提交 | `0.12 103`（单价 数量） | 本群员工；管理员代提交用本群第一个员工 |
| 审核通过 | `通过123` / `同意 123` / `approve123` | 审核员 / 管理员 |
| 审核拒绝 | `拒绝123` / `不同意 123` / `reject123` | 审核员 / 管理员 |
| 批量审核 | `同意全部` / `通过123 124 125` / `同意279-289` | 审核员 / 管理员 |
| 待审核 | `待审核` / `查看待审核` | 审核员 / 管理员 |
| 取消 | `取消 001` / `撤销 5` / `作废 1-3`；`取消全部` | 员工（只能取消本人待审核记录）；`取消全部` 仅审核员 |
| 工资 | `查工资` / `今天工资` / `本月工资` / `历史工资` | 员工本人 / 审核员 |

数据落在飞书多维表格（Bitable）里，每个群一张表；群与群之间数据完全隔离。

## 目录结构

```
kingdou/
├── skill/          → 安装到 ~/.hermes/skills/kingdou/
│   ├── SKILL.md            # 给 agent 看的总入口（触发词、命令、流程、红线）
│   ├── configs/            # 中央配置（本仓库是空模板 groups: {}）
│   ├── references/         # 全部细节文档：配置、审核、取消、工资、排障、历史
│   └── scripts/            # router 与配套工具（含测试）
├── plugin/         → 安装到 ~/.hermes/plugins/kingdou/
│   ├── plugin.yaml         # name / version / provides_hooks
│   └── __init__.py         # pre_gateway_dispatch 钩子：调用 router，成功则丢弃该消息
└── install.sh              # 一键安装（复制两棵目录 + 建日志目录 + 启用插件）
```

`skill/` 与 `plugin/` 的目录内容就是安装后的原样内容，手动安装时按上表映射复制即可。

## 安装

```bash
git clone <repo-url> kingdou && cd kingdou
./install.sh                 # DRY_RUN=1 ./install.sh 只打印将要做什么
```

`install.sh` 做的事情：

1. `skill/` → `~/.hermes/skills/kingdou/`（**已存在的 `configs/piecework-groups.json` 会先备份再保留**，
   不会覆盖你已登记的群）
2. `plugin/` → `~/.hermes/plugins/kingdou/`
3. 建日志目录 `~/.hermes/logs/kingdou/`
4. `hermes plugins enable kingdou`
5. 提示重启网关（必须在 Hermes 网关进程之外的 shell 里执行）：

```bash
systemctl --user restart hermes-gateway
```

### 前置条件

- Hermes Agent，网关已接飞书：`FEISHU_APP_ID` / `FEISHU_APP_SECRET` 写在 `~/.hermes/.env`
- 运行脚本的解释器带 `requests`（Hermes 运行时环境的 venv 自带；会话里 `python3` 就是它）
- Linux（重启网关用 `systemctl --user`）

## 配置（不做这一步系统是空载的）

仓库里的配置是**空模板** `groups: {}`。群/员工登记之前：任何消息都返回 `group_not_configured`，
**不写库、不发消息、不拦截 AI** —— 这是刻意的安全默认值。

登记一个群 / 一名员工：

```bash
cd ~/.hermes/skills/kingdou
python3 scripts/register_group.py \
  --chat-id oc_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx \
  --name "某个计件群" \
  --employee-openid ou_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx \
  --employee-name "某人" \
  --table-url "https://<tenant>.feishu.cn/wiki/<app_token>?table=<table_id>" \
  --admin-openid ou_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx   # 可选：独立审核员
```

脚本会自动解析 URL 取 `app_token` / `table_id`、拉表格字段、生成 `fields_detail` 并写入中央配置。
细节与坑见 `skill/references/onboarding-new-group.md` 和 `configuration-guide.md`。

> open_id 是**应用级**的：换一个飞书应用，同一个人的 open_id 就变了，旧 ID 抄回来只会得到
> `99992361`（跨应用）之类废 ID。所以本仓库不保存任何真实 ID。

## 运行开关

| `ENABLE_KINGDOU_GATEWAY_MODE` | 行为 |
|---|---|
| `execute`（默认） | 脚本成功后拦截 AI（钩子返回 `{"action": "skip"}`） |
| `shadow` | 只观察分类，不写飞书、不发消息、不拦截 AI |
| `off` | 关闭前置路由，全部交回 AI |

手工跑一次路由（安全预览）：

```bash
KINDOU_PY=${KINDOU_PY:-python3}
S="$HOME/.hermes/skills/kingdou/scripts"
PYTHONPATH=$S $KINDOU_PY -m router.router <chat_id> <sender_openid> '0.12 103' --execute --dry-run --no-send
```

`--no-send` 只抑制飞书消息，**不等于 dry-run**：要完全模拟必须同时带 `--dry-run`。

## 验证

```bash
S="$HOME/.hermes/skills/kingdou/scripts"; KINDOU_PY=${KINDOU_PY:-python3}
PYTHONPATH=$S $KINDOU_PY $S/tests/test_cancel_piecework.py    # 31 项取消回归
PYTHONPATH=$S $KINDOU_PY $S/tests/test_gateway_plugin.py      # 9 项插件接线
hermes plugins list | grep -i kingdou
systemctl --user is-active hermes-gateway
```

全量验证清单见 `skill/references/verification-checklist.md`。

## 红线

1. 脚本成功处理后必须拦截 AI，禁止 AI 二次回复。
2. 群里的标准确认消息只能由脚本发送。
3. 严禁跨群读取或泄露其他群的计件数据。
4. 审核人必须来自配置映射（`openid_name_mapping` / 权限列表），禁止从消息正文猜审核人。
5. 不要引入按网关日志轮询的并行提交路径，会造成重复记录。
6. 改脚本后必须清 `__pycache__` 并重启网关。

## 隐私与数据

- 仓库内**没有**真实的人员姓名、open_id、群 ID、多维表格 token、租户域名；文档示例统一是占位符
  （`员工<01>`、`oc_<redacted-01>`、`app_<redacted-02>` …），照抄进配置不会生效。
- 飞书凭据只从环境变量 / `~/.hermes/.env` 读取，不写日志。
- 运行日志落在 `~/.hermes/logs/kingdou/`（`shadow-router.log`、`shadow-router-errors.log`）。

## 许可

MIT，见 `LICENSE`。
