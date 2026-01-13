from llm_linear_executor.schemas import (
    NodeType,
    ALL_NODE_TYPES,
    MAIN_EXECUTOR_PERMISSIONS,
    SUB_EXECUTOR_PERMISSIONS,
    Context,
    NodeDefinition,
    ExecutionPlan
)
from pydantic import Field, model_validator
from typing import Optional, Any
from pydantic import BaseModel

ModelConfig = dict

# 布局常量 (与 graph.py 保持一致)
NODE_GAP_X = 200  # 节点之间的水平间距
THREAD_GAP_Y = 120  # 线程之间的垂直间距
MAIN_Y_BASELINE = 0  # 主线程Y轴基准线


class NodeProperties(NodeDefinition):
    """前端节点属性扩展"""
    # 标识与索引 (设置默认值，允许在创建时不传入，后续由 GuiExecutionPlan 自动填充)
    node_id: int = Field(default=0, description="节点ID，用于前端逻辑索引")
    thread_view_index: int = Field(default=0, description="在当前线程中的显示索引")
    # 布局信息 (直接平铺在对象中，方便存取)
    x: int = Field(default=0, description="UI X坐标")
    y: int = Field(default=0, description="UI Y坐标")

class GuiExecutionPlan(ExecutionPlan):
    """
    前端专用执行计划
    
    关键机制：
    1. 继承 ExecutionPlan 保持逻辑结构一致
    2. 覆盖 nodes 字段类型为 List[NodeProperties]
    3. Load 时：自动计算 node_id, thread_view_index, x, y 坐标
    4. Save 时：会自动保存 x,y 坐标到 JSON
    
    布局计算逻辑 (参考 graph.py auto_layout_nodes):
    - node_id: 节点在列表中的位置 (1-indexed)
    - thread_view_index: 根据 thread_id 分配的 Y 轴索引
    - x: 由 node_id 决定的水平位置
    - y: 由 thread_view_index 决定的垂直位置
    """
    nodes: list[NodeProperties] = Field(description="包含 UI 布局信息的节点列表")
    thread_view_indices: dict[str, int] = Field(default={},description="thread_id 到 thread_view_index 的映射")
    @model_validator(mode='after')
    def _init_nodes(self) -> 'GuiExecutionPlan':
        """
        在模型初始化后自动计算并填充节点的布局信息
        
        计算逻辑:
        1. node_id: 基于节点在列表中的位置(1-indexed)
        2. thread_view_index: 根据 thread_id 分配唯一索引，main线程为0
        3. x: node_id * NODE_GAP_X
        4. y: MAIN_Y_BASELINE - (thread_view_index * THREAD_GAP_Y)
        """
        for idx, node in enumerate(self.nodes):
            # 1. 分配 node_id (1-indexed)
            node.node_id = idx + 1
            
            # 2. 处理 thread_view_index
            tid = node.thread_id
            
            # 检查 JSON 中是否已有 thread_view_index 值 (非默认值0)
            # 如果已有值，优先使用已保存的值
            if node.thread_view_index != 0 or (tid == "main" and node.thread_view_index == 0):
                # 如果节点已有非0的 thread_view_index，或是 main 线程（默认0是正确的），使用它
                if tid not in self.thread_view_indices:
                    self.thread_view_indices[tid] = node.thread_view_index
            
            if tid not in self.thread_view_indices:
                # 为新的 thread_id 分配索引
                # main 线程为 0，其他线程依次递增
                if tid == "main":
                    self.thread_view_indices[tid] = 0
                else:
                    # 分配新索引: max + 1
                    current_indices = list(self.thread_view_indices.values())
                    next_idx = max(current_indices) + 1 if current_indices else 1
                    self.thread_view_indices[tid] = next_idx
            
            node.thread_view_index = self.thread_view_indices[tid]
            
            # 3. 计算 x 坐标 (如果当前为默认值0，才重新计算)
            if node.x == 0:
                node.x = node.node_id * NODE_GAP_X
            
            # 4. 计算 y 坐标 (如果当前为默认值0，才重新计算)
            if node.y == 0:
                node.y = MAIN_Y_BASELINE - (node.thread_view_index * THREAD_GAP_Y)
        
        return self
        



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

if __name__ == "__main__":
    from llm_linear_executor.os_plan import load_plans_from_templates
    plans = load_plans_from_templates(r"llm_linear_executor\example\example1\example.json", schema=GuiExecutionPlan)
    print(plans)