# AstrBot LLM 指令执行器插件

让 LLM 能够代理用户或以 Bot 自身身份执行 AstrBot 指令，实现自然语言到指令的转换，并通过 AstrBot 原生过滤器和权限策略控制管理员指令。

## 功能特性

- 🎮 **指令代理执行**：LLM 可以通过 `execute_command` 工具执行 Bot 指令
- 🤖 **Bot 自身执行**：Bot 可以以自己的身份执行指令，拥有独立的游戏账户
- 📋 **指令列表查询**：LLM 可以通过 `list_executable_commands` 工具获取可执行的指令列表
- 🔒 **安全控制**：支持白名单、黑名单、管理员指令权限控制和 AstrBot 原生过滤器校验
- 👤 **管理员用户列表**：支持配置特定用户执行管理员指令
- 🛡️ **Bot 管理员身份**：当 `bot_user_id` 是 AstrBot 框架管理员时，可在 `as_bot=true` 下以 Bot 身份执行低风险管理员指令
- 🔄 **自动缓存**：自动缓存指令处理器，提高执行效率

## 设计理念

本插件**配合 `astrbot_plugin_command_query` 使用**：

- `astrbot_plugin_command_query` 负责：查询指令名（LLM 用 `search_command` 工具查找指令）
- `astrbot_plugin_llm_executor` 负责：执行指令（LLM 用 `execute_command` 工具执行指令）

## 工作流程示例

1. 用户说："帮我钓鱼"
2. LLM 可能先调用 `search_command(keyword="钓鱼")` 确认指令存在
3. LLM 调用 `execute_command(command="钓鱼")` 执行指令
4. 插件执行指令并返回结果
5. LLM 组织自然语言回复用户

## LLM 工具函数

### execute_command

执行 Bot 指令。

**参数：**
- `command` (string, 必需): 要执行的指令名（不含前缀），如 "钓鱼"、"签到"、"背包"
- `args` (string, 可选): 指令参数，多个参数用空格分隔
- `at_qq_list` (array[string], 可选): 需要 @ 的目标用户 QQ 号列表
- `reply_image_url` (string, 可选): 需要引用图片时传入图片地址
- `as_bot` (boolean, 可选): 是否以 Bot 自己的身份执行指令（默认 false）
  - `false`（默认）：代理用户执行，使用用户的身份和账户
  - `true`：Bot 自己执行，使用 Bot 自己的身份和账户
  - 管理员指令只有在 `bot_user_id` 已加入 AstrBot 框架 `admins_id`，且请求可信、明确、低风险时才建议使用 `true`

**返回：**
JSON 格式的执行结果，包含 `success`、`command`、`result`、`executed_as` 或 `error` 字段

**示例：**
```
# 代理用户执行（默认）
execute_command(command="钓鱼")

# Bot 自己执行
execute_command(command="钓鱼", as_bot=true)

# Bot 自己签到
execute_command(command="签到", as_bot=true)

# 代理用户转账
execute_command(command="转账", args="@用户 100")
```

### list_executable_commands

列出可执行的指令。

**参数：**
- `category` (string, 可选): 按插件名筛选

**返回：**
JSON 格式的可执行指令列表，按插件分组

## 配置说明

在 AstrBot 管理面板中配置以下选项：

| 配置项 | 类型 | 默认值 | 说明 |
|--------|------|--------|------|
| `enabled` | bool | true | 是否启用 LLM 指令执行器 |
| `whitelist` | list | [] | 允许执行的指令白名单（空数组表示允许所有） |
| `blacklist` | list | [] | 禁止执行的指令黑名单 |
| `allow_admin_commands` | bool | false | 是否允许所有用户执行管理员指令 |
| `admin_users` | list | [] | 管理员用户列表，这些用户可以执行管理员指令 |
| `bot_user_id` | string | "bot_self" | Bot 自己的用户 ID，用于 as_bot=true 时的身份标识 |
| `enable_forward` | bool | true | 长文本结果是否自动使用合并转发 |
| `forward_threshold` | int | 1500 | 触发合并转发的文本长度阈值 |
| `at_position_mode` | string | "before_args" | 未使用 @ 占位符时，@ 用户默认放在参数前还是参数后 |
| `command_at_position_map` | object | {} | 按指令覆盖 @ 用户插入位置 |

### 配置示例

**只允许执行特定指令：**
```json
{"enabled": true,
    "whitelist": ["钓鱼", "签到", "背包", "状态"],
    "blacklist": [],
    "allow_admin_commands": false,
    "admin_users": []
}
```

**禁止执行敏感指令：**
```json
{
    "enabled": true,
    "whitelist": [],
    "blacklist": ["转账", "购买", "上架"],
    "allow_admin_commands": false,
    "admin_users": []
}
```

**允许特定用户执行管理员指令：**
```json
{
    "enabled": true,
    "whitelist": [],
    "blacklist": [],
    "allow_admin_commands": false,
    "admin_users": ["123456789", "987654321"]
}
```

**配置 Bot 用户 ID：**
```json
{
    "enabled": true,
    "whitelist": [],
    "blacklist": [],
    "allow_admin_commands": false,
    "admin_users": [],
    "bot_user_id": "123456789"
}
```
注：`bot_user_id` 可以设置为 Bot 的 QQ 号或其他唯一标识。

### Bot 自身执行功能说明

当使用 `as_bot=true` 参数时：

1. **独立身份**：Bot 会使用配置的 `bot_user_id` 作为自己的身份
2. **独立账户**：在游戏类插件中（如钓鱼），Bot 会拥有自己独立的账户、金币、物品等
3. **使用场景**：
   - 用户说"你也去钓鱼吧" → LLM 使用 `execute_command(command="钓鱼", as_bot=true)`
   - 用户说"帮我钓鱼" → LLM 使用 `execute_command(command="钓鱼")` （代理用户）
   - 用户说"看看你的背包" → LLM 使用 `execute_command(command="背包", as_bot=true)`

**注意事项**：
- Bot 需要先注册才能执行需要账户的指令
- Bot 的游戏数据与用户完全独立
- Bot 可以与用户进行互动（如转账、交易等）

### 管理员权限说明

管理员指令的执行权限检查逻辑如下：

1. 如果指令不是管理员指令，按用户意图正常执行
2. 如果指令是管理员指令：
   - 用户 ID 在 `admin_users` 列表中时允许执行
   - `allow_admin_commands=true` 时允许所有用户执行（不推荐）
   - 当 `as_bot=true` 且 `bot_user_id` 已加入 AstrBot 框架 `admins_id` 时，允许以 Bot 自身管理员身份执行
   - 其他情况拒绝执行

建议的 LLM 行为：
- 普通非管理员指令无需额外限制，默认代理用户，明确要求 Bot 自己参与时使用 `as_bot=true`
- 管理员指令需要确认用户可信、目标明确、参数明确且操作低风险后再执行
- 重启、关闭、停止、更新、重载、删除、清空、重置、权限变更、群发、广播、@全体等高影响管理员指令默认不要自动执行

这意味着：
- `admin_users` 列表中的用户可以执行管理员指令，无需开启 `allow_admin_commands`
- `allow_admin_commands` 是全局开关，开启后所有用户都可以执行管理员指令（不推荐）
- 如果希望 Bot 以自己的管理员身份执行低风险管理员指令，需要同时设置插件的 `bot_user_id`，并把同一个 ID 加入 AstrBot 主配置的 `admins_id`

## 用户指令

| 指令 | 别名 | 说明 |
|------|------|------|
| `/刷新指令缓存` | `refresh_commands` | 手动刷新指令处理器缓存 |
| `/执行器状态` | `executor_status` | 查看 LLM 指令执行器状态 |

## 安全注意事项

⚠️ **警告**：
- 推荐优先使用 `admin_users` 或 Bot 框架管理员身份控制管理员指令，不推荐开启 `allow_admin_commands`
- `allow_admin_commands` 会让所有用户都可以执行管理员指令，请确保您了解潜在风险
- 即使 Bot 可以以框架管理员身份执行指令，也应在 LLM 人格或工具描述中限制高影响管理员操作
- 重启、关闭、删除、清空、重置、权限变更、群发、广播、@全体等操作建议始终人工确认
- 建议根据实际场景配置黑名单或白名单，降低误调用风险

## 依赖

- AstrBot 框架
- 建议配合 `astrbot_plugin_command_query` 插件使用

## 作者

珈百璃

## 版本历史

### v1.2.0
- ✨ 支持 `as_bot=true` 且 `bot_user_id` 是 AstrBot 框架管理员时，以 Bot 自身管理员身份执行管理员指令
- ✅ 执行目标指令前复用 AstrBot 原生过滤器和参数解析
- 🛡️ 增强事件状态恢复，避免执行失败后污染原事件
- 📝 更新工具描述和安全说明，补充高影响管理员指令默认不自动执行

### v1.1.0
- ✨ 新增 `as_bot` 参数，支持 Bot 以自己的身份执行指令
- ✨ 新增 `bot_user_id` 配置项，用于标识 Bot 的用户 ID
- 📝 更新文档，说明 Bot 自身执行功能
- 🎮 Bot 可以在游戏中拥有独立的账户和资产

### v1.0.0
- 🎉 初始版本
- ✅ 支持 `execute_command` 和 `list_executable_commands` LLM 工具
- ✅ 支持白名单、黑名单和管理员指令权限控制
- ✅ 支持 `admin_users` 管理员用户列表配置