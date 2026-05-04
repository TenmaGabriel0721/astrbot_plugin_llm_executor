# LLM Executor 使用示例

本文档提供 `astrbot_plugin_llm_executor` 插件的实际使用示例。

## 基础指令执行

### 示例 1: 简单指令（无参数）

**用户消息：**
```
帮我签到
```

**LLM 工具调用：**
```json
{
  "tool": "execute_command",
  "parameters": {
    "command": "签到"
  }
}
```

**返回结果：**
```json
{
  "success": true,
  "command": "签到",
  "result": "✅ 签到成功！获得 10 金币"
}
```

### 示例 2: 带参数的指令

**用户消息：**
```
帮我抽10连
```

**LLM 工具调用：**
```json
{
  "tool": "execute_command",
  "parameters": {
    "command": "抽卡",
    "args": "10"
  }
}
```

**返回结果：**
```json
{
  "success": true,
  "command": "抽卡",
  "args": "10",
  "result": "🎴 十连结果：SSR x1, SR x3, R x6"
}
```

## @ 用户场景

### 示例 3: 禁言指定用户

**前提条件：**
- LLM 已通过其他工具获取到用户"张三"的 QQ 号为 `123456789`

**用户消息：**
```
禁言张三60秒
```

**LLM 工具调用：**
```json
{
  "tool": "execute_command",
  "parameters": {
    "command": "禁言",
    "args": "60",
    "at_qq_list": ["123456789"]
  }
}
```

**返回结果：**
```json
{
  "success": true,
  "command": "禁言",
  "args": "60",
  "result": "✅ 已禁言目标用户 60 秒"
}
```

### 示例 4: 修改群昵称

**用户消息：**
```
把李四的群昵称改成"打工人"
```

**LLM 处理流程：**
1. 获取李四的 QQ 号: `987654321`
2. 调用执行工具

**LLM 工具调用：**
```json
{
  "tool": "execute_command",
  "parameters": {
    "command": "改名",
    "args": "打工人",
    "at_qq_list": ["987654321"]
  }
}
```

**返回结果：**
```json
{
  "success": true,
  "command": "改名",
  "args": "打工人",
  "result": "✅ 已修改李四的群昵称为【打工人】"
}
```

### 示例 5: 设置管理员（多人）

**用户消息：**
```
把张三和李四都设为管理员
```

**LLM 工具调用：**
```json
{
  "tool": "execute_command",
  "parameters": {
    "command": "上管",
    "at_qq_list": ["123456789", "987654321"]
  }
}
```

### 示例 6: 踢出用户

**用户消息：**
```
把发广告的那个人踢了
```

**LLM 处理流程：**
1. 识别"发广告的那个人"的 QQ 号（假设为 `111222333`）
2. 调用执行工具

**LLM 工具调用：**
```json
{
  "tool": "execute_command",
  "parameters": {
    "command": "踢了",
    "at_qq_list": ["111222333"]
  }
}
```

## 图片引用场景

### 示例 7: 设置群头像

**用户消息：**
```
(用户发送图片)
把这个设为群头像
```

**LLM 处理流程：**
1. 从用户消息中提取图片 URL: `http://gchat.qpic.cn/xxx.jpg`
2. 调用执行工具

**LLM 工具调用：**
```json
{
  "tool": "execute_command",
  "parameters": {
    "command": "设置群头像",
    "reply_image_url": "http://gchat.qpic.cn/xxx.jpg"
  }
}
```

**返回结果：**
```json
{
  "success": true,
  "command": "设置群头像",
  "result": "✅ 群头像更新啦>v<"
}
```

### 示例 8: 图片裁剪

**用户消息：**
```
(用户发送图片)
帮我裁剪这张图片，从(100,100)到(300,300)
```

**LLM 工具调用：**
```json
{
  "tool": "execute_command",
  "parameters": {
    "command": "裁剪",
    "args": "100 100 300 300",
    "reply_image_url": "http://gchat.qpic.cn/xxx.jpg"
  }
}
```

## 复合场景

### 示例 9: @ + 参数

**用户消息：**
```
给张三设置头衔"群聊之星"
```

**LLM 工具调用：**
```json
{
  "tool": "execute_command",
  "parameters": {
    "command": "头衔",
    "args": "群聊之星",
    "at_qq_list": ["123456789"]
  }
}
```

### 示例 10: 批量操作

**用户消息：**
```
解除张三和李四的禁言
```

**LLM 工具调用：**
```json
{
  "tool": "execute_command",
  "parameters": {
    "command": "解禁",
    "at_qq_list": ["123456789", "987654321"]
  }
}
```

## 错误处理示例

### 示例 11: 权限不足

**LLM 工具调用：**
```json
{
  "tool": "execute_command",
  "parameters": {
    "command": "全员禁言"
  }
}
```

**返回结果：**
```json
{
  "success": false,
  "error": "指令 全员禁言 需要管理员权限，你不在管理员列表中"
}
```

### 示例 12: 指令不存在

**LLM 工具调用：**
```json
{
  "tool": "execute_command",
  "parameters": {
    "command": "不存在的指令"
  }
}
```

**返回结果：**
```json
{
  "success": false,
  "error": "未找到指令: 不存在的指令"
}
```

### 示例 13: 黑名单拦截

**LLM 工具调用：**
```json
{
  "tool": "execute_command",
  "parameters": {
    "command": "踢人"
  }
}
```

**返回结果（假设"踢人"在黑名单中）：**
```json
{
  "success": false,
  "error": "指令 踢人 在黑名单中"
}
```

## 最佳实践

### 实践 1: 先搜索后执行

```
用户: 帮我查看背包

LLM 流程:
1. 调用 search_command(keyword="背包") 确认指令存在
2. 确认后调用 execute_command(command="背包")
```

### 实践 2: 获取 QQ 号后执行

```
用户: 禁言张三

LLM 流程:
1. 调用群成员查询工具获取"张三"的 QQ 号
2. 获取到 QQ 号后调用 execute_command(command="禁言", at_qq_list=["123456789"])
```

### 实践 3: 确认图片 URL

```
用户: (发送图片) 设为群头像

LLM 流程:
1. 从 event.message_obj 中提取图片 URL
2. 验证 URL 有效后调用 execute_command(command="设置群头像", reply_image_url="...")
```

### 实践 4: 错误处理和重试

```python
# 伪代码示例
result = execute_command(command="禁言", at_qq_list=["123456789"])

if not result["success"]:
    if "权限" in result["error"]:
        # 告知用户权限不足
        return "抱歉，我没有权限执行此操作"
    elif "未找到" in result["error"]:
        # 建议用户使用 list_executable_commands
        return "指令不存在，可以用'列出指令'查看可用功能"
```

## 与其他工具配合

### 配合 command_query 插件

```
用户: 有什么钓鱼相关的功能吗？

LLM 流程:
1. 调用 search_command(keyword="钓鱼")
2. 获取到"钓鱼"指令的信息
3. 回复用户并询问是否执行
4. 用户确认后调用 execute_command(command="钓鱼")
```

### 配合群成员查询工具

```
用户: 禁言今天发言最多的人5分钟

LLM 流程:
1. 调用群成员统计工具找出发言最多的用户
2. 获取该用户的 QQ 号
3. 调用 execute_command(command="禁言", args="300", at_qq_list=["获取到的QQ号"])
```

## 注意事项

1. **QQ 号格式**：必须是字符串数组，如 `["123456789"]`
2. **图片 URL**：必须是完整的 http/https URL
3. **参数顺序**：某些指令对参数顺序敏感，注意 `args` 的格式
4. **权限检查**：执行前可以通过 `list_executable_commands` 确认权限
5. **错误处理**：始终检查返回的 `success` 字段
6. **日志记录**：所有执行都会记录日志，便于调试

## 测试建议

1. **单元测试**：测试基础指令执行
2. **集成测试**：测试 @ 和图片引用功能
3. **权限测试**：测试白名单/黑名单/管理员权限
4. **错误测试**：测试各种异常情况
5. **性能测试**：测试并发执行多个指令