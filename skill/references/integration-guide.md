# Kingdou Integration Guide

## Core Principles

**Configuration Over Assumption**: Always confirm group chat ID and corresponding configuration before operations.

**Complete Data Isolation**: Cross-group data access prohibited; each group's data is completely independent.

**Information Isolation Red Lines**:
- ❌ Prohibit cross-group data queries (e.g., Zhou Xiaomai asking about Zhang Yun's piecework)
- ❌ Prohibit cross-group information leaks (e.g., replying with another group's data in one group)
- ✅ Correct response: "抱歉，我无法查询其他计件群的数据，每个群的信息是独立保密的"
- ✅ Each group operates only on its corresponding Bitable table

## Message Trigger Rules

### Piecework Data Submission

| Trigger | Example |
|---------|---------|
| `单价 数量` (pure two numbers) | `0.18 100` |

**Matching Logic**: Message contains only two numbers (unit price + quantity format), no other text, triggers piecework submission flow. **Direct execution, no confirmation询问, no extra dialogue.**

**Submission Reply Rules (Red Line)**:
- ✅ Confirmation message **only sent via `feishu-send-message.py`** to group chat, this is the only reply channel
- ❌ **Prohibit any additional dialogue text after `feishu-send-message.py` sends**: including summaries, explanations, confirmation statements - Feishu API sent message is complete reply, extra text becomes second message in group, triggering user dissatisfaction

### Salary Queries

| Trigger Words | Example Messages | Description |
|---------------|------------------|-------------|
| `查工资` | `查工资` / `查工资 今天` | Query salary overview |
| `工资查询` | `工资查询` | Same as "查工资" |
| `今天工资` | `今天工资` | Query today's salary (3 times/day limit) |
| `本月工资` / `这个月工资` | `本月工资` | Query monthly salary (1 time/day, 3 times/week limit) |
| `历史工资` / `以前工资` | `历史工资 2026年3月` | Query historical salary (1 time/day, 3 times/week limit) |

**Matching Logic**: Message matches any query trigger word enters salary query flow.

### Review Operations

| Trigger Words | Example Messages | Description |
|---------------|------------------|-------------|
| `通过` / `同意` / `审核通过` / `approve` | `同意223` or `审核通过 RF001` | Approve specified record code (flexible format) |
| `拒绝` / `不同意` / `审核拒绝` / `reject` | `拒绝224` or `审核拒绝 RF002` | Reject specified record code (flexible format) |
| `待审核` / `查看待审核` | `待审核记录` | View all pending review records |

### Flexible Trigger Word Policy
- ✅ **Support no-space format**: `同意223`, `通过224`, `拒绝225`
- ✅ **Support space format**: `同意 223`, `通过 224`, `拒绝 225`
- ✅ **Support English triggers**: `approve226`, `reject 227`
- ✅ **Flexible separators**: Space is optional, improves user experience

### Batch Review Features (Advanced Version):
- ✅ **Approve All**: `同意全部` / `通过全部` - batch approve all pending records
- ✅ **Code List Batch**: Support `通过228 229 230` or `同意 RF001 RF002 RF003` multi-code format
- ❌ **Code Range Batch**: Current script **does not support** `拒绝 RF001-RF100` range format
- ✅ **Correct Approach**: Can directly send multiple codes like `通过225 226 227`, system automatically processes each

> **Important Reminder**: Now supports direct input like `通过225 226 227`, system automatically parses and batch processes all codes.

**Matching Logic**: Message matches any review trigger word and sender is admin/reviewer, enters review flow.

### Trigger Priority

1. **Review Related** (highest priority) - matches review triggers and identity is reviewer
2. **Salary Query** - matches query triggers
3. **Piecework Submission** (default) - matches submission triggers or pure numeric format

> **Note**: Messages not matching any trigger are ignored by Kingdou processing.

## Production Architecture: Script-First, AI-Fallback

Regular Kingdou messages no longer processed by AI main flow. Feishu gateway calls script router first:

- **Entry**: `~/.hermes/skills/kingdou/scripts/router/router.py`
- **Gateway Log Mark**: `[KingdouScript]`
- **Detailed JSON Log**: `~/.hermes/logs/kingdou/shadow-router.log`
- **Mode Switch**: `ENABLE_KINGDOU_GATEWAY_MODE`
  - `execute`: Production mode, script executes successfully then intercepts AI, prevents second reply/repeat processing
  - `shadow`: Observe only, no writes, no messages, no AI interception
  - `off`: Disable Kingdou pre-script

Script Distribution Rules:

```
router.py
  ├── submit          → submit_piecework.py        # Piecework submission
  ├── review          → review_piecework.py        # Review approval/rejection
  ├── pending_review  → query_pending_reviews.py   # Pending reviews query
  └── query           → query_salary.py            # Salary queries
```

Production Principles:
- ✅ Script success must directly `return`, skip AI pipeline
- ✅ Replies sent via script calling `feishu-send-message.py`
- ✅ AI only handles script-unrecognized, permission failures, or script exceptions
- ❌ Prohibit AI and script simultaneous processing of same piecework message
- ❌ Prohibit restoring `piecework-cron-guard` parallel submission paths scanning gateway.log

## Workflow Integration Points

### Session Context Requirements

Kingdou requires proper session context injection to function correctly:
- Current chat_id must be available in AI system prompt
- User isolation must be maintained through proper session keys  
- Gateway routing must correctly identify group vs. private contexts

### Error Handling Integration

- Script failures must fall back to AI processing
- AI must recognize when scripts have already processed messages
- Double-response prevention through gateway interception

## Critical Requirements

- ✅ Must use standard reply template format (strictly follow references/standard-reply-template.md)
- ✅ Must send via `feishu-send-message.py` (supports real @mention)
- ✅ Script success must intercept AI, prevent duplicate replies
- ❌ Prohibit any additional dialogue text after API sends

`待审核` / `查看待审核` / `待审核记录` query functionality still under development, currently handled by AI fallback.

## Performance Optimizations

- For known safe groups (e.g., Wang Xiaodou piecework group), can skip cron job conflict checks to improve response speed
- Still maintain dual verification steps to ensure data accuracy
- Formula field data parsing handles structured data format `{'type': 2, 'value': [value]}` vs simple numeric values

## Historical Lessons

- [LRN-20260511-002] **feishu-send-message.py sending prohibits extra dialogue output** - Users already receive API confirmation in Feishu group, agent outputting dialogue text becomes second message, triggering user dissatisfaction ("why this extra message?"). Rule: submission confirmation only via `feishu-send-message.py`, agent reply empty or minimal ("processed").
- [LRN-20260330-001] Not reading config to determine feature status → config priority
- [LRN-20260401-001] Group chat confusion → confirm group ID before operations
- [LRN-20260401-002] Cross-group data leakage → strictly enforce information isolation, prohibit cross-group data queries