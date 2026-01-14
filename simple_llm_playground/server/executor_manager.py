import uuid
from datetime import datetime
from typing import Any
from async_executor import AsyncExecutor
from simple_llm_playground.schemas import ExecutionPlan

# =============================================================================
# 执行器管理
# =============================================================================
class ExecutorManager:
    """执行器实例管理器"""
    
    def __init__(self):
        self.executors: dict[str, AsyncExecutor] = {}
        self.executor_status: dict[str, str] = {}  # executor_id -> overall status
        self.executor_start_times: dict[str, str] = {}  # executor_id -> start_time (ISO format)
        self._tools_registry: dict[str, Any] = {}  # 全局工具注册表
        self._llm_factory = None  # LLM 工厂函数
        
    def register_tool(self, name: str, tool: Any):
        """注册工具到全局注册表"""
        self._tools_registry[name] = tool
        
    def set_llm_factory(self, factory):
        """设置 LLM 工厂函数"""
        self._llm_factory = factory
        
    def get_tools_map(self, tool_names: list[str] | None) -> dict:
        """根据工具名称列表获取工具映射"""
        if not tool_names:
            return self._tools_registry.copy()
        return {name: self._tools_registry[name] for name in tool_names if name in self._tools_registry}
    
    def create_executor(
        self,
        plan: ExecutionPlan,
        default_tools_limit: int | None = None
    ) -> str:
        """创建新的执行器实例"""
        executor_id = str(uuid.uuid4())

        executor = AsyncExecutor(
            plan=plan,
            tools_map=self._tools_registry.copy(),
            default_tools_limit=default_tools_limit,
            llm_factory=self._llm_factory
        )
        
        self.executors[executor_id] = executor
        self.executor_status[executor_id] = "initialized"
        self.executor_start_times[executor_id] = datetime.now().isoformat()
        
        return executor_id
    
    def get_executor(self, executor_id: str) -> AsyncExecutor | None:
        """获取执行器实例"""
        return self.executors.get(executor_id)
    
    def remove_executor(self, executor_id: str):
        """移除执行器实例"""
        if executor_id in self.executors:
            del self.executors[executor_id]
        if executor_id in self.executor_status:
            del self.executor_status[executor_id]
        if executor_id in self.executor_start_times:
            del self.executor_start_times[executor_id]


# 全局执行器管理器
executor_manager = ExecutorManager()
