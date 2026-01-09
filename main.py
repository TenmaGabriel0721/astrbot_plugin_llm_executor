import json
from typing import Dict, List, Optional, Any
from astrbot.api.event import filter, AstrMessageEvent, MessageEventResult
from astrbot.api.star import Context, Star, register
from astrbot.api import logger, AstrBotConfig
from astrbot.core.star.filter.command import CommandFilter
from astrbot.core.star.filter.command_group import CommandGroupFilter
from astrbot.core.star.filter.permission import PermissionTypeFilter
from astrbot.core.star.star_handler import star_handlers_registry, StarHandlerMetadata
from astrbot.core.message.components import At, Plain, Image, Reply, Node, Nodes


class BotIdentityEventWrapper:
    """
    事件包装器，用于覆盖 get_sender_id() 方法返回Bot的ID
    """
    def __init__(self, original_event: AstrMessageEvent, bot_user_id: str):
        self._original_event = original_event
        self._bot_user_id = bot_user_id
    
    def get_sender_id(self):
        """返回Bot的ID而不是原始发送者ID"""
        return self._bot_user_id
    
    def __getattr__(self, name):
        """其他所有属性和方法都委托给原始事件对象"""
        return getattr(self._original_event, name)
    
    def __setattr__(self, name, value):
        """设置属性"""
        if name in ('_original_event', '_bot_user_id'):
            object.__setattr__(self, name, value)
        else:
            setattr(self._original_event, name, value)


@register(
    "astrbot_plugin_llm_executor",
    "珈百璃",
    "让LLM代理执行Bot指令或以Bot自身执行，配合command_query插件使用",
    "1.1.0"
)
class LLMExecutorPlugin(Star):
    """
    AstrBot LLM 指令执行器插件 v1.1
    
    【核心功能】
    让 LLM 能够代理执行普通插件指令，或以 Bot 自身执行指令，实现自然语言到指令的转换。
    
    【设计理念】
    - 配合 astrbot_plugin_command_query 使用
    - command_query 负责：查询指令名（LLM 用 search_command 工具查找指令）
    - llm_executor 负责：执行指令（LLM 用 execute_command 工具执行指令）
    
    【工作流程示例】
    1. 用户说："帮我钓鱼"
    2. LLM 可能先调用 search_command(keyword="钓鱼") 确认指令存在
    3. LLM 调用 execute_command(command="钓鱼") 执行指令
    4. 插件执行指令并返回结果
    5. LLM 组织自然语言回复用户
    """
    
    def __init__(self, context: Context, config: AstrBotConfig = None):
        """插件初始化"""
        super().__init__(context)
        self.config = config or {}
        self._handler_cache: Dict[str, Dict] = {}
        self._alias_to_command: Dict[str, str] = {}
        
        # 配置项
        self.enabled = self.config.get("enabled", True)
        self.whitelist: List[str] = self.config.get("whitelist", [])
        self.blacklist: List[str] = self.config.get("blacklist", [])
        self.allow_admin_commands = self.config.get("allow_admin_commands", False)
        self.admin_users: List[str] = self.config.get("admin_users", [])
        self.bot_user_id = self.config.get("bot_user_id", "bot_self")
        self.enable_forward = self.config.get("enable_forward", True)
        self.forward_threshold = self.config.get("forward_threshold", 1500)
        
        logger.info(f"LLM指令执行器插件已加载 v1.1")
        logger.info(f"  - 启用状态: {self.enabled}")
        logger.info(f"  - 白名单: {self.whitelist if self.whitelist else '无限制'}")
        logger.info(f"  - 黑名单: {self.blacklist if self.blacklist else '无'}")
        logger.info(f"  - 允许管理员指令: {self.allow_admin_commands}")
        logger.info(f"  - 管理员用户: {self.admin_users if self.admin_users else '无'}")
        logger.info(f"  - Bot用户ID: {self.bot_user_id}")
        logger.info(f"  - 合并转发: {'启用' if self.enable_forward else '禁用'} (阈值: {self.forward_threshold}字)")

    async def _initialize(self):
        """异步初始化，构建指令处理器缓存"""
        self._build_handler_cache()
        logger.info(f"已缓存 {len(self._handler_cache)} 个指令处理器")

    def _build_handler_cache(self):
        """构建指令名到处理器的映射 - 优化版 O(N+M)"""
        self._handler_cache.clear()
        self._alias_to_command.clear()
        
        try:
            # 获取所有已激活的插件
            all_stars = self.context.get_all_stars()
            all_stars = [star for star in all_stars if star.activated]
        except Exception as e:
            logger.error(f"获取插件列表失败: {e}")
            return
        
        if not all_stars:
            logger.warning("没有找到任何激活的插件")
            return
        
        # 跳过的插件列表
        skip_plugins = {
            "astrbot",
            "astrbot_plugin_llm_executor",
            "astrbot_plugin_command_query",
            "astrbot-reminder"
        }
        
        # === 优化关键: O(N) - 预构建 module_path -> (star, plugin_name) 的索引 ===
        module_to_star = {}
        for star in all_stars:
            plugin_name = getattr(star, "name", "未知插件")
            module_path = getattr(star, "module_path", None)
            
            # 跳过核心插件和自身
            if plugin_name in skip_plugins or not module_path:
                continue
            
            module_to_star[module_path] = (star, plugin_name)
        
        # === O(M) - 只遍历一次处理器注册表，使用 O(1) 字典查找 ===
        for handler in star_handlers_registry:
            if not isinstance(handler, StarHandlerMetadata):
                continue
            
            # O(1) 哈希查找，替代原来的 O(N) 内层循环
            star_info = module_to_star.get(handler.handler_module_path)
            if not star_info:
                continue
            
            star, plugin_name = star_info
            
            command_name = None
            aliases = []
            description = handler.desc or "无描述"
            is_admin_command = False
            
            # 查找命令过滤器和权限过滤器
            for filter_ in handler.event_filters:
                if isinstance(filter_, CommandFilter):
                    command_name = filter_.command_name
                    # 获取别名
                    if hasattr(filter_, 'alias') and filter_.alias:
                        if isinstance(filter_.alias, set):
                            aliases = list(filter_.alias)
                        elif isinstance(filter_.alias, list):
                            aliases = filter_.alias
                elif isinstance(filter_, CommandGroupFilter):
                    command_name = filter_.group_name
                elif isinstance(filter_, PermissionTypeFilter):
                    # 检查是否是管理员指令
                    is_admin_command = True
            
            # 如果找到了命令，添加到缓存
            if command_name:
                # 标准化命令名（不带前缀）
                if command_name.startswith("/"):
                    command_name = command_name[1:]
                
                handler_info = {
                    "command": command_name,
                    "description": description,
                    "plugin": plugin_name,
                    "aliases": aliases,
                    "is_admin": is_admin_command,
                    "handler": handler,
                    "module_path": handler.handler_module_path
                }
                
                self._handler_cache[command_name] = handler_info
                
                # 为别名建立索引
                for alias in aliases:
                    if alias.startswith("/"):
                        alias = alias[1:]
                    self._alias_to_command[alias] = command_name

    def _can_execute(self, command: str, event: AstrMessageEvent) -> tuple[bool, str]:
        """
        检查是否可以执行指令
        
        Args:
            command: 指令名（不含前缀）
            event: 消息事件
        
        Returns:
            (是否可执行, 原因)
        """
        # 检查插件是否启用
        if not self.enabled:
            return False, "LLM指令执行器已禁用"
        
        # 标准化命令名
        if command.startswith("/"):
            command = command[1:]
        
        # 解析别名
        actual_command = self._alias_to_command.get(command, command)
        
        # 检查指令是否存在
        if actual_command not in self._handler_cache:
            return False, f"未找到指令: {command}"
        
        handler_info = self._handler_cache[actual_command]
        
        # 检查白名单
        if self.whitelist:
            if actual_command not in self.whitelist and command not in self.whitelist:
                return False, f"指令 {command} 不在白名单中"
        
        # 检查黑名单
        if self.blacklist:
            if actual_command in self.blacklist or command in self.blacklist:
                return False, f"指令 {command} 在黑名单中"
        
        # 检查管理员指令权限
        if handler_info.get("is_admin", False):
            # 获取用户 ID
            user_id = str(event.get_sender_id())
            
            # 检查是否在管理员用户列表中
            if user_id in self.admin_users:
                return True, "可以执行（管理员用户）"
            
            # 检查全局 allow_admin_commands 配置
            if not self.allow_admin_commands:
                return False, f"指令 {command} 需要管理员权限，你不在管理员列表中"
        
        return True, "可以执行"

    def _get_plugin_instance(self, module_path: str) -> Optional[Star]:
        """
        获取处理器所属的插件实例
        
        Args:
            module_path: 处理器的模块路径
        
        Returns:
            插件实例或None
        """
        try:
            all_stars = self.context.get_all_stars()
            for star in all_stars:
                if getattr(star, "module_path", None) == module_path:
                    return star.star_cls
            return None
        except Exception as e:
            logger.error(f"获取插件实例失败: {e}")
            return None

    def _extract_content_from_result(self, result: Any) -> Dict[str, Any]:
        """
        从执行结果中提取内容（文本和图片）
        
        Args:
            result: 执行结果（可能是MessageEventResult或其他类型）
        
        Returns:
            包含 texts 和 images 的字典
        """
        texts = []
        images = []
        
        try:
            # 处理 MessageEventResult
            if hasattr(result, 'chain') and result.chain:
                for comp in result.chain:
                    # 处理纯文本
                    if hasattr(comp, 'text') and comp.text:
                        texts.append(str(comp.text))
                    # 处理 Plain 类型
                    elif hasattr(comp, 'type') and comp.type == 'Plain':
                        if hasattr(comp, 'text'):
                            texts.append(str(comp.text))
                    # 处理 Image 类型
                    elif isinstance(comp, Image) or (hasattr(comp, 'type') and comp.type == 'Image'):
                        if hasattr(comp, 'url') and comp.url:
                            images.append(str(comp.url))
                        elif hasattr(comp, 'file') and comp.file:
                            images.append(str(comp.file))
            # 处理字符串结果
            elif isinstance(result, str):
                texts.append(result)
            # 处理有 result_message 属性的对象
            elif hasattr(result, 'result_message') and result.result_message:
                texts.append(str(result.result_message))
        except Exception as e:
            logger.debug(f"提取内容时出错: {e}")
        
        return {"texts": texts, "images": images}

    def _build_message_components(self, command: str, args: str = "",
                                  at_qq_list: List[str] = None,
                                  reply_image_url: str = None) -> List:
        """
        构建消息组件列表，用于设置 event.message_obj
        
        支持两种 @ 位置模式：
        1. 如果 args 中包含占位符（如 @0, @1），则在对应位置插入 At 组件
        2. 否则，在指令后、参数前插入所有 At 组件（传统模式）
        
        Args:
            command: 指令名
            args: 指令参数，可以包含 @0, @1 等占位符指定 At 位置
            at_qq_list: 需要@的QQ号列表
            reply_image_url: 需要引用的图片URL
        
        Returns:
            消息组件列表
        """
        components = []
        
        # 如果有图片引用，添加 Reply 组件（包含图片）
        if reply_image_url:
            # 创建一个虚拟的 Reply 对象，包含图片
            # Image.fromURL() 是正确的构造方式，避免缺少 file 参数
            try:
                img_comp = Image.fromURL(reply_image_url)
            except (AttributeError, TypeError):
                # 回退：直接使用 file 参数传递 URL
                img_comp = Image(file=reply_image_url)
            reply_chain = [img_comp]
            reply_comp = Reply(id=0, sender_id=0, chain=reply_chain)
            components.append(reply_comp)
        
        # 构建消息内容
        if at_qq_list and args:
            # 检查 args 中是否包含占位符 @0, @1, @2 等
            has_placeholders = False
            for i in range(len(at_qq_list)):
                if f"@{i}" in args:
                    has_placeholders = True
                    break
            
            if has_placeholders:
                # 模式1: 使用占位符精确控制 @ 位置
                # 例如: args = "@0 100" 会在第一个位置插入 At 组件
                # 先添加指令
                components.append(Plain(text=f"/{command}"))
                
                # 按空格分割参数并逐个处理
                arg_parts = args.split()
                text_buffer = []  # 用于累积非占位符的文本
                
                for part in arg_parts:
                    # 检查是否是占位符
                    if part.startswith("@") and len(part) > 1 and part[1:].isdigit():
                        idx = int(part[1:])
                        if 0 <= idx < len(at_qq_list):
                            try:
                                # 先输出累积的文本（如果有）
                                if text_buffer:
                                    components.append(Plain(text=" " + " ".join(text_buffer)))
                                    text_buffer = []
                                # 添加 At 组件
                                components.append(At(qq=str(at_qq_list[idx])))
                            except Exception as e:
                                logger.warning(f"添加 At 组件失败 (QQ: {at_qq_list[idx]}): {e}")
                                text_buffer.append(part)  # 失败则当作普通文本
                        else:
                            text_buffer.append(part)
                    else:
                        text_buffer.append(part)
                
                # 添加剩余的文本
                if text_buffer:
                    components.append(Plain(text=" " + " ".join(text_buffer)))
            else:
                # 模式2: 传统模式 - 指令后紧跟所有 @ 组件，然后是参数
                components.append(Plain(text=f"/{command}"))
                for qq in at_qq_list:
                    try:
                        components.append(At(qq=str(qq)))
                    except Exception as e:
                        logger.warning(f"添加 At 组件失败 (QQ: {qq}): {e}")
                if args:
                    components.append(Plain(text=f" {args}"))
        else:
            # 没有 @ 或没有参数，简单构建
            command_text = f"/{command}"
            if args:
                command_text += f" {args}"
            components.append(Plain(text=command_text))
            
            # 添加 @ 组件（如果有）
            if at_qq_list:
                for qq in at_qq_list:
                    try:
                        components.append(At(qq=str(qq)))
                    except Exception as e:
                        logger.warning(f"添加 At 组件失败 (QQ: {qq}): {e}")
        
        return components

    @filter.llm_tool(name="execute_command")
    async def execute_command(self, event: AstrMessageEvent, **kwargs) -> str:
        """🎮 执行 指令
        
        当用户明确表达想要执行某个 功能 时，使用此工具来执行对应的指令。
        建议先使用 search_command 工具查找确认指令存在后再执行。
        
        【使用场景】
        - 用户说"帮我钓鱼" → execute_command(command="钓鱼")
        - 用户说"你也去钓鱼吧" → execute_command(command="钓鱼", as_bot=true)
        - 用户说"禁言张三60秒" → execute_command(command="禁言", args="60", at_qq_list=["123456789"])
        - 用户说"设置群头像为这张图" → execute_command(command="设置群头像", reply_image_url="http://...")
        
        【身份模式】
        - as_bot=false（默认）: 代理用户执行，使用用户的身份和账户
        - as_bot=true: Bot自己执行，使用Bot自己的身份和账户（Bot也会有自己的游戏账户）
        
        【特殊参数支持】
        - at_qq_list: 当指令需要@目标用户时使用（如禁言、踢人等）
        - reply_image_url: 当指令需要引用图片时使用（如设置群头像、裁剪图片等）
        
        【注意事项】
        - 指令名不需要带前缀（如 / 或 ~）
        - 如果指令需要参数，在 args 中传入
        - 某些管理员指令可能无法执行
        - LLM 可以通过其他工具获取群友的QQ号和昵称
        - 使用 as_bot=true 时，Bot会以自己的身份参与游戏（如钓鱼、签到等）
        
        Args:
            command(string): 要执行的指令名（不含前缀），如 "钓鱼"、"签到"、"背包"
            args(string): 指令参数，多个参数用空格分隔。可以使用 @0, @1 等占位符指定 at_qq_list 中对应用户的位置（可选）。例如 "@0 100" 表示第一个@用户后跟100
            at_qq_list(array[string]): 需要@的QQ号字符串列表（可选），如 ["123456789", "987654321"]
            reply_image_url(string): 需要引用的图片URL（可选）
            as_bot(boolean): 是否以Bot自己的身份执行指令（可选，默认false）。true=Bot自己执行，false=代理用户执行
        
        Returns:
            JSON 格式的执行结果，包含 success、command、result 或 error 字段
        """
        command = kwargs.get('command', '').strip()
        args = kwargs.get('args', '').strip()
        at_qq_list = kwargs.get('at_qq_list', [])
        reply_image_url = kwargs.get('reply_image_url', '').strip()
        as_bot = kwargs.get('as_bot', False)
        
        # 记录执行日志
        log_parts = [f"LLM请求执行指令: {command}"]
        if args:
            log_parts.append(f"参数: {args}")
        if at_qq_list:
            log_parts.append(f"@用户: {at_qq_list}")
        if reply_image_url:
            log_parts.append(f"引用图片: {reply_image_url}")
        if as_bot:
            log_parts.append(f"身份: Bot自己")
        else:
            log_parts.append(f"身份: 代理用户")
        logger.info(" | ".join(log_parts))
        
        # 参数检查
        if not command:
            return json.dumps({
                "success": False,
                "error": "缺少必需参数: command"
            }, ensure_ascii=False)
        
        # 刷新缓存（确保获取最新的处理器信息）
        if not self._handler_cache:
            self._build_handler_cache()
        
        # 1. 检查是否可以执行
        can_exec, reason = self._can_execute(command, event)
        if not can_exec:
            logger.warning(f"指令执行被拒绝: {command} - {reason}")
            return json.dumps({
                "success": False,
                "error": reason
            }, ensure_ascii=False)
        
        # 2. 标准化命令名并获取处理器信息
        if command.startswith("/"):
            command = command[1:]
        actual_command = self._alias_to_command.get(command, command)
        handler_info = self._handler_cache.get(actual_command)
        
        if not handler_info:
            return json.dumps({
                "success": False,
                "error": f"未找到指令: {command}"
            }, ensure_ascii=False)
        
        # 3. 获取插件实例
        plugin_instance = self._get_plugin_instance(handler_info['module_path'])
        if not plugin_instance:
            return json.dumps({
                "success": False,
                "error": f"无法获取指令 {command} 所属插件的实例"
            }, ensure_ascii=False)
        
        # 4. 执行处理器
        original_msg = event.message_str
        original_message_obj = getattr(event, 'message_obj', None)
        original_event = None
        
        try:
            handler: StarHandlerMetadata = handler_info['handler']
            
            # 如果as_bot=true，使用包装器替换事件对象
            if as_bot:
                # 保存原始事件对象
                original_event = event
                original_sender_id = event.get_sender_id()
                
                # 创建包装器，覆盖 get_sender_id() 方法
                event = BotIdentityEventWrapper(event, self.bot_user_id)
                logger.debug(f"已创建Bot身份包装器，原始ID: {original_sender_id}, Bot ID: {self.bot_user_id}")
            
            # 修改 event.message_str 以包含指令和参数
            # 使用 / 作为标准前缀
            if args:
                event.message_str = f"/{actual_command} {args}"
            else:
                event.message_str = f"/{actual_command}"
            
            # 如果有特殊参数，构建 message_obj
            if at_qq_list or reply_image_url:
                try:
                    # 构建消息组件
                    components = self._build_message_components(
                        actual_command,
                        args,
                        at_qq_list,
                        reply_image_url
                    )
                    
                    # 更新 message_obj 的 message 属性
                    if hasattr(event, 'message_obj') and hasattr(event.message_obj, 'message'):
                        event.message_obj.message = components
                        logger.debug(f"已构建特殊消息组件: At={len(at_qq_list) if at_qq_list else 0}, Image={bool(reply_image_url)}")
                    else:
                        logger.warning("无法修改 message_obj，可能不支持此操作")
                except Exception as e:
                    logger.error(f"构建消息组件失败: {e}")
            
            logger.debug(f"执行指令，消息设置为: {event.message_str}")
            
            # 执行并收集结果
            result_texts = []
            result_images = []
            results_to_send = []  # 收集所有结果用于合并转发判断
            
            try:
                # 调用处理器的 handler 方法
                # handler.handler 已经是绑定方法，不需要传入 plugin_instance
                async for result in handler.handler(event):
                    if result is not None:
                        results_to_send.append(result)
                        # 收集内容用于返回给 LLM
                        extracted = self._extract_content_from_result(result)
                        result_texts.extend(extracted["texts"])
                        result_images.extend(extracted["images"])
            except TypeError as e:
                # 某些处理器可能不是异步生成器
                logger.debug(f"处理器调用方式调整: {e}")
                result = await handler.handler(event)
                if result is not None:
                    results_to_send.append(result)
                    # 收集内容用于返回给 LLM
                    extracted = self._extract_content_from_result(result)
                    result_texts.extend(extracted["texts"])
                    result_images.extend(extracted["images"])
            
            # 判断是否需要使用合并转发
            total_text_length = sum(len(text) for text in result_texts)
            use_forward = (
                self.enable_forward
                and total_text_length > self.forward_threshold
                and event.get_platform_name() == "aiocqhttp"  # 只对 QQ 平台启用
            )
            
            if use_forward:
                # 使用合并转发发送
                logger.info(f"文本长度 {total_text_length} 超过阈值 {self.forward_threshold}，使用合并转发")
                try:
                    # 将所有结果合并到一个 Node 中
                    all_components = []
                    for result in results_to_send:
                        if hasattr(result, 'chain') and result.chain:
                            all_components.extend(result.chain)
                    
                    if all_components:
                        node = Node(
                            uin=event.get_self_id(),
                            name="AstrBot",
                            content=all_components
                        )
                        from astrbot.core.message.message_event_result import MessageEventResult
                        forward_result = MessageEventResult()
                        forward_result.chain = [node]
                        await event.send(forward_result)
                        logger.debug(f"已使用合并转发发送指令结果")
                except Exception as forward_err:
                    logger.error(f"合并转发失败，使用普通方式发送: {forward_err}")
                    # 失败则回退到普通发送
                    for result in results_to_send:
                        try:
                            await event.send(result)
                        except Exception as send_err:
                            logger.warning(f"发送结果失败: {send_err}")
            else:
                # 普通发送
                for result in results_to_send:
                    try:
                        await event.send(result)
                        logger.debug(f"已发送指令结果给用户")
                    except Exception as send_err:
                        logger.warning(f"发送结果失败: {send_err}")
            
            # 恢复原始消息和事件对象
            if as_bot and original_event is not None:
                # 如果使用了包装器，恢复原始事件对象
                event = original_event
                logger.debug(f"已恢复原始事件对象")
            
            event.message_str = original_msg
            if original_message_obj is not None:
                event.message_obj = original_message_obj
            
            # 构建返回结果
            response = {
                "success": True,
                "command": actual_command,
                "args": args if args else None
            }
            
            # 添加文本结果
            if result_texts:
                response["result"] = "\n".join(result_texts)
            
            # 添加图片URL（如果有）
            if result_images:
                response["images"] = result_images
                if not result_texts:
                    response["result"] = f"指令返回了 {len(result_images)} 张图片"
            
            # 如果什么都没有
            if not result_texts and not result_images:
                response["result"] = "指令执行完成（无输出内容）"
            
            # 添加执行身份标识
            if as_bot:
                response["executed_as"] = "bot"
            else:
                response["executed_as"] = "user"
            
            logger.info(f"指令执行成功: {command} (身份: {'Bot' if as_bot else '用户'}), 文本: {len(result_texts)}, 图片: {len(result_images)}")
            return json.dumps(response, ensure_ascii=False)
            
        except Exception as e:
            logger.error(f"执行指令 {command} 时发生错误: {e}", exc_info=True)
            
            # 尝试恢复原始消息和事件对象
            try:
                if as_bot and original_event is not None:
                    event = original_event
                event.message_str = original_msg
            except Exception:
                pass
            
            return json.dumps({
                "success": False,
                "command": actual_command,
                "error": f"执行失败: {str(e)}"
            }, ensure_ascii=False)

    @filter.llm_tool(name="list_executable_commands")
    async def list_executable_commands(self, event: AstrMessageEvent, **kwargs) -> str:
        """📋 列出可执行的指令
        
        获取当前可以通过 execute_command 执行的所有指令列表。
        
        【使用场景】
        - 用户问"你能帮我做什么" → 列出可执行的指令
        - 用户问"有哪些功能可以用" → 列出可执行的指令
        
        Args:
            category(string): 按插件名筛选（可选）
        
        Returns:
            JSON 格式的可执行指令列表
        """
        category = kwargs.get('category', '').strip()
        
        logger.info(f"LLM请求列出可执行指令，分类: {category or '全部'}")
        
        # 刷新缓存
        if not self._handler_cache:
            self._build_handler_cache()
        
        # 收集可执行的指令
        executable_commands = []
        
        for cmd_name, handler_info in self._handler_cache.items():
            # 检查是否可执行
            can_exec, _ = self._can_execute(cmd_name, event)
            if not can_exec:
                continue
            
            # 按分类筛选
            if category and category.lower() not in handler_info['plugin'].lower():
                continue
            
            executable_commands.append({
                "command": cmd_name,
                "description": handler_info['description'],
                "plugin": handler_info['plugin'],
                "aliases": handler_info['aliases']
            })
        
        # 按插件分组
        plugins_dict = {}
        for cmd in executable_commands:
            plugin = cmd['plugin']
            if plugin not in plugins_dict:
                plugins_dict[plugin] = []
            plugins_dict[plugin].append({
                "command": cmd['command'],
                "description": cmd['description'],
                "aliases": cmd['aliases']
            })
        
        return json.dumps({
            "success": True,
            "total_count": len(executable_commands),
            "plugins": plugins_dict
        }, ensure_ascii=False, indent=2)

    @filter.command("测试bot身份")
    async def test_bot_identity(self, event: AstrMessageEvent):
        """测试Bot身份切换功能 - 使用包装器方法"""
        original_id = event.get_sender_id()
        test_id = "test_bot_12345"
        
        try:
            # 使用包装器测试
            wrapped_event = BotIdentityEventWrapper(event, test_id)
            wrapped_id = wrapped_event.get_sender_id()
            
            # 测试包装器是否能正常访问其他属性
            can_access_message_str = hasattr(wrapped_event, 'message_str')
            can_access_send = hasattr(wrapped_event, 'send')
            
            result = f"""🔍 Bot身份测试结果（包装器方法）：
原始ID: {original_id}
测试ID: {test_id}
包装器返回的ID: {wrapped_id}
修改是否成功: {'✅ 是' if str(wrapped_id) == str(test_id) else '❌ 否'}

包装器功能测试:
- 可以访问 message_str: {'✅' if can_access_message_str else '❌'}
- 可以访问 send 方法: {'✅' if can_access_send else '❌'}

Bot配置的ID: {self.bot_user_id}

💡 新方法说明：
现在使用包装器来覆盖 get_sender_id() 方法，
而不是直接修改事件对象的属性。
这样可以确保无论事件对象内部如何实现，
都能正确返回Bot的ID。
"""
            yield event.plain_result(result)
        except Exception as e:
            yield event.plain_result(f"❌ 测试失败: {e}\n{type(e).__name__}: {str(e)}")
    
    @filter.command("刷新指令缓存", alias={"refresh_commands"})
    async def refresh_cache(self, event: AstrMessageEvent):
        """手动刷新指令处理器缓存"""
        self._build_handler_cache()
        yield event.plain_result(f"✅ 指令缓存已刷新，共缓存 {len(self._handler_cache)} 个指令")

    @filter.command("执行器状态", alias={"executor_status"})
    async def executor_status(self, event: AstrMessageEvent):
        """查看LLM指令执行器状态"""
        enabled_str = '✅ 已启用' if self.enabled else '❌ 已禁用'
        whitelist_str = ', '.join(self.whitelist) if self.whitelist else '无限制'
        blacklist_str = ', '.join(self.blacklist) if self.blacklist else '无'
        admin_str = '是' if self.allow_admin_commands else '否'
        admin_users_str = ', '.join(self.admin_users) if self.admin_users else '无'
        
        status_text = f"""=== LLM 指令执行器状态 ===
🔌 启用状态: {enabled_str}
📝 缓存指令数: {len(self._handler_cache)}
📋 白名单: {whitelist_str}
🚫 黑名单: {blacklist_str}
👑 允许管理员指令: {admin_str}
👤 管理员用户: {admin_users_str}

【可执行指令统计】"""
        
        # 统计各插件的指令数
        plugin_counts = {}
        for handler_info in self._handler_cache.values():
            plugin = handler_info['plugin']
            if plugin not in plugin_counts:
                plugin_counts[plugin] = 0
            plugin_counts[plugin] += 1
        
        for plugin, count in sorted(plugin_counts.items()):
            status_text += f"\n  • {plugin}: {count} 个指令"
        
        yield event.plain_result(status_text)

    async def terminate(self) -> None:
        """插件卸载时调用"""
        logger.info("LLM指令执行器插件已卸载")