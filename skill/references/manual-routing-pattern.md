# 手动路由模式

当 gateway 未拦截消息（`ENABLE_KINGDOU_GATEWAY_MODE` 为 `off` 或 `shadow`）时，AI 需手动处理计件消息。

## 流程

1. 从飞书消息上下文获取 `chat_id` 和发送者 `open_id`
2. 运行路由脚本：
   ```bash
   PYTHONPATH=~/.hermes/skills/kingdou/scripts \
   $KINDOU_PY -m router.router \
     <chat_id> <open_id> '<message>' --execute
   ```
3. 解析 JSON 响应，检查 `ok` 和 `executed` 字段
4. **如果脚本成功（ok=true）**：
   - 脚本已通过 `feishu_client.py` 发送飞书消息（响应中有 `message_id`）
   - AI 仅在会话中输出最简确认，**不发送飞书消息**
   - 格式：`✅ 提交成功 | 编码: {record_code}` 或 `✅ 审核通过 | 编码: {record_code}`
5. **如果脚本失败（ok=false）**：
   - 根据 `reason` 字段给出简短说明
   - 常见原因：`sender_not_in_employee_list`、`invalid_format`、`duplicate`

## 注意事项

- 脚本成功后 AI 不应重复发送飞书消息，避免群内出现两条确认
- `references/kingdou-standard-reply-template.md` 中的模板格式是给脚本内部参考的，不是给 AI 手动调用的
- `feishu-send-message.py` 脚本不存在，不要尝试调用

---

## 手动路由时的消息发送（重要）

当 gateway 未拦截消息（mode=off/shadow）而 AI 手动运行 router 脚本时：
- **脚本自身会通过 `feishu_client.py` 发送飞书消息**，响应中包含 `message_id`
- **AI 不应再发送任何飞书消息**，避免重复回复
- AI 仅在会话中输出最简确认（如 `✅ 提交成功 | 编码: xxx`），不使用 `feishu-send-message.py`（该脚本不存在）
- `references/standard-reply-template.md` 中的 `feishu-send-message.py` 引用是给脚本内部参考的模板格式，不是给 AI 手动调用的

**安全预览命令**（不修改数据、不发消息）：
```bash
PYTHONPATH=~/.hermes/skills/kingdou/scripts \
$KINDOU_PY -m router.router \
  <chat_id> <sender_openid> '<message>' --execute --dry-run --no-send
```

**生产执行命令**（写入 Bitable + 发飞书消息）：
```bash
PYTHONPATH=~/.hermes/skills/kingdou/scripts \
$KINDOU_PY -m router.router \
  <chat_id> <sender_openid> '<message>' --execute
```
