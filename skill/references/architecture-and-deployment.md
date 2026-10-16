# Kingdou 系统架构与部署

## 系统解耦架构



The Kingdou system has been successfully decoupled from hardcoded gateway logic. All business rules are now centralized in:

**File**: `~/.hermes/skills/kingdou/configs/piecework-groups.json`

**Structure**:
```json
{
  "global_admins": ["openid1", "openid2"],
  "independent_admins": ["openid3"],
  "groups": {
    "chat_id_1": {
      "employee_openid": "employee_openid",
      "allowed_submitters": ["openid1", "openid2"],
      "piecework_table": "https://feishu.cn/wiki/table_url",
      "group_name": "Group Name"
    }
  }
}
```

## Router Script Implementation

The router script at `~/.hermes/skills/kingdou/scripts/router/router.py` now handles all business logic:

- Loads central configuration
- Validates user permissions against `global_admins` and `allowed_submitters`
- Determines auditor status based on admin lists
- Processes submissions with proper error handling
- Generates appropriate confirmation messages

## Migration Benefits

1. **Configuration Centralization**: Single source of truth for all group settings
2. **Logic Separation**: Business rules moved from gateway core to skill directory
3. **Maintainability**: Adding new groups or admins requires only config file updates
4. **Testability**: Router script can be tested independently with sample inputs
5. **Backward Compatibility**: Existing submission workflows remain unchanged

## Testing Results

- ✅ Admin users receive auditor confirmation messages
- ✅ Regular employees get standard confirmation messages  
- ✅ Unauthorized users are properly rejected with clear error messages
- ✅ All existing group configurations migrated successfully

## 部署要求



### What Kingdou IS:
- Gateway plugin/module with core logic in `~/.hermes/hermes-agent/gateway/core/handlers.py`
- Hardcoded admin validation via `is_user_admin()` function  
- Dynamic configuration loading (no persistent local config files)
- Script-first architecture that bypasses AI agent entirely
- Performance-optimized for zero-waste execution

### What Kingdou IS NOT:
- Traditional Hermes skill (no SKILL.md, cannot use `skill_view(name='kingdou')`)
- File-based configuration system (no `piecework-groups.json` exists on disk)
- AI-assisted workflow (gateway handles everything directly)

## Deployment Requirements

### 1. Gateway Core Modifications
Must modify `~/.hermes/hermes-agent/gateway/core/handlers.py` to include:
- Hardcoded global_admins list
- Group-specific employee OpenID lists  
- Message parsing and validation logic

### 2. Router Script (Formatting Only)
Create minimal router at `~/.hermes/skills/kingdou/scripts/router/router.py`:
- Contains ONLY reply formatting logic
- NO configuration loading or business validation
- Called by gateway after all processing is complete

### 3. Configuration Data Source
Since no local config files exist, you must:
- Extract configuration from session logs of existing system
- Hardcode group configurations in gateway source
- OR implement dynamic loading from external API/database

### 4. Testing Strategy
- Test with actual Feishu messages (not simulated input)
- Verify gateway bypasses AI agent completely  
- Confirm hardcoded admin/employee lists work correctly

## Critical Files Structure

```
~/.hermes/
├── hermes-agent/gateway/core/handlers.py          # CORE LOGIC (hardcoded configs)
├── skills/kingdou/scripts/router/router.py        # FORMATTING ONLY (no business logic)
└── openid_name_mapping.json                       # OpenID to name mapping
```

## Migration Warning

Attempting to deploy Kingdou as a traditional skill will FAIL because:
1. No central configuration file exists on filesystem
2. Core validation logic is hardcoded in gateway
3. System expects direct gateway integration, not skill-based workflow

Deployment requires **rebuilding the gateway integration**, not copying skill files.

**注意**: 部署指南中的部分描述已过时。当前系统使用中央配置文件 `~/.hermes/skills/kingdou/configs/piecework-groups.json`，并非无持久化配置。
