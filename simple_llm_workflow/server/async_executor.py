# 异步执行器定义 V2
# 独立的异步版本，逻辑与同步版本 Executor 相同
# 业务扩展应继承此类
import copy
from datetime import datetime
from typing import Callable, Optional, Any
from llm_linear_executor.executor import Executor 
from simple_llm_workflow.schemas import (
    NodeDefinition, ExecutionPlan,NodeStatus,NodeContext,NodeStatus,NodeExecutionState
)
from langchain_core.messages import HumanMessage, AIMessage, ToolMessage

import logging
logger = logging.getLogger(__name__)
 


# =============================================================================
# 异步执行器
# =============================================================================
class AsyncExecutor(Executor):
    """
    异步数据驱动执行器 V2
    
    继承自 llm_linear_executor.Executor，添加了执行状态追踪和 execute_step 支持。
    """

    def __init__(
        self,
        plan: ExecutionPlan,
        tools_map: dict[str, Callable] | None = None, # 工具映射 {tool_name: callable}
        default_tools_limit: int | None = 1, # 默认工具调用次数限制（每个工具的默认调用次数），None 表示无限制
        llm_factory: Callable[..., Any] | None = None # LLM 工厂函数，用于创建 LLM 实例
    ):
        """
        初始化异步执行器

        Args:
            plan: 执行计划
            tools_map: 工具映射 {tool_name: callable}
            default_tools_limit: 默认工具调用次数限制（每个工具的默认调用次数），None 表示无限制
            llm_factory: LLM 工厂函数，用于创建 LLM 实例
        """
        # 调用父类初始化
        # 注意：父类 __init__ 签名是 (plan, tools_map, default_tools_limit, llm_factory)
        super().__init__(
            plan=plan,
            tools_map=tools_map,
            default_tools_limit=default_tools_limit,
            llm_factory=llm_factory
        )
        
        # ===== 状态追踪（扩展） =====
        self.node_states: dict[int, NodeExecutionState] = {}
        self.node_contexts: dict[int, NodeContext] = {}
        self._current_node_index = 0  # 当前执行到的节点索引
        
        # 上下文历史快照，记录每个节点执行前的 context
        # 用于支持节点重新执行时恢复上下文
        self.context_history: dict[int, dict] = {}  # {node_id: deepcopy(self.context)}
        
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
    # 主执行方法（异步）- 覆盖父类 execute (同步)
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
        
        # 逐个执行节点，这里的逻辑与父类 aexecute 类似，但增加了状态更新
        for i, node in enumerate(self.plan.nodes):
            node_id = i + 1
            # 根据节点配置重置工具调用次数限制
            self.reset_tools_limit(node)
            await self._execute_single_node(node, node_id)
            context = self.node_contexts.get(node_id)
            if context:
                content = context.llm_output
        
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
        # 保存执行前的上下文快照（用于支持重新执行）
        self.context_history[node_id] = copy.deepcopy(self.context)
        
        # 更新状态为 RUNNING
        self.node_states[node_id].status = NodeStatus.RUNNING
        self.node_states[node_id].start_time = datetime.now()
        
        try:
            # 确保线程存在（必须先创建线程，才能记录消息）
            if node.thread_id not in self.context["messages"]:
                self._create_thread(node.thread_id, node)
            
            # 记录执行前的线程消息（在线程确保存在后获取）
            messages_before = self._serialize_messages(
                self._get_thread_messages(node.thread_id)
            )
            
            # 使用处理器分发 (父类的方法)
            handler = self._node_handlers.get(node.node_type)
            if not handler:
                raise ValueError(f"未知节点类型: {node.node_type}")
            
            

            # 执行节点 (使用 await，兼容父类的异步 handler)
            # 对于 tool-first 节点，工具调用发生在 handler 内部
            content = await handler(node)
            # LLM 输入 prompt
            llm_input = self._get_prompt(node)
            # 删除 prompt 中的 当前节点的输出content
            llm_input = llm_input.replace(content, "")
            
            # 如果节点设置了 data_out，根据 data_out_thread 合并到目标线程
            # (这个逻辑已经包含在父类 handler 里了吗？)
            # 检查父类 executor.py:
            # _execute_llm_first_node -> calls _set_data_out.
            # aexecute -> calls _merge_data_out.
            # 父类的 handler 只负责执行和 set_data_out，merge 是由调用者做的。
            # 所以这里需要做 merge。
            
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
                tool_calls=[],  # TODO: 收集工具调用记录，父类目前没有方便的接口暴露这个，除非解析 messsages
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

    async def rerun_node(self, node_id: int) -> Optional[NodeContext]:
        """
        重新执行指定节点
        
        1. 恢复到该节点执行前的 context
        2. 重置该节点及之后节点的状态
        3. 重新执行该节点
        
        Args:
            node_id: 要重新执行的节点 ID
            
        Returns:
            NodeContext: 执行完成的节点上下文
            
        Raises:
            ValueError: 如果节点尚未执行过
        """
        if node_id not in self.context_history:
            raise ValueError(f"节点 {node_id} 尚未执行过，无法重新运行")
        
        if node_id < 1 or node_id > len(self.plan.nodes):
            raise ValueError(f"节点 ID {node_id} 超出范围 (1-{len(self.plan.nodes)})")
        
        logger.info(f"🔄 重新执行节点 {node_id}")
        
        # 1. 恢复上下文到该节点执行前的状态
        self.context = copy.deepcopy(self.context_history[node_id])
        
        # 2. 删除该节点及之后的历史和上下文
        for nid in list(self.context_history.keys()):
            if nid >= node_id:
                del self.context_history[nid]
        for nid in list(self.node_contexts.keys()):
            if nid >= node_id:
                del self.node_contexts[nid]
        
        # 3. 重置该节点及之后的状态为 PENDING
        for nid, state in self.node_states.items():
            if nid >= node_id:
                state.status = NodeStatus.PENDING
                state.start_time = None
                state.end_time = None
                state.error = None
        
        # 4. 更新当前节点索引
        self._current_node_index = node_id - 1
        
        # 5. 执行该节点
        node = self.plan.nodes[node_id - 1]
        self.reset_tools_limit(node)
        await self._execute_single_node(node, node_id)
        
        logger.info(f"✅ 节点 {node_id} 重新执行完成")
        
        return self.node_contexts.get(node_id)
