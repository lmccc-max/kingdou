# 金豆计件工资管理 - 标准回复模板

## 数据提交确认回复

```
✅ 计件数据已成功提交！

📋 提交详情：
- 📊编码：{record_id}
- 姓名：{employee_name}
- 单价：{unit_price} 元
- 数量：{quantity} 件
- 金额：{amount}
- 提交时间：{submit_time}

📝 当前状态：待审核 <at user_id="{reviewer_open_id}">{reviewer_name}</at>
🔔 审核员将在工作时间内处理您的申请。

如有疑问，请联系管理员。
```

**@mention 格式说明（重要）**：
- ✅ **使用飞书原生@mention格式**：`<at user_id="{reviewer_open_id}">{reviewer_name}</at>`
- ✅ 这样发送后，飞书会真正@到审核员，显示为可点击的蓝色链接，并发送通知
- ❌ **禁止使用普通文本 `@姓名`**：这样只是纯文本，不会真正@到人

**{reviewer_name} 和 {reviewer_open_id} 获取规则（重要）**：
- 从配置文件 `~/.hermes/skills/kingdou/configs/piecework-groups.json` 获取
- 优先使用群的 `independent_admins`（独立管理员列表）
- 如 `independent_admins` 为空，使用 `global_admins`（全局管理员列表）
- 从 `openid_name_mapping` 中查找 OpenID 对应的姓名
- 示例：员工<03>计件群的 independent_admins 为空，使用 global_admins → 管理员<01>(ou_<redacted-05>)、管理员<03>(ou_<redacted-12>)

**发送消息方式（重要）**：
- ✅ **脚本内部发送**：路由器脚本通过 `feishu_client.py` 自动发送消息，无需 AI 手动调用
- ❌ **`feishu-send-message.py` 不存在**：该脚本在当前架构中不存在，不要尝试调用
- 当 AI 手动运行路由脚本时，脚本成功即表示消息已发送，AI 不应再发送飞书消息

**金额字段处理规则**：
- 查询时金额 > 0：显示 `{amount} 元`（飞书公式字段已计算的真实结果）
- 查询时金额 = 0 或未计算：显示 `未计算（飞书公式字段自动计算中）`
- 当显示"未计算"时，添加提示：`⚠️ 提示：金额由系统自动计算，如需查看请1分钟后再次尝试查询。`

## 审核通过回复

单条记录：
```
✅ 计件记录已审核通过！

📋 审核详情：
- 📊编码：{record_id} | 单价：{unit_price} 元 | 数量：{quantity} 件 | 金额：{amount} 元 | 审核时间：{review_time} | 审核人：{reviewer}

💰 该笔金额将计入您的工资结算。
```

多条记录：
```
✅ 计件记录已审核通过！

📋 审核详情：
- 📊编码：{record_id_1} | 单价：{unit_price_1} 元 | 数量：{quantity_1} 件 | 金额：{amount_1} 元 | 审核时间：{review_time} | 审核人：{reviewer}
- 📊编码：{record_id_2} | 单价：{unit_price_2} 元 | 数量：{quantity_2} 件 | 金额：{amount_2} 元 | 审核时间：{review_time} | 审核人：{reviewer}
...

💰 该笔金额将计入您的工资结算。
```

**审核人字段获取规则（重要）**：
- 审核人 = 实际发送"审核通过"消息的用户真实姓名
- **获取流程**：
  1. 从会话上下文中获取消息发送者的 OpenID
  2. 查询中央配置文件 `~/.hermes/skills/kingdou/configs/piecework-groups.json` 中的 `openid_name_mapping`（注意：字段名为 `openid_name_mapping`，不是 `openid_name_map`）
  3. 使用 OpenID 查到对应的姓名填入审核人字段
- ✅ **通过 OpenID 查询中央配置文件**：从消息会话中获取发送者的 OpenID，然后查询 `~/.hermes/skills/kingdou/configs/piecework-groups.json` 中的 `admin_name_mapping`
- 禁止直接复制消息模板中的"审核人"字段值（该值可能不正确）
- 如果 OpenID 在映射表中找不到，应询问用户确认

## 审核拒绝回复

```
❌ 计件记录审核未通过！

📋 拒绝详情：
- 📊编码：{record_id}
- 姓名：{employee_name}
- 拒绝时间：{reject_time}
- 审核人：{reviewer}

📝 拒绝原因：{reject_reason}

请重新提交正确的计件数据。
```

**审核人字段获取规则（重要）**：
- 审核人 = 实际发送"审核拒绝"消息的用户真实姓名
- **获取流程**：
  1. 从会话上下文中获取消息发送者的 OpenID
  2. 查询中央配置文件 `~/.hermes/skills/kingdou/configs/piecework-groups.json` 中的 `openid_name_mapping`（注意：字段名为 `openid_name_mapping`，不是 `openid_name_map`）
  3. 使用 OpenID 查到对应的姓名填入审核人字段
  4. 如 OpenID 不在映射表中 → 审核人字段留空，回复中提示联系管理员添加映射
- 禁止直接复制消息模板中的"审核人"字段值（该值可能不正确）
- 如果 OpenID 在映射表中找不到，审核人字段留空并提示用户联系管理员

## 查询结果回复

```
📊 {employee_name} 的计件统计（{period}）：

{detailed_records}

💰 总计金额：{total_amount} 元
✅ 已通过：{approved_count} 条
⏳ 待审核：{pending_count} 条
❌ 已拒绝：{rejected_count} 条
```

## 跨群查询拒绝回复

```
抱歉，我无法查询其他计件群的数据。每个群的信息是独立保密的，请在对应的计件群中进行查询。
```

## 待审核记录回复

```
⏳ {group_name}待审核记录：

📋 待审核详情：
{pending_details}

💰 待审核总计金额：{total_amount} 元
📝 共 {pending_count} 条记录等待审核 <at user_id="{reviewer_open_id}">{reviewer_name}</at>
```

- `{group_name}`：群名称
- `{pending_details}`：每条记录的详情，每行格式为 `📊编码：{code} | 数量：{qty}件 | 单价：{price}元 | 金额：{amount}元 | 提交时间：{submit_time}`
- `{total_amount}`：所有待审核记录金额之和
- `{pending_count}`：待审核记录总数
- `{reviewer_name}`：该群的审核员姓名（从配置文件获取）
- `{reviewer_open_id}`：该群审核员的 OpenID（用于@mention）

**@mention 格式说明**：
- 使用 `<at user_id="{reviewer_open_id}">{reviewer_name}</at>` 格式
- 优先使用群的 `independent_admins`，如为空则使用 `global_admins`
- 必须通过飞书API发送消息，禁止使用 send_message 工具

## 错误处理回复

```
⚠️ 操作遇到问题：

错误详情：{error_message}

请稍后重试，或联系管理员处理。
```

## 使用说明

- 所有占位符 `{xxx}` 需要替换为实际数据
- 金额必须经过双重验证（手动累加 vs 表格自动求和）
- 编码必须来自飞书 AutoNumber 字段，不可手动指定
- 严格执行信息隔离原则，禁止跨群数据查询

## ⛔ 发送后禁言规则（红线）

**通过 `feishu-send-message.py` 发送确认消息后，agent 自身回复必须为空或仅最简确认（如"已处理"）。**

- ❌ **严禁**在API发送后输出任何总结、复述、说明性对话文本
- ❌ **严禁**重复已通过飞书API发送的内容
- ❌ **严禁**使用 `send_message` 工具发送计件确认
- ⚠️ 额外对话文本会作为第二条消息出现在群里，引起用户不满，且可能被网关重复路由触发二次处理产生重复记录
---

### feishu-send-message.py 不存在
`references/standard-reply-template.md` 引用了 `scripts/feishu-send-message.py`，但该脚本不存在。消息发送由 `scripts/router/feishu_client.py` 在脚本内部完成。**不要尝试调用 `feishu-send-message.py`**。
