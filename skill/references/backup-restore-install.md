# Kingdou 备份恢复 / 全新安装

用于：拿到一份 kingdou 备份 tar 包（或旧机器的目录拷贝），要在本机装出一套可用的 kingdou。

**默认规则（与 SKILL.md「本次安装」一致）：员工与管理员的具体 open_id 一律不恢复。** open_id 是
应用级作用域，换一个飞书应用就全部失效，抄回来只会得到 `99992361`（跨应用）之类的废 ID。

## 备份包里有什么 / 什么不要装

- `kingdou_skill/` — SKILL.md、references/、configs/、scripts/。这是要装的部分。
- `piecework/groups/<oc_*>/config.json` — 部分群的独立配置（基础群信息 + 员工身份）。
- `openid_name_mapping.json` — 散落的旧映射，**不要安装**。
- `gateway/feishu.py` — 旧版 Hermes 的整体适配器文件。**不要安装**：平台适配器现在已经是插件，
  这个文件属于另一个版本。同类网关集成改走插件钩子。
- `configs/*.bak*` — 旧配置快照，含真实 open_id，**不要安装**。

## 步骤

1. 解压到**持久目录**（不要只留在 scratch，闲置 24h 会被清）。
2. 复制 `kingdou_skill/` → `~/.hermes/skills/kingdou/`：SKILL.md、references/、configs/、
   scripts/（跳过 `__pycache__` 和 `*.bak*`）。
3. 生成中央配置 `configs/piecework-groups.json`：**只保留顶层 schema，业务内容一律不恢复**。
   - 顶层只留 `version` / `updated_at` / `global_admins` / `openid_name_mapping` / `groups`。
   - `global_admins: []`、`openid_name_mapping: {}`、`groups: {}` —— 群、群名、chat_id、app_token、
     table_id、fields_detail 全部不恢复（群条目格式见 `configuration-guide.md`）。
   - `version` 递增、`updated_at` 改成当天。
4. 独立群配置：真实群目录（`piecework/groups/<oc_*>/`）不恢复；只放一份空格式模板
   `piecework/groups/_template/config.json`（`group_name` / `employee_openid` / `employee_name` /
   `piecework_table` 空串、`allowed_submitters: []`）。
5. 建 `~/.hermes/logs/kingdou/`。
6. 清理文档里的业务标识符与人员信息：示例里到处是真实的 open_id / 群 ID / 表 token / 字段 ID / 姓名，
   逐类扫并替换成稳定占位符 —— **同一真实值 → 同一占位符**，保留文档里「这个 vs 那个」的区分度。
   要扫的类别：
   `ou_[0-9a-f]{32}`（员工/管理员，顺带 `on_` / `u_` 形式的 union_id / user_id）、`oc_[0-9a-f]{32}`（群）、
   27 位字母数字的 app_token/wiki token、`tbl...`（table_id）、`vew...`（view_id）、`fld...`（field_id）、
   `cli_...`（app_id）、租户子域（`<tenant>.feishu.cn`）、**所有人名（含「X计件群」里的 X）**。
   占位符用 `oc_<redacted-NN>` / `员工<NN>` / `管理员<NN>` 这种形式，并在 SKILL.md 顶部注明
   「文档里的标识符与姓名都是占位符」。scripts/ 里的示例（docstring、测试夹具）也要一起扫干净。
   人名要**长串优先**替换：带别名的全称先于简称（如「全名（别名）」先于「别名」），单字姓先处理两字名
   再处理单字，否则会把长名字切成半个。

   这一步不要手搓，用自带的脚本（幂等，可反复跑，退出码 1 = 还有残留）：

   ```bash
   # 1) 先看映射，不写盘
   python3 scripts/scrub_restore_identifiers.py --dry \
     --names-file <备份目录>/openid_name_mapping.json \
     ~/.hermes/skills/kingdou ~/.hermes/plugins/kingdou

   # 2) 确认后正式执行
   python3 scripts/scrub_restore_identifiers.py \
     --names-file <备份目录>/openid_name_mapping.json \
     ~/.hermes/skills/kingdou ~/.hermes/plugins/kingdou
   ```

   脚本自带的类别表见文件头 docstring（ou_/on_/u_、oc_、/wiki//base/ 后的 app_token、
   tbl/vew/fld/cli、租户子域、姓名），app_token 按上下文锚定所以不会误伤长度相近的普通串；
   姓名按长度降序替换，上面「单字姓被切成半个」的坑它已经处理。姓名清单可以直接丢备份里的
   `openid_name_mapping.json`（键是 id、值是姓名，脚本会取值当姓名）。
7. 同步修正文档里的过期路径：已不存在的解释器路径换成本机实际 venv；`gateway/platforms/feishu.py`
   一类的集成检查项换成插件检查项；重启命令按本机单元类型（system 还是 `--user`）写。
8. 安装网关插件，`hermes plugins enable kingdou`（详见 SKILL.md「运行时架构」）。
9. 验证（见下节）。
10. 身份登记 —— 唯一需要用户提供信息的步骤：按 `references/onboarding-new-group.md` 走
    `scripts/register_group.py`。

## 验证

- `python3 -m json.tool configs/piecework-groups.json`（尾部逗号是历史高频错误）。
- `py_compile` 插件 + `scripts/router/*.py` + `scripts/*.py` + `scripts/tests/*.py`。
- `tests/test_cancel_piecework.py`（31 项回归）与 `tests/test_gateway_plugin.py`（9 项接线）。
- 用一个任意 chat_id + 任意假 open_id 跑 `--execute --dry-run --no-send`，期望
  `group_not_configured`（群还没登记）；登记群但未登记员工时期望 `sender_not_in_employee_list`
  —— 这类结果本身就证明「没写库、没发消息、没拦截 AI」，是全新安装应有的空载状态。
- 残留扫描：跑 `scripts/scrub_restore_identifiers.py`（不带 `--dry`）退出码必须为 0；
  `grep -rno 'ou_[0-9a-f]\{32\}' <安装目标目录>` 必须为空（grep 只覆盖身份类，脚本覆盖全部类别）。

## 备份包约定（生成新备份时照此办）

一条命令搞定（含预检 + 打包 + 验证）：

```bash
cd ~/.hermes/skills/kingdou
python3 scripts/make_clean_backup.py    # 输出目录取 $KINDOU_BACKUP_DIR（未设则家目录）
```

- 位置与命名：`<输出目录>/kingdou_backup_<YYYYmmdd_HHMMSS>.tar.gz`，时间戳用 **+08:00**
  （`--stamp-tz` 可改）。本仓库维护者的惯例：`KINDOU_BACKUP_DIR=/home/lmccc`、`--owner lmccc:lmccc`。
  属主 `lmccc:lmccc`、权限 `664`。
- 包内结构：

  ```
  kingdou_backup_<stamp>/
    MANIFEST.md                     包说明 + 恢复步骤 + 「无真实数据」声明
    SHA256SUMS                      逐文件校验和
    kingdou_skill/                  → ~/.hermes/skills/kingdou/
    kingdou_plugin/                 → ~/.hermes/plugins/kingdou/
    piecework/groups/               → ~/.hermes/piecework/groups/（只有 _template）
  ```

- **打包前必须预检**：源目录里不得出现 `oc_/ou_` 32 位 ID、27 位 app_token、`tbl/vew/fld...`、
  `cli_...`、租户子域、真实姓名（占位符 `cli_xxxx…` / `<redacted-NN>` / `员工<NN>` 除外），
  命中就拒绝打包。
- **打包后必须验证**：解开到临时目录 → SHA256SUMS 自洽 → 与当前安装逐文件比对 →
  JSON/`py_compile` → 从包里跑一次路由 dry-run（期望 `group_not_configured`）→ 两个回归测试 →
  复扫无真实数据 → 确认属主/权限。

## 陷阱

- **`--no-send` 不是 dry-run**：恢复后做任何验证前，先确认命令里同时有 `--dry-run`，否则会静默写入
  生产 Bitable。
- **配置文件只留格式**：不要把备份里的 `app_token` / `table_id` / 群名抄回中央配置。空 `groups: {}`
  时路由器对任何群都返回 `group_not_configured`，这是干净空载状态；一旦抄回旧表，写入就会指向旧生产表。
- **不要为了「先跑通」临时塞入假 open_id 或旧 open_id**：假 ID 匹配不到员工，旧 ID 在换应用后是废的，
  两者都会让「到底有没有生效」变得无法判断。
- **不要恢复 `piecework-cron-guard` 之类的并行提交路径**，会造成重复记录（SKILL.md 红线 #5）。
- 改完脚本必须清 `__pycache__`，否则跑的是旧代码。

---

### 安装/恢复：配置只留格式，业务内容与身份一律不恢复（完整步骤见 `references/backup-restore-install.md`）

**默认按最彻底的理解执行。** 用户说「全新安装 / 不保留具体 id / 不保留某人某物」时，点到的那项是下限
而不是上限：一次把业务内容（群、群名、chat_id、app_token、table_id、fields_detail）与人员信息
（open_id、姓名）全部清光，只留 schema。先留着「看起来有用」的群结构或表 token、等用户分几轮来纠正，
是本类任务最常见的返工。

- 从备份 tar 或旧机目录安装/恢复时，**人员信息一律不恢复**：
  - 员工/管理员的具体 open_id → `global_admins: []`、`openid_name_mapping: {}`
    （open_id 是**应用级**作用域，换一个飞书应用就全部失效，抄回来只会得到 `99992361` 之类废 ID）。
  - 员工/管理员姓名、含人名的群名 → 配置文件里本来就不留；文档里的姓名统一抹成 `员工<NN>` / `管理员<NN>` 占位符。
- **配置文件只保留格式，业务内容一律不恢复**：
  - 中央配置 `configs/piecework-groups.json` → `groups: {}`，只留顶层 schema
    `version / updated_at / global_admins / openid_name_mapping / groups`（群、群名、chat_id、app_token、
    table_id、fields_detail 全部不恢复）。
  - 独立群配置 `~/.hermes/piecework/groups/` → 真实群目录不恢复，只留空格式模板 `_template/config.json`。
  - 群条目格式见 `references/configuration-guide.md` 的「Example Minimal Group Configuration」。
  - 文档与脚本里的标识符、姓名一律抹成占位符，用 `scripts/scrub_restore_identifiers.py`
    （幂等；`--dry` 先看映射，正式跑的退出码 1 表示还有残留）。
- 备份里的 `openid_name_mapping.json`、`configs/*.bak*`、旧版 `gateway/feishu.py` 一律不安装。
- 文档（SKILL.md 与 references/*.md）里散布的示例 `ou_...` 也要一并抹掉，否则会被后来者当真实 ID 抄回去。
- 新员工/管理员入职时按 `references/onboarding-new-group.md` 用 `scripts/register_group.py` 重新登记。
- 因此当前是彻底的空载状态：任何群 `group_not_configured`、任何发送者 `sender_not_in_employee_list`，
  即 **不会写库、不会发消息、不会拦截 AI**。
- 上线顺序：登记群与员工 → dry-run 验证 → 再把 `ENABLE_KINGDOU_GATEWAY_MODE` 切到 `execute`
  （登记期间建议先设 `shadow`）。
