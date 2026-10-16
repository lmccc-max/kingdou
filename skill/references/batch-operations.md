# 批量操作指南（提交与审核）

## 批量审核





### 审核编码格式限制


1. **消息解析限制**：`message_parser.py` 的 `REVIEW_PATTERN` 正则表达式只匹配单个编码格式：`^\\s*(审核通过|通过审核|审核拒绝|拒绝审核)\\s+([A-Za-z0-9_-]+)\\s*$`
2. **API字段类型不匹配**：飞表格中"编码"字段为 AutoNumber（数字类型），但搜索时传递了带"RF"前缀的字符串会导致 `InvalidFilter` 错误
3. **批量处理未实现**：当前 `review_piecework.py` 脚本只设计处理单个编码，没有批量处理逻辑

## 解决方案
### 临时解决方案（当前使用）
- 将范围格式手动拆分为单独的审核命令
- 使用纯数字编码（225、226、227）而不是带前缀格式（RF225、RF226、RF227）
- 逐条执行：`审核通过 225`、`审核通过 226`、`审核通过 227`

### 长期改进方向
1. **增强消息解析**：支持范围格式解析（如 `225-227` → [225, 226, 227]）
2. **自动编码清理**：从输入中自动提取纯数字部分（RF225 → 225）
3. **实现批量审核循环**：在 `review_piecework` 函数中添加批量处理逻辑

## 验证命令
```bash
# 检查单个记录是否存在
cd ~/.hermes/skills/kingdou/scripts && python3 -c "
from router.feishu_client import FeishuClient
from router.config_loader import ConfigLoader
group = ConfigLoader().get_group('oc_<redacted-02>')
client = FeishuClient()
result = client.search_by_code(group, 225)
print(result)
"

# 执行单个审核
cd ~/.hermes/skills/kingdou/scripts && python3 -c "
from router.review_piecework import review_piecework
result = review_piecework(
    chat_id='oc_<redacted-02>',
    sender_id='ou_<redacted-06>',
    message_text='审核通过 225'
)
print(result)
"
```

## 批量提交



当用户连续发送多条计件数据时（短时间内发送多条消息），系统应能够：
1. 识别为批量提交请求
2. 一次性处理所有记录
3. 统一回复所有提交结果

## 触发条件

用户行为模式：
- 连续发送多条 `单价 数量` 格式的消息
- 消息间隔时间较短（通常在1分钟内）
- 示例：
  ```
  0.06 108
  0.06 105
  ```

## 处理流程

```
1. 检测批量提交信号
   - 收到第一条计件消息
   - 在5秒内收到第二条计件消息
   - 判定为批量提交

2. 批量创建记录
   - 使用循环依次创建所有记录
   - 记录每个创建的 record_id
   - 更新每个记录的审核状态为"待审核"

3. 批量查询确认
   - 使用 record_id 列表查询所有记录
   - 获取每个记录的完整字段（编码、金额等）

4. 统一回复
   - 使用标准回复模板
   - 列出所有提交记录的详情
   - 显示总计信息
```

## 代码示例

```python
import os
import json
import requests
from datetime import datetime

# 获取 tenant_access_token
def get_token():
    app_id = os.environ.get('FEISHU_APP_ID')
    app_secret = os.environ.get('FEISHU_APP_SECRET')
    url = "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal"
    headers = {"Content-Type": "application/json"}
    data = {"app_id": app_id, "app_secret": app_secret}
    resp = requests.post(url, headers=headers, json=data)
    return resp.json()["tenant_access_token"]

# 批量创建记录
def batch_create_records(app_token, table_id, records_data, employee_name):
    token = get_token()
    create_url = f"https://open.feishu.cn/open-apis/bitable/v1/apps/{app_token}/tables/{table_id}/records"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    
    results = []
    for data in records_data:
        record_data = {
            "fields": {
                "姓名": employee_name,
                "单价": data["单价"],
                "数量": data["数量"]
            }
        }
        
        resp = requests.post(create_url, headers=headers, json=record_data)
        result = resp.json()
        
        if result.get("code") == 0:
            record = result["data"]["record"]
            record_id = record["record_id"]
            
            # 更新审核状态
            update_url = f"{create_url}/{record_id}"
            update_data = {"fields": {"审核状态": "待审核"}}
            requests.put(update_url, headers=headers, json=update_data)
            
            # 查询确认
            query_url = f"{create_url}/{record_id}"
            resp = requests.get(query_url, headers={"Authorization": f"Bearer {token}"})
            query_result = resp.json()
            
            if query_result.get("code") == 0:
                fields = query_result["data"]["record"]["fields"]
                # 解析字段...
                results.append({
                    "code": parse_field(fields.get('编码', '')),
                    "unit_price": fields.get('单价', 0),
                    "quantity": fields.get('数量', 0),
                    "amount": parse_amount(fields.get('金额', 0)),
                    "submit_time": parse_datetime(fields.get('日期/时间', ''))
                })
    
    return results

# 生成批量回复
def generate_batch_reply(results, employee_name):
    reply = f"✅ 计件数据已成功提交！\n\n📋 提交详情：\n\n"
    
    for i, r in enumerate(results, 1):
        reply += f"**记录{i}：**\n"
        reply += f"- 📊编码：{r['code']}\n"
        reply += f"- 姓名：{employee_name}\n"
        reply += f"- 单价：{r['unit_price']:.2f} 元\n"
        reply += f"- 数量：{r['quantity']} 件\n"
        reply += f"- 金额：{r['amount']:.2f} 元\n"
        reply += f"- 提交时间：{r['submit_time']}\n\n"
    
    reply += "📝 当前状态：待审核\n"
    reply += "🔔 审核员将在工作时间内处理您的申请。\n\n"
    reply += "如有疑问，请联系管理员。"
    
    return reply
```

## 回复模板

```
✅ 计件数据已成功提交！

📋 提交详情：

**记录1：**
- 📊编码：{code1}
- 姓名：{employee_name}
- 单价：{unit_price1} 元
- 数量：{quantity1} 件
- 金额：{amount1} 元
- 提交时间：{submit_time1}

**记录2：**
- 📊编码：{code2}
- 姓名：{employee_name}
- 单价：{unit_price2} 元
- 数量：{quantity2} 件
- 金额：{amount2} 元
- 提交时间：{submit_time2}

📝 当前状态：待审核
🔔 审核员将在工作时间内处理您的申请。

如有疑问，请联系管理员。
```

## 注意事项

1. **保持原子性**：要么全部成功，要么明确告知哪些失败
2. **顺序处理**：按用户发送顺序创建记录，确保编码连续
3. **统一时间戳**：批量记录使用相近的提交时间
4. **错误处理**：单条记录失败不影响其他记录的处理

