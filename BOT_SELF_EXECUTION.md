# Bot 自身执行功能详解

## 概述

从 v1.1.0 版本开始，`astrbot_plugin_llm_executor` 支持 Bot 以自己的身份执行指令，使 Bot 不仅能代理用户执行操作，还能作为独立个体参与游戏和互动。

## 核心概念

### 两种执行模式

1. **代理模式**（`as_bot=false`，默认）
   - Bot 代理用户执行指令
   - 使用用户的身份、账户和资产
   - 适用场景：用户请求 Bot 帮助完成操作

2. **自主模式**（`as_bot=true`）
   - Bot 以自己的身份执行指令
   - 使用 Bot 自己的账户和资产
   - 适用场景：Bot 作为独立个体参与活动

## 配置说明

### bot_user_id 配置

在插件配置中设置 Bot 的用户 ID：

```json
{
    "bot_user_id": "bot_123456789"
}
```

**推荐设置：**
- 如果 Bot 有 QQ 号，可以设置为 Bot 的 QQ 号
- 也可以使用自定义的唯一标识符，如 `"bot_self"`、`"assistant_ai"` 等
- 确保该 ID 在系统中是唯一的

## 使用示例

### 场景 1：钓鱼游戏

**用户请求帮助（代理模式）：**
```
用户: "帮我钓鱼"
LLM: execute_command(command="钓鱼", as_bot=false)
结果: 使用用户的账户钓鱼，金币和鱼类归用户所有
```

**用户邀请 Bot 参与（自主模式）：**
```
用户: "你也去钓鱼吧"
LLM: execute_command(command="钓鱼", as_bot=true)
结果: 使用 Bot 自己的账户钓鱼，Bot 获得金币和鱼类
```

### 场景 2：查看状态

**查看用户状态：**
```
用户: "看看我的状态"
LLM: execute_command(command="状态", as_bot=false)
结果: 显示用户的游戏状态
```

**查看 Bot 状态：**
```
用户: "你的状态怎么样"
LLM: execute_command(command="状态", as_bot=true)
结果: 显示 Bot 自己的游戏状态
```

### 场景 3：签到

**用户签到：**
```
用户: "签到"
LLM: execute_command(command="签到", as_bot=false)
结果: 用户完成签到，获得奖励
```

**Bot 自己签到：**
```
用户: "你也签个到吧"
LLM: execute_command(command="签到", as_bot=true)
结果: Bot 完成签到，Bot 获得奖励
```

### 场景 4：互动场景

**用户向 Bot 转账：**
```
用户: "给你转 1000 金币"
LLM: execute_command(command="转账", args="1000", at_qq_list=[bot_user_id], as_bot=false)
结果: 用户向 Bot 转账 1000 金币
```

**Bot 向用户转账：**
```
用户: "你能给我一些金币吗"
LLM: execute_command(command="转账", args="500", at_qq_list=[user_id], as_bot=true)
结果: Bot 向用户转账 500 金币（如果 Bot 有足够金币）
```

## 技术实现

### 身份切换机制

当 `as_bot=true` 时，插件会：

1. **保存原始发送者 ID**
   ```python
   original_sender_id = event.unified_msg_origin.sender.user_id
   ```

2. **替换为 Bot 的 ID**
   ```python
   event.unified_msg_origin.sender.user_id = self.bot_user_id
   ```

3. **执行指令**
   - 目标插件通过 `event.get_sender_id()` 获取到的是 Bot 的 ID
   - 所有操作都作用于 Bot 的账户

4. **恢复原始 ID**
   ```python
   event.unified_msg_origin.sender.user_id = original_sender_id
   ```

### 返回值标识

执行结果中会包含 `executed_as` 字段：

```json
{
    "success": true,
    "command": "钓鱼",
    "result": "🎣 恭喜你钓到了：小丑鱼...",
    "executed_as": "bot"  // "bot" 或 "user"
}
```

## 适用插件

### 完全支持

以下类型的插件完全支持 Bot 自身执行：

- ✅ **钓鱼游戏**（astrbot_plugin_fishing）
  - Bot 可以注册、钓鱼、签到
  - Bot 拥有独立的金币、背包、鱼塘
  - Bot 可以参与市场交易

- ✅ **签到系统**
  - Bot 可以每日签到获得奖励

- ✅ **经济系统**
  - Bot 可以拥有金币
  - Bot 可以与用户进行转账

- ✅ **背包系统**
  - Bot 可以拥有物品
  - Bot 可以使用道具

- ✅ **轻量管理员操作**（需谨慎）
  - 当 `bot_user_id` 已加入 AstrBot 框架 `admins_id`，且 LLM 使用 `as_bot=true` 时，Bot 可以以自身管理员身份执行管理员指令
  - 仅建议用于可信用户明确要求的低风险、目标明确、参数明确的管理操作
  - 重启、关闭、停止、更新、重载、删除、清空、重置、权限变更、群发、广播、@全体等高影响操作默认不应自动执行

### 部分支持

- ⚠️ **社交功能**
  - 需要插件支持识别 Bot 身份
  - 某些互动功能可能需要特殊处理

### 不推荐

- ❌ **管理员指令**
  - Bot 通常不应执行管理员指令
  - 如需执行，需要特别配置权限

## 最佳实践

### 1. 语义识别

LLM 应该能够识别用户的意图：

```python
# 需要代理用户
"帮我钓鱼" → as_bot=false
"帮我签到" → as_bot=false
"查看我的背包" → as_bot=false

# Bot 自己执行
"你也去钓鱼" → as_bot=true
"你自己签个到" → as_bot=true
"看看你的背包" → as_bot=true
```

### 2. 初始化

Bot 第一次参与游戏时需要注册：

```python
# Bot 注册
execute_command(command="注册", as_bot=true)
```

### 3. 自然对话

Bot 可以更自然地参与对话：

```
用户: "我们一起去钓鱼吧"
Bot: "好的！" 
     execute_command(command="钓鱼", as_bot=false)  // 先帮用户钓
     execute_command(command="钓鱼", as_bot=true)   // 再自己钓
     "我钓到了一条小鱼！"
```

### 4. 竞争与合作

Bot 可以与用户形成竞争或合作关系：

```python
# 竞争：比谁钓的鱼多
用户钓鱼 → as_bot=false
Bot 钓鱼 → as_bot=true
比较结果

# 合作：Bot 给用户道具
Bot 转账给用户 → as_bot=true
```

## 注意事项

### 1. 账户独立性

- Bot 的账户与所有用户完全独立
- Bot 需要自己积累资源（金币、物品等）
- Bot 的操作不会影响用户的资产

### 2. 权限限制

- 普通非管理员指令可以按用户意图代理用户或以 Bot 自身身份执行
- Bot 执行管理员指令需要将插件配置中的 `bot_user_id` 加入 AstrBot 框架主配置 `admins_id`
- 管理员指令只建议用于可信用户明确要求的低风险操作
- 重启、关闭、停止、更新、重载、删除、清空、重置、权限变更、群发、广播、@全体等高影响管理员操作默认不应自动执行

### 3. 资源管理

- Bot 的资源有限，需要合理使用
- 可以通过管理员指令给 Bot 充值
- Bot 可以通过游戏机制获取资源

### 4. 冷却时间

- Bot 和用户的冷却时间是独立的
- Bot 钓鱼不会影响用户的钓鱼冷却
- 可以实现"轮流钓鱼"的玩法

## 故障排查

### 问题 1：Bot 执行指令提示"未注册"

**原因**：Bot 还没有游戏账户

**解决**：
```python
execute_command(command="注册", as_bot=true)
```

### 问题 2：Bot 身份识别不正确

**原因**：`bot_user_id` 配置不正确

**解决**：
1. 检查配置文件中的 `bot_user_id`
2. 确保 ID 唯一且不与其他用户冲突
3. 重启插件使配置生效

### 问题 3：Bot 无法执行某些指令

**原因**：插件不支持身份切换机制

**解决**：
1. 检查目标插件是否使用 `event.get_sender_id()` 获取用户 ID
2. 某些老旧插件可能需要更新才能支持

## 示例对话

### 完整互动示例

```
用户: "我们来比赛钓鱼吧"
Bot: "好的！我们一起钓鱼看谁钓得多！"
     execute_command(command="钓鱼", as_bot=true)
     "我钓到了一条草鱼！你也试试吧~"

用户: "钓鱼"
Bot: execute_command(command="钓鱼", as_bot=false)
     "哇！你钓到了金枪鱼，看来你运气更好呢！"

用户: "看看你的背包"
Bot: execute_command(command="背包", as_bot=true)
     "我的背包里有：草鱼 x1，金币 50"

用户: "我给你一些金币"
Bot: execute_command(command="转账", args="@bot 100", as_bot=false)
     "谢谢你！现在我有 150 金币了~"
```

## 总结

Bot 自身执行功能使得 Bot 不再只是一个工具，而是可以作为游戏中的独立个体与用户互动。这为创造更丰富、更有趣的用户体验提供了可能性。

合理使用 `as_bot` 参数，可以实现：
- 🎮 Bot 与用户一起玩游戏
- 🤝 Bot 与用户进行交易和互动
- 🏆 Bot 参与竞争和挑战
- 💬 更自然的对话体验