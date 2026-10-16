# 管理员补录操作指南

## 场景说明
当需要为员工补录计件数据时（例如数据遗漏、系统故障恢复等），管理员可以使用此流程进行补录操作。

## 操作步骤

### 1. 确认管理员身份
- 全局管理员：`ou_<redacted-05>` (管理员<01>)、`ou_<redacted-03>` (管理员<02>)、`ou_<redacted-06>` (管理员<03>)
- 独立管理员：各群配置中的 `independent_admins` 列表

### 2. 获取目标员工信息
- 从群配置中获取正确的员工 OpenID
- 示例：员工<02>计件群的员工 OpenID 是 `ou_<redacted-07>`

### 3. 执行补录命令
```python
from router.submit_piecework import submit_piecework

result = submit_piecework(
    chat_id='群聊ID',
    sender_id='员工OpenID',  # 使用员工的OpenID，不是管理员的
    message_text='单价 数量'
)
```

### 4. 验证结果
- 检查 `result.ok` 是否为 True
- 记录分配的编码用于后续跟踪

## 注意事项
- **必须使用员工的 OpenID**：即使管理员执行补录，也要使用目标员工的 OpenID，否则会因权限验证失败
- **数据格式**：保持标准的 "单价 数量" 格式，如 "0.660 50"
- **群组隔离**：确保在正确的群组中操作，避免跨群数据污染

## 常见错误
- `sender_not_in_employee_list`：使用了错误的 OpenID，应使用群配置中定义的员工 OpenID
- 权限不足：非管理员用户尝试补录操作

## 示例
```python
# 为员工<02>补录数据
result = submit_piecework(
    chat_id='oc_<redacted-01>',
    sender_id='ou_<redacted-07>', 
    message_text='0.660 50'
)
# 成功返回: SubmitResult(ok=True, code='386', ...)
```