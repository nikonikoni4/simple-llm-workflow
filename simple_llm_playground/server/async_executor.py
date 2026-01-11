# 异步执行器定义 V2
# 独立的异步版本，逻辑与同步版本 Executor 相同
# 业务扩展应继承此类

import asyncio
from datetime import datetime
from enum import Enum
from typing import Callable, Optional, Any, Coroutine
from pydantic import BaseModel

from .data_driving_schemas import (
    Context, NodeDefinition, ExecutionPlan, NodeType
)
from langchain_core.messages import HumanMessage, AIMessage, ToolMessage

import logging
logger = logging.getLogger(__name__)


# =============================================================================
# 执行状态定义
# =============================================================================
class NodeStatus(str, Enum):
    """节点执行状态"""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class NodeExecutionState(BaseModel):
    """节点执行状态记录"""
    node_id: int
    node_name: str
    status: NodeStatus = NodeStatus.PENDING
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    error: Optional[str] = None


class NodeContext(BaseModel):
    """节点上下文信息 - 用于前端展示"""
    node_id: int
    node_name: str
    thread_id: str
    thread_messages_before: list[dict] = []  # 执行前的线程消息
    thread_messages_after: list[dict] = []   # 执行后的线程消息
    llm_input: str = ""                       # LLM 输入 prompt
    llm_output: str = ""                      # LLM 输出
    tool_calls: list[dict] = []               # 工具调用记录
    data_out_content: Optional[str] = None    # 输出到父线程的内容


# =============================================================================
# 异步执行器
# =============================================================================
class AsyncExecutor:
    """
    异步数据驱动执行器 V2
    
    独立的异步实现，逻辑与同步版本 Executor 完全相同。
    业务扩展（如调试执行器）应继承此类。
    
    支持特性:
    - 多线程 Context 消息隔离
    - 4 种节点类型分发执行 (llm-first, tool-first, planning)
    - data_out 机制: 子线程向父线程输出结果
    - 执行状态追踪
    - 节点上下文收集
    """

    def __init__(
        self,
        plan: ExecutionPlan,
        user_message: str,
        main_thread_id: str = "main", # 主线程 ID
        tools_map: dict[str, Callable] | None = None, # 工具映射 {tool_name: callable}
        default_tools_limit: int | None = 1, # 默认工具调用次数限制（每个工具的默认调用次数），None 表示无限制
        llm_factory: Callable[..., Any] | None = None # LLM 工厂函数，用于创建 LLM 实例
    ):
        """
        初始化异步执行器

        Args:
            plan: 执行计划
            user_message: 用户消息
            main_thread_id: 主线程 ID
            tools_map: 工具映射 {tool_name: callable}
            default_tools_limit: 默认工具调用次数限制（每个工具的默认调用次数），None 表示无限制
            llm_factory: LLM 工厂函数，用于创建 LLM 实例
        """
        self.plan = plan
        self.main_thread_id = main_thread_id
        self.llm_factory = llm_factory

        # 新的多线程 Context 结构
        self.context: Context = {
            "messages": {
                main_thread_id: [HumanMessage(content=user_message)]
            },
            "data_out": {},
        }

        # 工具映射
        self.tools_map = tools_map or {}

        # 默认工具使用限制（当节点未设置 tools_limit 时使用）
        if default_tools_limit:
            self._default_tools_limit = default_tools_limit
        else:
            self._default_tools_limit = 1
        
        self.tools_usage_limit = {}
        
        # tokens 使用统计
        self.tokens_usage = {
            'input_tokens': 0,
            'output_tokens': 0,
            'total_tokens': 0
        }
        
        # 节点类型 -> 处理函数 映射
        self._node_handlers: dict[NodeType, Callable[[NodeDefinition], Coroutine[Any, Any, str]]] = {
            "llm-first": self._execute_llm_first_node,
            "tool-first": self._execute_tool_first_node,
            "planning": self._execute_planning_node,
        }
        self.role_map = {
            "llm-first": "assistant",
            "tool-first": "tool",
            "planning": "assistant"
        }
        
        # ===== 状态追踪（新增） =====
        self.node_states: dict[int, NodeExecutionState] = {}
        self.node_contexts: dict[int, NodeContext] = {}
        self._current_node_index = 0  # 当前执行到的节点索引
        
        # 初始化所有节点状态
        self._init_node_states()

    def _init_node_states(self):
        """初始化所有节点的状态为 PENDING"""
        for i, node in enumerate(self.plan.nodes):
            node_id = i + 1  # 假设节点 ID 从 1 开始
            self.node_states[node_id] = NodeExecutionState(
                node_id=node_id,
                node_name=node.node_name,
                status=NodeStatus.PENDING
            )
    
    # =========================================================================
    # Context 辅助方法
    # =========================================================================
    def _get_thread_messages(self, thread_id: str) -> list:
        """获取指定线程的消息列表"""
        return self.context["messages"].get(thread_id, [])

    def _add_message_to_thread(self, thread_id: str, message) -> None:
        """添加消息到指定线程"""
        if thread_id not in self.context["messages"]:
            raise ValueError(f"线程 {thread_id} 不存在")
        self.context["messages"][thread_id].append(message)

    def _create_thread(self, thread_id: str, node: NodeDefinition | None = None) -> None:
        """
        创建新线程，并根据 node 的 data_in 配置注入初始消息
        
        Args:
            thread_id: 新线程ID
            node: 节点定义，用于获取 data_in 配置
        """
        if thread_id in self.context["messages"]:
            return  # 线程已存在，直接返回
        
        self.context["messages"][thread_id] = []
        # 处理 data_in：注入初始消息到新线程
        if node is not None:
            # 确定数据来源线程：优先使用 data_in_thread，否则默认为 main
            source_thread = node.data_in_thread or self.main_thread_id
            if not node.data_in_thread:
                logger.warning(f"    ⚠️  data_in: 节点 '{node.node_name}' 没有指定 data_in_thread，使用默认的 main 线程")
            if source_thread and source_thread in self.context["messages"]:
                source_msgs = self.context["messages"][source_thread]
                
                # 检查源线程是否有数据
                if source_msgs:
                    if node.data_in_slice:
                        # 使用指定的切片范围
                        start, end = node.data_in_slice
                        injected = source_msgs[start:end]
                    else:
                        # 默认：取最后一条消息
                        injected = [source_msgs[-1]]
                    
                    # 注入消息到新线程
                    if injected:
                        self.context["messages"][thread_id].extend(injected)
                        logger.debug(f"    → data_in: 从 '{source_thread}' 注入 {len(injected)} 条消息到 '{thread_id}'")

    def _set_data_out(self, thread_id: str, node_type: str, description: str, content: str) -> None:
        """设置线程的输出数据"""
        self.context["data_out"][thread_id] = {
            "role": self.role_map[node_type],
            "content": f"{description}{content}" if description else content
        }

    def _merge_data_out(self, child_thread_id: str, target_thread_id: str) -> None:
        """
        将子线程的 data_out 合并到目标线程的 messages
        
        Args:
            child_thread_id: 子线程ID（数据来源）
            target_thread_id: 目标线程ID（由节点的 data_out_thread 决定）
        """
        if child_thread_id not in self.context["data_out"]:
            return
        
        if target_thread_id and target_thread_id in self.context["messages"]:
            data = self.context["data_out"][child_thread_id]
            self._add_message_to_thread(target_thread_id, AIMessage(content=data["content"]))
            logger.debug(f"    → data_out: 从 '{child_thread_id}' 合并到 '{target_thread_id}'")

    # =========================================================================
    # 工具管理方法
    # =========================================================================
    def reset_tools_limit(self, node: NodeDefinition | None = None):
        """
        重置工具调用次数限制

        Args:
            node: 当前执行的节点。如果节点设置了 tools_limit，则与默认限制合并；
                  节点的限制优先级高于默认限制。
        """
        self.tools_usage_limit = {}

        # 获取当前节点使用的工具列表
        tools_to_limit = set()
        initial_tool = None
        if node and node.tools:
            tools_to_limit.update(node.tools)
        # 对于 tool-first 节点，需要包含初始工具（额外+1配额，因为初始调用不应占用LLM限额）
        if node and node.node_type == "tool-first" and node.initial_tool_name:
            initial_tool = node.initial_tool_name
            tools_to_limit.add(initial_tool)

        # 应用默认限制到所有相关工具
        if self._default_tools_limit is not None:
            for tool in tools_to_limit:
                self.tools_usage_limit[tool] = self._default_tools_limit
            # tool-first 的初始工具额外+1（初始调用不计入LLM限额）
            if initial_tool:
                self.tools_usage_limit[initial_tool] += 1

        # 如果节点有单独的 tools_limit，覆盖默认值（优先级更高）
        node_tools_limit = getattr(node, 'tools_limit', None) if node else None
        if node_tools_limit:
            self.tools_usage_limit.update(node_tools_limit)
    
    def reset_tokens_usage(self):
        """重置 tokens 使用统计"""
        self.tokens_usage = {
            'input_tokens': 0,
            'output_tokens': 0,
            'total_tokens': 0
        }
    
    def _accumulate_tokens(self, result) -> None:
        """累加 tokens 使用量"""
        if not result:
            logger.debug("    ⚠️  _accumulate_tokens: result 为空，跳过统计")
            return

        tokens_added = False

        # 尝试从 response_metadata 获取 token usage
        if hasattr(result, 'response_metadata') and 'token_usage' in result.response_metadata:
            token_usage = result.response_metadata['token_usage']
            input_tokens = token_usage.get('input_tokens', 0)
            output_tokens = token_usage.get('output_tokens', 0)
            total_tokens = token_usage.get('total_tokens', 0)

            self.tokens_usage['input_tokens'] += input_tokens
            self.tokens_usage['output_tokens'] += output_tokens
            self.tokens_usage['total_tokens'] += total_tokens
            tokens_added = True
            logger.debug(f"    📊 Token 统计 (response_metadata): input={input_tokens}, output={output_tokens}, total={total_tokens}")

        # 尝试直接从 result 获取 token usage（某些 LLM 实现）
        elif hasattr(result, 'token_usage'):
            token_usage = result.token_usage
            input_tokens = token_usage.get('input_tokens', 0)
            output_tokens = token_usage.get('output_tokens', 0)
            total_tokens = token_usage.get('total_tokens', 0)

            self.tokens_usage['input_tokens'] += input_tokens
            self.tokens_usage['output_tokens'] += output_tokens
            self.tokens_usage['total_tokens'] += total_tokens
            tokens_added = True
            logger.debug(f"    📊 Token 统计 (token_usage): input={input_tokens}, output={output_tokens}, total={total_tokens}")

        # 尝试从 usage_metadata 获取（OpenAI 新版格式）
        elif hasattr(result, 'usage_metadata'):
            usage = result.usage_metadata
            input_tokens = usage.get('input_tokens', 0)
            output_tokens = usage.get('output_tokens', 0)
            total_tokens = usage.get('total_tokens', 0)

            self.tokens_usage['input_tokens'] += input_tokens
            self.tokens_usage['output_tokens'] += output_tokens
            self.tokens_usage['total_tokens'] += total_tokens
            tokens_added = True
            logger.debug(f"    📊 Token 统计 (usage_metadata): input={input_tokens}, output={output_tokens}, total={total_tokens}")

        if not tokens_added:
            logger.warning(f"    ⚠️  无法从 LLM 响应中获取 token 统计信息")
            logger.debug(f"    📋 result 类型: {type(result)}, 属性: {dir(result)}")

    def _validate_tools(self, tools: list[str] | None):
        """验证工具是否存在"""
        if not tools:
            return
        for tool in tools:
            if tool not in self.tools_map:
                raise ValueError(f"工具 {tool} 不存在，可用工具: {list(self.tools_map.keys())}")

    def _can_use_tool(self, tool_name: str) -> bool:
        """判断指定工具是否还能调用（未声明的工具默认有默认调用次数）"""

        return self.tools_usage_limit.get(tool_name, self._default_tools_limit) > 0
   
    
    def _consume_tool_usage(self, tool_name: str) -> None:
        """消耗一次工具调用次数"""
        if tool_name in self.tools_usage_limit:
            self.tools_usage_limit[tool_name] -= 1

    def _has_available_tools(self, tools: list[str] | None) -> bool:
        """检查是否还有可用的工具调用次数"""
        if not tools:
            return False
        return any(self._can_use_tool(tool) for tool in tools)

    def _tools_limit_prompt(self, tools: list[str] | None) -> str:
        """生成工具调用次数限制的 prompt"""
        if not tools:
            return ""
        lines = []
        for tool in tools:
            remaining = self.tools_usage_limit.get(tool, 0)
            lines.append(f"工具 {tool} 可以调用 {remaining} 次")
        return "\n".join(lines)

    def _create_llm_with_tools(self, tools: list[str] | None):
        """创建 LLM，如果有工具则绑定"""
        if self.llm_factory is None:
            raise ValueError("必须提供 llm_factory 来创建 LLM 实例")
        
        llm = self.llm_factory()
        if tools:
            tool_objects = [self.tools_map[t] for t in tools]
            llm = llm.bind_tools(tool_objects)
        return llm

    # =========================================================================
    # Prompt 构建
    # =========================================================================
    def get_history(self, thread_id: str) -> str:
        """返回指定线程的格式化历史消息字符串"""
        result = []
        messages = self._get_thread_messages(thread_id)
        for message in messages:
            if isinstance(message, HumanMessage):
                result.append(f"user: {message.content}")
            elif isinstance(message, ToolMessage):
                result.append(f"tool: {message.content}")
            elif isinstance(message, AIMessage):
                # 如果有 tool_calls，需要格式化输出
                if hasattr(message, 'tool_calls') and message.tool_calls:
                    tool_calls_str = ", ".join([
                        f"{tc.get('name', 'unknown')}({tc.get('args', {})})" 
                        for tc in message.tool_calls
                    ])
                    result.append(f"assistant: [调用工具: {tool_calls_str}]")
                    if message.content:
                        result.append(f"assistant: {message.content}")
                else:
                    result.append(f"assistant: {message.content}")
        return "\n".join(result) if result else ""

    def _get_prompt(self, node: NodeDefinition) -> str:
        """构建节点的 prompt"""
        return f"""
# 历史消息
{self.get_history(node.thread_id)}
# 你需要按照下面要求完成任务：
{node.task_prompt}
"""

    # =========================================================================
    # 消息序列化辅助
    # =========================================================================
    def _serialize_messages(self, messages: list) -> list[dict]:
        """将消息列表序列化为字典列表，用于前端展示"""
        result = []
        for msg in messages:
            if isinstance(msg, HumanMessage):
                result.append({"role": "user", "content": msg.content})
            elif isinstance(msg, AIMessage):
                item = {"role": "assistant", "content": msg.content}
                if hasattr(msg, 'tool_calls') and msg.tool_calls:
                    item["tool_calls"] = msg.tool_calls
                result.append(item)
            elif isinstance(msg, ToolMessage):
                result.append({
                    "role": "tool",
                    "content": msg.content,
                    "tool_call_id": msg.tool_call_id
                })
        return result

    # =========================================================================
    # 工具执行（异步）
    # =========================================================================
    async def _execute_tool_call_for_thread(self, tool_call: dict, thread_id: str) -> tuple[bool, str | None]:
        """执行工具调用并将结果添加到指定线程"""
        tool_name = tool_call.get("name", "")
        tool_args = tool_call.get("args", {})
        tool_id = tool_call.get("id", "")
        
        if tool_name not in self.tools_map:
            error_msg = f"未知工具: {tool_name}，可用工具: {list(self.tools_map.keys())}"
            logger.info(f"    ✗ {error_msg}")
            return False, error_msg
        
        if not self._can_use_tool(tool_name):
            error_msg = f"error 工具 {tool_name} 调用次数已用完"
            logger.info(f"    ✗ {error_msg}")
            self._add_message_to_thread(thread_id, ToolMessage(content=error_msg, tool_call_id=tool_id))
            return False, error_msg
        
        logger.info(f"    - 执行工具: {tool_name}, args: {tool_args}")
        
        # 异步执行工具（如果工具是 coroutine，使用 await，否则用 run_in_executor）
        tool_func = self.tools_map[tool_name]
        if asyncio.iscoroutinefunction(tool_func.invoke if hasattr(tool_func, 'invoke') else tool_func):
            tool_result = await tool_func.invoke(tool_args)
        else:
            # 同步工具在线程池中执行，避免阻塞
            loop = asyncio.get_event_loop()
            tool_result = await loop.run_in_executor(None, lambda: tool_func.invoke(tool_args))
        
        self._consume_tool_usage(tool_name)
        logger.info(f"    - 工具 {tool_name} 剩余调用次数: {self.tools_usage_limit[tool_name]}")
        
        self._add_message_to_thread(thread_id, ToolMessage(content=str(tool_result), tool_call_id=tool_id))
        return True, str(tool_result)

    # =========================================================================
    # 节点处理器（异步）
    # =========================================================================
    
    async def _llm_tool_loop(self, node: NodeDefinition, llm) -> str:
        """
        LLM 工具调用循环
        
        使用 messages 列表调用 LLM，支持多轮工具调用直到 LLM 返回最终结果
        """
        # 添加任务 prompt 到线程
        tools_limit_prompt = self._tools_limit_prompt(node.tools)
        initial_task_prompt = f"""工具可调用次数限制，请合理安排工具调用:
{tools_limit_prompt}
你需要按照下面要求完成任务：
{node.task_prompt}"""
        self._add_message_to_thread(node.thread_id, HumanMessage(content=initial_task_prompt))
        
        result = None
        round_count = 0
        while True:
            round_count += 1
            logger.debug(f"[DEBUG] 第 {round_count} 轮循环")
            
            messages = self._get_thread_messages(node.thread_id)
            
            # 异步调用 LLM
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(None, lambda: llm.invoke(messages))
            
            self._accumulate_tokens(result)
            self._add_message_to_thread(node.thread_id, result)
            
            # 无 tool_calls，结束
            if not (hasattr(result, 'tool_calls') and result.tool_calls):
                logger.debug(f"    → LLM 返回最终结果（无 tool_calls）")
                break
            
            # 执行工具
            logger.debug(f"    → LLM 请求调用 {len(result.tool_calls)} 个工具")
            executed = 0
            for tool_call in result.tool_calls:
                success, _ = await self._execute_tool_call_for_thread(tool_call, node.thread_id)
                if success:
                    executed += 1
            
            # 无成功执行或工具用完，结束
            if executed == 0:
                logger.debug(f"    → 本轮没有成功执行任何工具")
                break
            if not self._has_available_tools(node.tools):
                logger.debug(f"    → 所有工具调用次数已用完")
                break
        
        logger.debug(f"[DEBUG] 工具循环完成，共 {round_count} 轮")
        return result.content if result else ""

    async def _llm_single_call(self, node: NodeDefinition, llm) -> str:
        """
        单次 LLM 调用（可能包含一次工具调用）
        """
        prompt = self._get_prompt(node)
        
        # 异步调用 LLM
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(None, lambda: llm.invoke(prompt))
        
        self._accumulate_tokens(result)
        self._add_message_to_thread(node.thread_id, result)
        
        # 如果有 tool_calls，执行一次
        if hasattr(result, 'tool_calls') and result.tool_calls:
            for tool_call in result.tool_calls:
                await self._execute_tool_call_for_thread(tool_call, node.thread_id)
        
        return result.content

    async def _execute_llm_first_node(self, node: NodeDefinition) -> str:
        """
        LLM-First 节点执行器

        流程：LLM思考 -> [可选]调用工具 -> [可选]循环

        配置选项：
        - tools: 可用工具列表
        - enable_tool_loop: 是否启用工具调用循环
        - task_prompt: 为空时跳过 LLM 执行，仅作为数据中转节点
        """
        logger.info(f"执行节点 [llm-first]: {node.node_name}")

        # 如果 task_prompt 为空，跳过 LLM 执行（数据中转节点）
        if not node.task_prompt or node.task_prompt.strip() == "":
            logger.info(f"    - task_prompt 为空，跳过 LLM 执行（数据中转节点）")
            # 处理 data_out��空内容）
            if node.data_out:
                self._set_data_out(node.thread_id, node.node_type,
                                  node.data_out_description, "")
            return ""

        # 验证工具
        if node.tools:
            self._validate_tools(node.tools)
            logger.info(f"    - 可用工具: {node.tools}")
            logger.info(f"    - 工具循环: {'启用' if node.enable_tool_loop else '禁用'}")
        
        # 创建 LLM（可能带工具）
        llm = self._create_llm_with_tools(node.tools)
        
        if node.enable_tool_loop and node.tools:
            # 启用循环：使用 messages 列表调用
            final_content = await self._llm_tool_loop(node, llm)
        else:
            # 不启用循环：单次调用
            final_content = await self._llm_single_call(node, llm)
        
        # 处理 data_out
        if node.data_out:
            self._set_data_out(node.thread_id, node.node_type, 
                              node.data_out_description, final_content)
        
        return final_content

    async def _execute_tool_first_node(self, node: NodeDefinition) -> str:
        """
        Tool-First 节点执行器
        
        流程：执行初始工具 -> [可选]LLM分析 -> [可选]调用更多工具 -> [可选]循环
        
        配置选项：
        - initial_tool_name: 初始工具名称（必需）
        - initial_tool_args: 初始工具参数
        - task_prompt: LLM 任务描述（为空时只返回工具结果）
        - tools: 后续可用工具列表
        - enable_tool_loop: 是否启用工具调用循环
        """
        logger.info(f"执行节点 [tool-first]: {node.node_name}")
        
        # 验证初始工具配置
        if not node.initial_tool_name:
            raise ValueError(f"tool-first 节点 {node.node_name} 必须指定 initial_tool_name")
        if node.initial_tool_name not in self.tools_map:
            raise ValueError(f"工具 {node.initial_tool_name} 不存在")
        
        # 检查初始工具调用限制
        if not self._can_use_tool(node.initial_tool_name):
            error_msg = f"工具 {node.initial_tool_name} 调用次数已用完"
            logger.info(f"    ✗ {error_msg}")
            self._add_message_to_thread(node.thread_id,
                ToolMessage(content=error_msg, tool_call_id="initial_tool"))
            return error_msg
        
        # 执行初始工具
        tool_args = node.initial_tool_args or {}
        logger.info(f"    - 执行初始工具: {node.initial_tool_name}")
        logger.info(f"    - 工具参数: {tool_args}")
        
        # 异步执行初始工具
        tool_func = self.tools_map[node.initial_tool_name]
        loop = asyncio.get_event_loop()
        if asyncio.iscoroutinefunction(tool_func.invoke if hasattr(tool_func, 'invoke') else tool_func):
            tool_result = await tool_func.invoke(tool_args)
        else:
            tool_result = await loop.run_in_executor(None, lambda: tool_func.invoke(tool_args))
        
        self._consume_tool_usage(node.initial_tool_name)
        logger.info(f"    - 工具 {node.initial_tool_name} 剩余调用次数: {self.tools_usage_limit[node.initial_tool_name]}")
        
        # 添加工具结果到上下文
        self._add_message_to_thread(node.thread_id,
            ToolMessage(content=str(tool_result), tool_call_id="initial_tool"))
        
        # 如果没有 task_prompt，直接返回工具结果
        if not node.task_prompt:
            final_content = str(tool_result)
        else:
            # 验证额外工具
            if node.tools:
                self._validate_tools(node.tools)
                logger.info(f"    - 后续可用工具: {node.tools}")
                logger.info(f"    - 工具循环: {'启用' if node.enable_tool_loop else '禁用'}")
            
            # 创建 LLM（可能带额外工具）
            llm = self._create_llm_with_tools(node.tools)
            
            if node.enable_tool_loop and node.tools:
                # 启用循环
                final_content = await self._llm_tool_loop(node, llm)
            else:
                # 单次调用
                final_content = await self._llm_single_call(node, llm)
        
        # 处理 data_out
        if node.data_out:
            self._set_data_out(node.thread_id, node.node_type,
                              node.data_out_description, final_content)
        
        return final_content


    async def _execute_planning_node(self, node: NodeDefinition) -> str:
        """
        规划节点（暂未实现）
        
        TODO: 后续迭代实现
        - 调用 LLM 生成子计划 (使用 SubExecutorPlan schema)
        - 创建子线程
        - 递归执行子计划
        - 结果合并
        """
        raise NotImplementedError(
            f"planning 节点 {node.node_name} 尚未实现，请在后续迭代中添加支持"
        )

    # =========================================================================
    # 主执行方法（异步）
    # =========================================================================
    async def execute(self) -> dict:
        """
        异步执行整个计划
        
        Returns:
            dict: 包含执行结果的字典
                - content: 最终输出内容
                - messages: 所有消息（按 thread_id 组织）
                - tokens_usage: tokens 使用量统计
                - data_out: 各线程的输出数据
        """
        logger.info(f"\n开始执行计划: {self.plan.task}\n")

        # 重置工具调用次数和 tokens 统计
        self.reset_tools_limit()
        self.reset_tokens_usage()

        content = None
        for i, node in enumerate(self.plan.nodes):
            node_id = i + 1
            # 根据节点配置重置工具调用次数限制
            self.reset_tools_limit(node)
            await self._execute_single_node(node, node_id)
            content = self.node_contexts.get(node_id, NodeContext(node_id=node_id, node_name=node.node_name, thread_id=node.thread_id)).llm_output
        
        logger.info(f"\n计划执行完成！")
        logger.info(f"📊 Tokens 使用统计:")
        logger.info(f"   - 输入 tokens: {self.tokens_usage['input_tokens']}")
        logger.info(f"   - 输出 tokens: {self.tokens_usage['output_tokens']}")
        logger.info(f"   - 总计 tokens: {self.tokens_usage['total_tokens']}\n")
        
        return {
            "content": content,
            "messages": self.context["messages"],
            "tokens_usage": self.tokens_usage,
            "data_out": self.context["data_out"]
        }

    async def _execute_single_node(self, node: NodeDefinition, node_id: int) -> str:
        """
        执行单个节点（内部方法）
        
        Args:
            node: 节点定义
            node_id: 节点 ID
            
        Returns:
            节点执行结果
        """
        # 更新状态为 RUNNING
        self.node_states[node_id].status = NodeStatus.RUNNING
        self.node_states[node_id].start_time = datetime.now()
        
        # 记录执行前的线程消息
        messages_before = self._serialize_messages(
            self._get_thread_messages(node.thread_id)
        )
        
        try:
            # 确保线程存在
            if node.thread_id not in self.context["messages"]:
                self._create_thread(node.thread_id, node)
            
            # 使用处理器分发
            handler = self._node_handlers.get(node.node_type)
            if not handler:
                raise ValueError(f"未知节点类型: {node.node_type}")
            
            # 记录 LLM 输入
            llm_input = self._get_prompt(node)
            
            # 执行节点
            content = await handler(node)
            
            # 如果节点设置了 data_out，根据 data_out_thread 合并到目标线程
            if node.data_out:
                # 目标线程由 data_out_thread 决定，若没有则默认为 main
                if not node.data_out_thread:
                    logger.warning(f"    ⚠️  data_out: 节点 '{node.node_name}' 没有指定 data_out_thread，使用默认的 main 线程")
                target_thread = node.data_out_thread if node.data_out_thread else self.main_thread_id
                self._merge_data_out(node.thread_id, target_thread)
            
            # 记录执行后的线程消息
            messages_after = self._serialize_messages(
                self._get_thread_messages(node.thread_id)
            )
            
            # 保存节点上下文
            self.node_contexts[node_id] = NodeContext(
                node_id=node_id,
                node_name=node.node_name,
                thread_id=node.thread_id,
                thread_messages_before=messages_before,
                thread_messages_after=messages_after,
                llm_input=llm_input,
                llm_output=content,
                tool_calls=[],  # TODO: 收集工具调用记录
                data_out_content=self.context["data_out"].get(node.thread_id, {}).get("content") if node.data_out else None
            )
            
            # 更新状态为 COMPLETED
            self.node_states[node_id].status = NodeStatus.COMPLETED
            self.node_states[node_id].end_time = datetime.now()
            
            self._current_node_index = node_id
            
            return content
            
        except Exception as e:
            # 更新状态为 FAILED
            self.node_states[node_id].status = NodeStatus.FAILED
            self.node_states[node_id].end_time = datetime.now()
            self.node_states[node_id].error = str(e)
            logger.error(f"节点 {node.node_name} 执行失败: {e}")
            raise

    async def execute_step(self) -> Optional[NodeContext]:
        """
        单步执行：执行下一个待执行的节点
        
        Returns:
            NodeContext: 执行完成的节点上下文，如果没有更多节点则返回 None
        """
        # 找到下一个待执行的节点
        next_node_id = self._current_node_index + 1
        
        if next_node_id > len(self.plan.nodes):
            logger.info("所有节点已执行完成")
            return None
        
        # 第一次执行时初始化
        if self._current_node_index == 0:
            self.reset_tokens_usage()

        node = self.plan.nodes[next_node_id - 1]
        # 根据节点配置重置工具调用次数限制
        self.reset_tools_limit(node)
        await self._execute_single_node(node, next_node_id)
        
        return self.node_contexts.get(next_node_id)

    def get_node_context(self, node_id: int) -> Optional[NodeContext]:
        """获取指定节点的上下文信息"""
        return self.node_contexts.get(node_id)

    def get_all_node_states(self) -> list[NodeExecutionState]:
        """获取所有节点的执行状态"""
        return list(self.node_states.values())

    def get_execution_progress(self) -> dict:
        """获取执行进度"""
        total = len(self.plan.nodes)
        completed = sum(1 for s in self.node_states.values() if s.status == NodeStatus.COMPLETED)
        failed = sum(1 for s in self.node_states.values() if s.status == NodeStatus.FAILED)
        running = sum(1 for s in self.node_states.values() if s.status == NodeStatus.RUNNING)
        
        return {
            "total": total,
            "completed": completed,
            "failed": failed,
            "running": running,
            "pending": total - completed - failed - running,
            "progress_percent": (completed / total * 100) if total > 0 else 0
        }
