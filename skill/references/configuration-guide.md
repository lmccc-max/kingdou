# Kingdou 配置管理完整指南

## 配置文件结构


The decoupled Kingdou system uses a central configuration file at:
`~/.hermes/skills/kingdou/configs/piecework-groups.json`

## Required Top-Level Fields
- `version`: Semantic version string (e.g., "1.1")
- `updated_at`: ISO date string (e.g., "2026-06-02")  
- `global_admins`: Array of OpenIDs with global administrator privileges
- `openid_name_mapping`: Dictionary mapping all OpenIDs to human-readable names
- `groups`: Object containing all group configurations keyed by chat_id

## Required Group Configuration Fields
Each group entry MUST include:
- `name`: Human-readable group name
- `app_token`: Feishu Bitable app token for API access
- `table_id`: Feishu Bitable table ID for data storage
- `employee_list`: Array of allowed employee OpenIDs (only these users can submit)
- `independent_admins`: Array of group-specific administrator OpenIDs (optional)
- `fields_detail`: Complete field mapping object with:
  - Field name as key (e.g., "编码", "姓名", "单价", "数量", "金额")
  - Each field contains: `field_id`, `type`, and optionally `formatter` or `is_primary`

## Validation Requirements
1. **All OpenIDs must be mapped**: Every OpenID in `global_admins`, `independent_admins`, and `employee_list` must have an entry in `openid_name_mapping`
2. **No redundant fields**: Avoid duplicate field definitions (e.g., both `fields` and `fields_detail`)
3. **Version tracking**: Always increment version and update timestamp when making changes
4. **JSON validity**: Configuration must be valid JSON with proper encoding

## Common Issues and Fixes
- **Missing OpenID mapping**: Add the missing OpenID to `openid_name_mapping` with appropriate name
- **Redundant field definitions**: Remove duplicate field structures, keep only `fields_detail`
- **Outdated version info**: Update `version` and `updated_at` fields after any modification
- **Incomplete group config**: Ensure all required fields are present for each group

## Example Minimal Group Configuration
```json
{
  "oc_example_chat_id": {
    "name": "Example Group",
    "app_token": "APP_TOKEN_HERE", 
    "table_id": "TABLE_ID_HERE",
    "employee_list": ["ou_employee_openid_here"],
    "independent_admins": [],
    "fields_detail": {
      "编码": {"field_id": "fld_primary_key", "type": "AutoNumber", "is_primary": true},
      "姓名": {"field_id": "fld_name", "type": "Text"},
      "单价": {"field_id": "fld_price", "type": "Number", "formatter": "0.000"},
      "数量": {"field_id": "fld_quantity", "type": "Number", "formatter": "0"},
      "金额": {"field_id": "fld_amount", "type": "Formula", "formatter": "0.00", "auto_calculated": true},
      "审核状态": {"field_id": "fld_status", "type": "Text"},
      "审核人": {"field_id": "fld_reviewer", "type": "Text"}
    }
  }
}
```

## 新群配置模板

# 计件群配置模板 (JSON格式)

```json
{
  "groups": {
    "chat_id_123456789": {
      "name": "生产一部计件群",
      "app_token": "app_xxx",
      "table_id": "tbl_xxx",
      "admin_ids": ["ou_admin1", "ou_admin2"],
      "employee_list": ["ou_emp1", "ou_emp2", "ou_emp3"],
      "fields": {
        "record_id": "autonum_field_id",
        "employee_name": "text_field_id",
        "date_time": "date_field_id",
        "unit_price": "number_field_id",
        "quantity": "number_field_id",
        "amount": "formula_field_id",
        "status": "text_field_id",
        "reviewer": "text_field_id",
        "remark": "text_field_id"
      }
    }
  }
}
```

## 字段说明

- `chat_id`: 飞书群聊ID（从 conversation_label 获取）
- `app_token`: 飞书多维表格应用token
- `table_id`: 表格ID
- `admin_ids`: 审核员用户ID列表
- `employee_list`: 允许提交计件的员工ID列表
- `fields`: 表格字段映射，必须与实际表格字段ID匹配

## 重要原则

- 配置文件是唯一真相源，每次操作前必须重新加载
- 不同群组的数据完全隔离，禁止跨群操作
- 字段ID必须从实际表格中获取，不可凭印象填写

## 新群配置设置详细指南



### 1. 信息收集
从用户消息中提取以下关键信息：
- **群ID**: 通常需要手动指定或从会话上下文中获取（格式：oc_xxxxxxxxxxxxxxxxxxxxxx）
- **员工OpenID**: 从@mention或用户提供的信息中获取（格式：ou_xxxxxxxxxxxxxxxxxxxxxx）
- **员工姓名**: 用户明确提供的姓名
- **飞书表格URL**: 完整的Wiki链接，包含table参数

### 2. URL解析
从飞书表格URL `https://tenant_<redacted-01>.feishu.cn/wiki/{app_token}?table={table_id}&view={view_id}` 中提取：
- **app_token**: URL路径中的部分（如：app_<redacted-03>）
- **table_id**: table参数的值（如：tbl_<redacted-02>）

### 3. 中央配置文件更新
编辑 `~/.hermes/skills/kingdou/configs/piecework-groups.json`：

#### 3.1 更新openid_name_mapping
在 `openid_name_mapping` 对象中添加新条目：
```json
"ou_<redacted-08>": "员工<06>"
```

#### 3.2 添加群组配置
在 `groups` 对象中添加新群组配置，使用标准字段结构：
```json
"oc_<redacted-03>": {
  "name": "员工<06>计件群",
  "app_token": "app_<redacted-03>",
  "table_id": "tbl_<redacted-02>",
  "independent_admins": [],
  "employee_list": [
    "ou_<redacted-08>"
  ],
  "fields_detail": {
    "编码": {
      "field_id": "fld_<redacted-01>",
      "type": "AutoNumber",
      "is_primary": true
    },
    "姓名": {
      "field_id": "fld_<redacted-02>",
      "type": "Text"
    },
    "日期/时间": {
      "field_id": "fld_<redacted-03>",
      "type": "CreatedTime",
      "formatter": "yyyy/MM/dd HH:mm"
    },
    "单价": {
      "field_id": "fld_<redacted-04>",
      "type": "Number",
      "formatter": "0.000"
    },
    "数量": {
      "field_id": "fld_<redacted-05>",
      "type": "Number",
      "formatter": "0"
    },
    "金额": {
      "field_id": "fld_<redacted-06>",
      "type": "Formula",
      "formatter": "0.00",
      "auto_calculated": true
    },
    "审核状态": {
      "field_id": "fld_<redacted-07>",
      "type": "Text"
    },
    "审核人": {
      "field_id": "fld_<redacted-08>",
      "type": "Text"
    },
    "备注": {
      "field_id": "fld_<redacted-09>",
      "type": "Text"
    }
  }
}
```

### 4. 版本管理
- **版本号**: 递增主配置文件的version字段（如从1.1到1.2）
- **更新时间**: 设置updated_at为当前日期（格式：YYYY-MM-DD）

### 5. 验证步骤
1. 确认中央配置文件语法正确（有效的JSON）
2. 验证openid_name_mapping包含正确的映射
3. 确认群组配置中的employee_list与openid_name_mapping一致
4. 检查app_token和table_id是否正确提取
5. 删除任何冗余的单独群配置目录（所有配置应集中在中央文件中）

## 常见错误和解决方案

### 错误1: openid_name_mapping缺失
**症状**: 系统提示"员工OpenID没有对应的姓名映射"
**解决方案**: 确保在中央配置文件的openid_name_mapping部分添加了正确的映射

### 错误2: 群组配置字段不完整
**症状**: 计件提交失败，字段验证错误
**解决方案**: 使用标准的fields_detail结构，确保包含所有必需字段

### 错误3: app_token或table_id解析错误
**症状**: API调用返回表格不存在错误
**解决方案**: 仔细检查URL解析，确保app_token来自URL路径，table_id来自query参数

### 错误4: 版本号未更新
**症状**: 配置缓存问题，新配置未生效
**解决方案**: 始终递增版本号以确保配置重新加载

## 最佳实践

1. **集中配置**: 所有群组配置必须维护在中央配置文件中，避免分散配置
2. **一致性检查**: openid_name_mapping中的OpenID必须与群组配置中的employee_list完全一致
3. **标准字段**: 使用统一的fields_detail结构，便于维护和调试
4. **版本控制**: 每次配置变更都应递增版本号，便于追踪和回滚
5. **清理冗余**: 避免创建单独的群配置目录，所有配置应集中在中央文件中

## 自动化脚本建议

考虑开发自动化脚本来处理新群配置：
- 自动从URL提取app_token和table_id
- 自动生成标准群组配置JSON
- 自动更新版本号
- 自动验证配置语法和一致性

## 配置注意事项



### 问题
配置文件中使用的是飞书字段ID（如 `fld_<redacted-01>`），但飞书Bitable API在**创建记录时**需要使用**字段名称**（如 `编码`）。

### 错误示例
```json
"fields": {
  "编码": "fld_<redacted-01>",  // ❌ 这是字段ID，创建记录时会报错 FieldNameNotFound
  "姓名": "fld_<redacted-02>"
}
```

### 正确做法
```json
"fields": {
  "编码": "编码",  // ✅ 使用字段名称
  "姓名": "姓名"
}
```

### 需要更新的群配置

1. **员工<01>计件群** (`oc_<redacted-02>`)
2. **员工<02>计件群** (`oc_<redacted-01>`)

### 更新命令

手动编辑 `~/.hermes/skills/productivity/kingdou/configs/piecework-groups.json`：

将字段映射从字段ID改为字段名称：
- `"编码": "fld_<redacted-01>"` → `"编码": "编码"`
- `"姓名": "fld_<redacted-02>"` → `"姓名": "姓名"`
- `"日期/时间": "fld_<redacted-03>"` → `"日期/时间": "日期/时间"`
- `"单价": "fld_<redacted-04>"` → `"单价": "单价"`
- `"数量": "fld_<redacted-05>"` → `"数量": "数量"`
- `"金额": "fld_<redacted-06>"` → `"金额": "金额"`
- `"审核状态": "fld_<redacted-07>"` → `"审核状态": "审核状态"`
- `"审核人": "fld_<redacted-08>"` → `"审核人": "审核人"`
- `"备注": "fld_<redacted-09>"` → `"备注": "备注"`
- `"已累加金额": "fld_<redacted-10>"` → `"已累加金额": "已累加金额"`

### 备注

- 字段ID仅在**获取字段信息**的API中使用
- **创建/更新记录**时始终使用字段名称
- **查询记录**返回的数据也用字段名称作为key


---

### Wiki/Base Token 作为 App Token
飞书 wiki 和 base URL 中的 token 都可以直接用作 Bitable API 的 app_token：
```
Wiki: https://tenant_<redacted-01>.feishu.cn/wiki/app_<redacted-01>?table=tbl_<redacted-01>
      └── token (可直接用作 app_token)                    └── table_id

Base: https://tenant_<redacted-01>.feishu.cn/base/app_<redacted-02>
      └── token (可直接用作 app_token)
```
**不需要**通过 wiki API 转换，直接用 token 调用 Bitable API 即可。Base URL 可能不含 `table=` 参数，需先调用 tables 列表接口获取 table_id。

---

### 独立群配置文件
部分群配置在中央配置 `configs/piecework-groups.json` 中找不到，而是在独立文件中：
```
~/.hermes/piecework/groups/<chat_id>/config.json
```
示例内容：
```json
{
  "group_name": "员工<05>计件群",
  "employee_openid": "ou_<redacted-01>",
  "employee_name": "员工<05>",
  "piecework_table": "https://tenant_<redacted-01>.feishu.cn/wiki/app_<redacted-01>?table=tbl_<redacted-01>&view=vew_<redacted-01>",
  "allowed_submitters": ["ou_<redacted-01>"]
}
```
需要解析 `piecework_table` URL 获取 wiki_token（作为 app_token）和 table_id。

全新安装/恢复后这里只有 `_template/config.json`（空格式模板）—— 真实群目录按需创建，不要从备份抄回来（见「安装/恢复」章节）。

---

### JSON 格式错误
`configs/piecework-groups.json` 中的最后一个元素后**不能有逗号**（trailing comma）。常见错误：
```json
// ❌ 错误
"ou_<redacted-02>": "员工<11>",  // 逗号后是 }

// ✅ 正确
"ou_<redacted-02>": "员工<11>"   // 无逗号
```
修复后验证：`python3 -m json.tool ~/.hermes/skills/kingdou/configs/piecework-groups.json`

---

### 中央配置有 300 秒进程内缓存
`config_loader.py` 把 `configs/piecework-groups.json` 读进进程内缓存（TTL 300 秒），所以：
- 改完配置后，**已在运行的网关/插件进程可能继续用旧配置**，文件改动不会立刻生效；
- 验证配置要走独立进程的 CLI（`python3 -m router.router ...`），它读的是磁盘上的新配置；
- 要立即生效就重启网关（在网关进程之外的 shell 里执行）。
排查“配置看着对但路由结果不对”时先想这一条，别急着改代码。
