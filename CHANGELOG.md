# 更新日志

## [1.1.0] - 2026-01-03

### ✨ 新增功能

- **Bot 自身执行模式**：新增 `as_bot` 参数，支持 Bot 以自己的身份执行指令
  - `as_bot=false`（默认）：代理用户执行，使用用户的身份和账户
  - `as_bot=true`：Bot 自己执行，使用 Bot 自己的身份和账户
  
- **Bot 用户 ID 配置**：新增 `bot_user_id` 配置项
  - 用于标识 Bot 的用户 ID
  - 默认值为 `"bot_self"`
  - 可配置为 Bot 的 QQ 号或其他唯一标识

### 🔧 技术改进

- 实现了事件发送者 ID 的动态替换机制
- 在执行指令时临时修改 `event.unified_msg_origin.sender.user_id`
- 执行完成后自动恢复原始发送者 ID
- 返回结果中添加 `executed_as` 字段标识执行身份

### 📝 文档更新

- 更新 `README.md`，添加 Bot 自身执行功能说明
- 新增 `BOT_SELF_EXECUTION.md` 详细使用指南
- 更新配置文件 `_conf_schema.json`
- 更新插件版本号和描述

### 🎮 使用场景

Bot 现在可以：
- 在钓鱼游戏中拥有自己的账户
- 与用户一起玩游戏
- 进行交易和转账
- 参与竞争和挑战
- 更自然地参与对话互动

### 📋 API 变更

#### execute_command 工具函数

新增参数：
```python
as_bot (boolean, 可选): 是否以Bot自己的身份执行指令（默认false）
```

返回值新增字段：
```json
{
    "executed_as": "bot" // "bot" 或 "user"
}
```

### 🔍 示例

```python
# 代理用户钓鱼
execute_command(command="钓鱼")
execute_command(command="钓鱼", as_bot=false)

# Bot 自己钓鱼
execute_command(command="钓鱼", as_bot=true)

# Bot 查看自己的背包
execute_command(command="背包", as_bot=true)

# Bot 给用户转账
execute_command(command="转账", args="@user 100", as_bot=true)
```

### ⚠️ 注意事项

- Bot 需要先注册才能执行需要账户的指令
- Bot 的账户与所有用户完全独立
- 确保 `bot_user_id` 配置正确且唯一
- 某些老旧插件可能不支持此功能

---

## [1.0.0] - 初始版本

### 🎉 首次发布

- 支持 LLM 代理执行 Bot 指令
- 支持 `execute_command` 工具函数
- 支持 `list_executable_commands` 工具函数
- 支持白名单和黑名单控制
- 支持管理员指令权限控制
- 支持管理员用户列表配置
- 支持特殊参数（`at_qq_list`、`reply_image_url`）
- 自动缓存指令处理器