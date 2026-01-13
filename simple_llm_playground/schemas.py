from llm_linear_executor.llm_linear_executor.schemas import (
    NodeType,
    ALL_NODE_TYPES,
    MAIN_EXECUTOR_PERMISSIONS,
    SUB_EXECUTOR_PERMISSIONS,
    Context,
    NodeDefinition,
    ExecutionPlan
)
from pydantic import Field
from typing import Optional
from pydantic import BaseModel
class NodeProperties(NodeDefinition):
    """前端节点属性扩展"""
    # 标识与索引
    node_id: int = Field(description="节点ID，用于前端逻辑索引")
    thread_order_index: int = Field(description="在当前线程中的顺序索引")
    
    # 布局信息 (直接平铺在对象中，方便存取)
    x: int = Field(default=0, description="UI X坐标")
    y: int = Field(default=0, description="UI Y坐标")

class GuiExecutionPlan(ExecutionPlan):
    """
    前端专用执行计划
    
    关键机制：
    1. 继承 ExecutionPlan 保持逻辑结构一致
    2. 覆盖 nodes 字段类型为 List[NodeProperties]
    3. Load 时：Pydantic 会自动解析 x,y 坐标
    4. Save 时：会自动保存 x,y 坐标到 JSON
    """
    nodes: list[NodeProperties] = Field(description="包含 UI 布局信息的节点列表")





class InitExecutorRequest(BaseModel):
    """初始化执行器请求"""
    plan: dict  # ExecutionPlan 的字典形式
    user_message: str
    default_tool_limit: Optional[int] = 1  # 默认工具调用次数限制
    llm_config: Optional[ModelConfig] = None  # 重命名避免与 Pydantic 保留字段冲突


class InitExecutorResponse(BaseModel):
    """初始化执行器响应"""
    executor_id: str
    status: str
    node_count: int
    message: str


class StepExecutorRequest(BaseModel):
    """单步执行请求"""
    node_id: Optional[int] = None  # 可选，不指定则执行下一个


class ExecutorStatusResponse(BaseModel):
    """执行器状态响应"""
    executor_id: str
    overall_status: str
    progress: dict
    node_states: list[dict]


class NodeContextResponse(BaseModel):
    """节点上下文响应"""
    node_id: int
    node_name: str
    thread_id: str
    thread_messages_before: list[dict]
    thread_messages_after: list[dict]
    llm_input: str
    llm_output: str
    tool_calls: list[dict]
    data_out_content: Optional[str]


class ExecutionResultResponse(BaseModel):
    """执行结果响应"""
    executor_id: str
    status: str
    content: Optional[str]
    tokens_usage: dict
    message: str