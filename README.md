# AstrBot LLM 指令执行器插件

让 LLM 能够代理执行 Bot 指令，实现自然语言到指令的转换。

## 功能特性

- 🎮 **指令代理执行**：LLM 可以通过 `execute_command` 工具执行 Bot 指令
- 📋 **指令列表查询**：LLM 可以通过 `list_executable_commands` 工具获取可执行的指令列表
- 🔒 **安全控制**：支持白名单、黑名单和管理员指令权限控制
- 👤 **管理员用户列表**：支持配置特定用户执行管理员指令
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

**返回：**
JSON 格式的执行结果，包含 `success`、`command`、`result` 或 `error` 字段

**示例：**
```
execute_command(command="钓鱼")
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

### 管理员权限说明

管理员指令的执行权限检查逻辑如下：

1. 如果指令不是管理员指令，直接允许执行
2. 如果指令是管理员指令：
   - 首先检查用户 ID 是否在 `admin_users` 列表中，如果在则允许执行
   - 如果不在 `admin_users` 列表中，检查 `allow_admin_commands` 配置
   - 如果 `allow_admin_commands` 为 true，允许执行
   - 否则拒绝执行

这意味着：
- `admin_users` 列表中的用户可以执行管理员指令，无需开启 `allow_admin_commands`
- `allow_admin_commands` 是全局开关，开启后所有用户都可以执行管理员指令（不推荐）

## 用户指令

| 指令 | 别名 | 说明 |
|------|------|------|
| `/刷新指令缓存` | `refresh_commands` | 手动刷新指令处理器缓存 |
| `/执行器状态` | `executor_status` | 查看 LLM 指令执行器状态 |

## 安全注意事项

⚠️ **警告**：
- 默认情况下，管理员指令（如修改金币、奖励道具等）不允许通过 LLM 执行
- 推荐使用 `admin_users` 配置特定用户的管理员权限，而不是开启 `allow_admin_commands`
- 如果启用 `allow_admin_commands`，请确保您了解潜在的安全风险
- 建议使用白名单模式，只允许执行安全的指令

## 依赖

- AstrBot 框架
- 建议配合 `astrbot_plugin_command_query` 插件使用

## 作者

珈百璃

## 版本历史

### v1.0.0
- 初始版本
- 支持 `execute_command` 和 `list_executable_commands` LLM 工具
- 支持白名单、黑名单和管理员指令权限控制
- 支持 `admin_users` 管理员用户列表配置