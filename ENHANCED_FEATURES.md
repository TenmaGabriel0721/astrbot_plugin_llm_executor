# LLM Executor 增强功能文档

## 概述

`astrbot_plugin_llm_executor` v1.1 新增了对特殊参数的支持，使 LLM 能够执行需要 @ 用户和引用图片的指令。

## 新增功能

### 1. @ 用户支持 (at_qq_list)

**功能说明：**
- 允许 LLM 在执行指令时 @ 指定的 QQ 用户
- 适用于需要指定目标用户的指令（如禁言、踢人、改名等）

**使用场景：**
```json
// 场景1: 禁言用户
{
  "command": "禁言",
  "args": "60",
  "at_qq_list": ["123456789"]
}

// 场景2: 设置管理员
{
  "command": "上管",
  "at_qq_list": ["123456789", "987654321"]
}

// 场景3: 踢出用户
{
  "command": "踢了",
  "at_qq_list": ["123456789"]
}
```

**对话示例：**
```
用户: 帮我禁言张三60秒
LLM: (先通过其他工具获取张三的QQ号: 123456789)
     execute_command(command="禁言", args="60", at_qq_list=["123456789"])
Bot: ✅ 已禁言张三60秒
```

### 2. 引用图片支持 (reply_image_url)

**功能说明：**
- 允许 LLM 在执行指令时引用图片
- 适用于需要图片作为输入的指令（如设置群头像、图片裁剪等）

**使用场景：**
```json
// 场景1: 设置群头像
{
  "command": "设置群头像",
  "reply_image_url": "http://example.com/image.jpg"
}

// 场景2: 裁剪图片
{
  "command": "裁剪",
  "args": "100 100 200 200",
  "reply_image_url": "http://example.com/image.jpg"
}
```

**对话示例：**
```
用户: (发送图片) 把这个设为群头像
LLM: (先通过 message 获取图片URL: http://xxx.com/image.jpg)
     execute_command(command="设置群头像", reply_image_url="http://xxx.com/image.jpg")
Bot: ✅ 群头像更新啦>v<
```

## 技术实现

### 消息组件构建

插件通过 `_build_message_components()` 方法构建消息组件：

```python
def _build_message_components(self, command: str, args: str = "", 
                              at_qq_list: List[str] = None, 
                              reply_image_url: str = None) -> List:
    components = []
    
    # 1. 添加图片引用（如果有）
    if reply_image_url:
        reply_chain = [Image(url=reply_image_url)]
        reply_comp = Reply(id=0, sender_id=0, chain=reply_chain)
        components.append(reply_comp)
    
    # 2. 添加指令文本
    command_text = f"/{command}"
    if args:
        command_text += f" {args}"
    components.append(Plain(text=command_text))
    
    # 3. 添加 @ 组件（如果有）
    if at_qq_list:
        for qq in at_qq_list:
            components.append(At(qq=str(qq)))
    
    return components
```

### 消息对象修改

执行指令时，插件会：
1. 修改 `event.message_str` 为指令格式
2. 如果有特殊参数，构建并替换 `event.message_obj.message`
3. 执行完成后恢复原始状态

## 兼容性说明

### 向后兼容
- 原有的 `execute_command(command, args)` 调用方式完全兼容
- 新参数 `at_qq_list` 和 `reply_image_url` 为可选参数

### 依赖要求
- AstrBot 核心版本需支持 `astrbot.core.message.components`
- 目标插件需正确处理 `message_obj` 中的消息组件

### 支持的插件类型

**完全支持：**
- ✅ qqadmin 系列指令（禁言、踢人、改名等）
- ✅ gifcaijian 图片裁剪指令
- ✅ 其他使用 `get_ats()` 和 `extract_image_url()` 的插件

**部分支持：**
- ⚠️ 只解析 `message_str` 的插件（仅支持文本参数）

**不支持：**
- ❌ 需要特殊消息格式的插件（需要插件侧适配）

## 使用建议

### 对于 LLM 使用者

1. **获取 QQ 号**：在使用 `at_qq_list` 前，确保已通过其他工具获取到目标用户的 QQ 号
2. **图片 URL**：确保 `reply_image_url` 是可访问的完整 URL
3. **权限检查**：注意某些指令可能需要管理员权限

### 对于插件开发者

如果你的插件需要支持 LLM Executor：

1. **使用标准消息组件**：
   ```python
   from astrbot.core.message.components import At, Reply, Image
   
   def get_ats(event):
       return [seg.qq for seg in event.get_messages() if isinstance(seg, At)]
   
   def extract_image_url(chain):
       for seg in chain:
           if isinstance(seg, Image):
               return seg.url
           elif isinstance(seg, Reply) and seg.chain:
               for reply_seg in seg.chain:
                   if isinstance(reply_seg, Image):
                       return reply_seg.url
       return None
   ```

2. **同时支持 message_str 和 message_obj**：
   ```python
   async def my_handler(self, event):
       # 方式1: 从 message_obj 获取
       ats = get_ats(event)
       
       # 方式2: 从 message_str 解析（兼容旧版）
       if not ats and '@' in event.message_str:
           # 解析逻辑...
   ```

## 示例代码

### 完整使用示例

```python
# 场景1: 禁言用户（需要@）
result = await execute_command(
    command="禁言",
    args="60",
    at_qq_list=["123456789"]
)

# 场景2: 设置群头像（需要图片）
result = await execute_command(
    command="设置群头像",
    reply_image_url="http://example.com/avatar.jpg"
)

# 场景3: 复合操作
result = await execute_command(
    command="改名",
    args="新昵称",
    at_qq_list=["123456789"]
)

# 场景4: 传统方式（完全兼容）
result = await execute_command(
    command="钓鱼"
)
```

## 常见问题

### Q: 为什么我的指令没有正确 @ 用户？
A: 检查以下几点：
1. 目标插件是否支持从 `message_obj` 中解析 At 组件
2. QQ 号格式是否正确（字符串类型）
3. 查看日志确认消息组件是否正确构建

### Q: 图片引用不生效怎么办？
A: 确保：
1. 图片 URL 可访问且格式正确
2. 目标插件支持从 Reply 组件中提取图片
3. 图片 URL 使用 http/https 协议

### Q: 可以同时使用 at_qq_list 和 reply_image_url 吗？
A: 可以，插件会同时构建两种组件。但具体是否生效取决于目标插件的实现。

## 版本历史

### v1.1.0 (2025-12-27)
- ✨ 新增 `at_qq_list` 参数支持
- ✨ 新增 `reply_image_url` 参数支持
- ✨ 新增 `_build_message_components()` 方法
- 📝 更新文档和使用说明
- 🐛 改进错误处理和日志记录

### v1.0.0
- 🎉 初始版本发布
- ✅ 基础指令执行功能
- ✅ 权限控制（白名单/黑名单）