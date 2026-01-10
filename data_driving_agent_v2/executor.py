# 执行器定义 V2
# 支持多线程 Context 和 4 种节点类型分发

from data_driving_schemas import (
    Context, NodeDefinition, ExecutionPlan, NodeType
)
from langchain_core.messages import HumanMessage, AIMessage, ToolMessage

from typing import Callable
import logging
logger = logging.getLogger(__name__)
class Executor:
    """
    数据驱动执行器 V2
    
    支持特性:
    - 多线程 Context 消息隔离
    - 4 种节点类型分发执行 (llm_auto, tool, query, planning)
    - data_out 机制: 子线程向父线程输出结果
    """
    

    def __init__(
        self,
        plan: ExecutionPlan,
        user_message: str,
        main_thread_id: str = "main",
        tools_map: dict[str, Callable] | None = None,
        default_tools_limit: int | None = 1,
        llm_factory: Callable[[], any] | None = None
    ):
        """
        初始化执行器

        Args:
            plan: 执行计划
            user_message: 用户消息
            main_thread_id: 主线程 ID
            tools_map: 工具映射 {tool_name: callable}
            default_tools_limit: 默认工具调用次数限制（每个工具的默认调用次数），None 表示无限制
            llm_factory: LLM 工厂函数，用于创建 LLM 实例。如果不提供，需要自行设置默认工厂
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
        if tools_map is None:
            tools_map = {}
            logger.warning("未提供工具映射")
        self.tools_map = tools_map

        # 默认工具使用限制（当节点未设置 tools_limit 时使用）
        self._default_tools_limit = default_tools_limit
        self.tools_usage_limit = {}
        
        # tokens 使用统计
        self.tokens_usage = {
            'input_tokens': 0,
            'output_tokens': 0,
            'total_tokens': 0
        }
        
        # 节点类型 -> 处理函数 映射
        self._node_handlers: dict[NodeType, Callable[[NodeDefinition], str]] = {
            "llm-first": self._execute_llm_first_node,
            "tool-first": self._execute_tool_first_node,
            "planning": self._execute_planning_node,
        }
        self.role_map = {
            "llm-first": "assistant",
            "tool-first": "tool",
            "planning": "assistant"
        }


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
        if node and node.tools:
            tools_to_limit.update(node.tools)

        # 应用默认限制到所有相关工具
        if self._default_tools_limit is not None:
            for tool in tools_to_limit:
                self.tools_usage_limit[tool] = self._default_tools_limit

        # 如果节点有单独的 tools_limit，覆盖默认值（优先级更高）
        if node and node.tools_limit:
            self.tools_usage_limit.update(node.tools_limit)
    
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
        """判断指定工具是否还能调用（未声明的工具默认有 DEFAULT_TOOL_USAGE_COUNT 次调用机会）"""
        return self.tools_usage_limit.get(tool_name, self._default_tools_limit) > 0
    
    def _consume_tool_usage(self, tool_name: str) -> None:
        """消耗一次工具调用次数（未声明的工具会被初始化后再消耗）"""
        if tool_name not in self.tools_usage_limit:
            # 未声明的工具，初始化为默认次数
            self.tools_usage_limit[tool_name] = self._default_tools_limit
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
    # 工具执行
    # =========================================================================
    def _execute_tool_call_for_thread(self, tool_call: dict, thread_id: str) -> tuple[bool, str | None]:
        """执行工具调用并将结果添加到指定线程"""
        tool_name = tool_call.get("name", "")
        tool_args = tool_call.get("args", {})
        tool_id = tool_call.get("id", "")
        
        if tool_name not in self.tools_map:
            error_msg = f"未知工具: {tool_name}，可用工具: {list(self.tools_map.keys())}"
            logger.info(f"    ✗ {error_msg}")
            return False, error_msg
        
        if not self._can_use_tool(tool_name):
            error_msg = f"工具 {tool_name} 调用次数已用完"
            logger.info(f"    ✗ {error_msg}")
            self._add_message_to_thread(thread_id, ToolMessage(content=error_msg, tool_call_id=tool_id))
            return False, error_msg
        
        logger.info(f"    - 执行工具: {tool_name}, args: {tool_args}")
        tool_result = self.tools_map[tool_name].invoke(tool_args)
        self._consume_tool_usage(tool_name)
        logger.info(f"    - 工具 {tool_name} 剩余调用次数: {self.tools_usage_limit[tool_name]}")
        
        self._add_message_to_thread(thread_id, ToolMessage(content=str(tool_result), tool_call_id=tool_id))
        return True, str(tool_result)

    # =========================================================================
    # 节点处理器
    # =========================================================================
    
    def _llm_tool_loop(self, node: NodeDefinition, llm) -> str:
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
            result = llm.invoke(messages)
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
                success, _ = self._execute_tool_call_for_thread(tool_call, node.thread_id)
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

    def _llm_single_call(self, node: NodeDefinition, llm) -> str:
        """
        单次 LLM 调用（可能包含一次工具调用）
        """
        prompt = self._get_prompt(node)
        print("="*20) 
        print(node.node_name)
        print(prompt)
        print("="*20)
        result = llm.invoke(prompt)
        self._accumulate_tokens(result)
        self._add_message_to_thread(node.thread_id, result)
        
        # 如果有 tool_calls，执行一次
        if hasattr(result, 'tool_calls') and result.tool_calls:
            for tool_call in result.tool_calls:
                self._execute_tool_call_for_thread(tool_call, node.thread_id)
        
        return result.content

    def _execute_llm_first_node(self, node: NodeDefinition) -> str:
        """
        LLM-First 节点执行器
        
        流程：LLM思考 -> [可选]调用工具 -> [可选]循环
        
        配置选项：
        - tools: 可用工具列表
        - enable_tool_loop: 是否启用工具调用循环
        """
        logger.info(f"执行节点 [llm-first]: {node.node_name}")
        
        # 验证工具
        if node.tools:
            self._validate_tools(node.tools)
            logger.info(f"    - 可用工具: {node.tools}")
            logger.info(f"    - 工具循环: {'启用' if node.enable_tool_loop else '禁用'}")
        
        # 创建 LLM（可能带工具）
        llm = self._create_llm_with_tools(node.tools)
        
        if node.enable_tool_loop and node.tools:
            # 启用循环：使用 messages 列表调用
            final_content = self._llm_tool_loop(node, llm)
        else:
            # 不启用循环：单次调用
            final_content = self._llm_single_call(node, llm)
        
        # 处理 data_out
        if node.data_out:
            self._set_data_out(node.thread_id, node.node_type, 
                              node.data_out_description, final_content)
        
        return final_content

    def _execute_tool_first_node(self, node: NodeDefinition) -> str:
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
        tool_result = self.tools_map[node.initial_tool_name].invoke(tool_args)
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
                final_content = self._llm_tool_loop(node, llm)
            else:
                # 单次调用
                final_content = self._llm_single_call(node, llm)
        
        # 处理 data_out
        if node.data_out:
            self._set_data_out(node.thread_id, node.node_type,
                              node.data_out_description, final_content)
        
        return final_content


    def _execute_planning_node(self, node: NodeDefinition) -> str:
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
    # 主执行方法
    # =========================================================================
    def execute(self) -> dict:
        """
        执行整个计划
        
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
        for node in self.plan.nodes:
            # 根据节点配置重置工具调用次数限制
            self.reset_tools_limit(node)

            # 确保线程存在
            if node.thread_id not in self.context["messages"]:
                self._create_thread(node.thread_id, node)
            
            # 使用处理器分发
            handler = self._node_handlers.get(node.node_type)
            if not handler:
                raise ValueError(f"未知节点类型: {node.node_type}")
            
            content = handler(node)
            print(content)
            # 如果节点设置了 data_out，根据 data_out_thread 合并到目标线程
            if node.data_out:
                # 目标线程由 data_out_thread 决定，若没有则默认为 main
                if not node.data_out_thread:
                    logger.warning(f"    ⚠️  data_out: 节点 '{node.node_name}' 没有指定 data_out_thread，使用默认的 main 线程")
                target_thread = node.data_out_thread if node.data_out_thread else self.main_thread_id
                self._merge_data_out(node.thread_id, target_thread)
        
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

# =============================================================================
# 测试代码
# =============================================================================
if __name__ == "__main__":
    # 创建测试计划 - 使用 llm_auto 和 query 节点
    #

    # 配置日志级别，方便调试
    import logging
    logging.basicConfig(
        level=logging.DEBUG,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    import os
    from load_plans import load_plan_from_template
    from langchain_core.tools import tool
    from langchain_openai import ChatOpenAI

    @tool
    def add(a,b):
        "加法"
        return a+b

    tools_map = {
        "add": add
    }

    # 创建 LLM 工厂函数
    def create_llm_factory():
        """创建 LLM 工厂函数"""
        api_key = os.getenv("DASHSCOPE_API_KEY") or os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("请设置环境变量 DASHSCOPE_API_KEY 或 OPENAI_API_KEY")

        return lambda: ChatOpenAI(
            model="qwen-plus-2025-12-01",
            openai_api_key=api_key,
            openai_api_base="https://dashscope.aliyuncs.com/compatible-mode/v1",
            temperature=0.7
        )

    # 获取当前脚本所在目录的绝对路径
    current_dir = os.path.dirname(os.path.abspath(__file__))
    # 构建 json 文件的绝对路径
    json_path = os.path.join(current_dir, "test_plan", "example", "example.json")
    plan, tools_limit = load_plan_from_template(json_path=json_path,
                                              pattern_name="custom")

    executor = Executor(
        plan,
        "请帮我总结 2026-01-03 的使用情况",
        tools_map=tools_map,
        default_tools_limit=1,
        llm_factory=create_llm_factory()
    )
    result = executor.execute()

    # 格式化输出
    print("\n" + "=" * 80)
    print("📊 AI 生成的行为总结")
    print("=" * 80 + "\n")
    print(result["content"])
    print("\n" + "=" * 80)
    print(f"📈 统计信息：共产生 {sum(len(msgs) for msgs in result['messages'].values())} 条消息")
    tokens = result["tokens_usage"]
    print(f"🔢 Tokens 使用: 输入={tokens['input_tokens']}, 输出={tokens['output_tokens']}, 总计={tokens['total_tokens']}")
    print("=" * 80)