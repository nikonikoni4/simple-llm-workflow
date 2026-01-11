# FastAPI 后端服务
# 提供 RESTful API 用于前端与 AsyncExecutor 交互


from typing import Optional
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

import sys
import os

# 添加父目录到 path
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)


from .data_driving_schemas import ExecutionPlan
from .executor_manager import executor_manager


# =============================================================================
# 请求/响应模型
# =============================================================================
class ModelConfig(BaseModel):
    """模型配置"""
    api_key: Optional[str] = None
    enable_search: bool = False
    enable_thinking: bool = False
    temperature: float = 0.7
    top_p: float = 0.9


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





# =============================================================================
# FastAPI 应用
# =============================================================================
@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    # 启动时的初始化
    print("🚀 Backend API starting...")
    
    # 这里可以加载默认工具和 LLM 工厂
    # 实际使用时需要根据项目配置来设置
    
    # Setup test tools when running with uvicorn
    
    # setup_test_tools()
    # Also try to load get_daily_stats from test directory
    # try:
    #     # Add test directory to path if not already there
    #     test_dir = os.path.join(parent_dir, "test")
    #     if test_dir not in sys.path:
    #         sys.path.insert(0, test_dir)
        
    #     from test_fuction.get_daily_stats import get_daily_stats
    #     executor_manager.register_tool("get_daily_stats", get_daily_stats)
    #     print("✅ Registered tool: get_daily_stats")
    # except Exception as e:
    #     print(f"⚠️ Warning: Could not load get_daily_stats tool: {e}")
    
    # Setup LLM factory (using environment variable or defaults)
    setup_llm_factory()
    
    yield
    
    # 关闭时的清理
    print("🛑 Backend API shutting down...")
    executor_manager.executors.clear()


app = FastAPI(
    title="Simple LLM Playground API",
    description="Backend API for LLM Executor debugging and visualization",
    version="1.0.0",
    lifespan=lifespan
)

# CORS 配置
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# =============================================================================
# API 端点
# =============================================================================

@app.get("/")
async def root():
    """根路径 - 健康检查"""
    return {
        "status": "running",
        "service": "Simple LLM Playground API",
        "version": "1.0.0"
    }


@app.get("/api/tools")
async def list_tools():
    """列出所有已注册的工具"""
    tools = []
    for name, tool in executor_manager._tools_registry.items():
        tool_data = {
            "name": name,
            "description": getattr(tool, 'description', 'No description'),
        }
        
        # Try to extract parameter information from langchain tool
        try:
            # Check if it's a langchain tool with args_schema
            if hasattr(tool, 'args_schema'):
                schema = tool.args_schema
                if schema:
                    # Get field information from pydantic model
                    tool_data["parameters"] = {}
                    if hasattr(schema, 'model_fields'):
                        for field_name, field_info in schema.model_fields.items():
                            tool_data["parameters"][field_name] = {
                                "type": str(field_info.annotation),
                                "required": field_info.is_required(),
                                "description": field_info.description or ""
                            }
            
            # Also try to get from function signature
            if hasattr(tool, 'func'):
                import inspect
                sig = inspect.signature(tool.func)
                if "parameters" not in tool_data:
                    tool_data["parameters"] = {}
                
                for param_name, param in sig.parameters.items():
                    if param_name not in tool_data["parameters"]:
                        tool_data["parameters"][param_name] = {
                            "type": str(param.annotation) if param.annotation != inspect.Parameter.empty else "Any",
                            "required": param.default == inspect.Parameter.empty,
                            "description": ""
                        }
        except Exception as e:
            # If extraction fails, just skip parameters
            print(f"Warning: Could not extract parameters for tool {name}: {e}")
        
        tools.append(tool_data)
    
    return {"tools": tools}



@app.post("/api/executor/init", response_model=InitExecutorResponse)
async def init_executor(request: InitExecutorRequest):
    """
    初始化执行器

    创建一个新的 AsyncExecutor 实例，准备执行计划
    """
    try:
        # 解析 ExecutionPlan
        plan = ExecutionPlan(**request.plan)
        if request.default_tool_limit is None:
            request.default_tool_limit = 1
        # 创建执行器
        executor_id = executor_manager.create_executor(
            plan=plan,
            user_message=request.user_message,
            default_tools_limit=request.default_tool_limit # 当这个是None时，导致后面会报错
        )
        
        return InitExecutorResponse(
            executor_id=executor_id,
            status="initialized",
            node_count=len(plan.nodes),
            message=f"Executor initialized with {len(plan.nodes)} nodes"
        )
        
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/api/executor/{executor_id}/run", response_model=ExecutionResultResponse)
async def run_executor(executor_id: str, background_tasks: BackgroundTasks):
    """
    运行执行器（执行整个计划）
    
    在后台任务中执行，立即返回
    """
    executor = executor_manager.get_executor(executor_id)
    if not executor:
        raise HTTPException(status_code=404, detail="Executor not found")
    
    # 更新状态
    executor_manager.executor_status[executor_id] = "running"
    
    async def execute_in_background():
        try:
            result = await executor.execute()
            executor_manager.executor_status[executor_id] = "completed"
        except Exception as e:
            executor_manager.executor_status[executor_id] = f"failed: {str(e)}"
    
    # 添加后台任务
    background_tasks.add_task(execute_in_background)
    
    return ExecutionResultResponse(
        executor_id=executor_id,
        status="running",
        content=None,
        tokens_usage=executor.tokens_usage,
        message="Execution started in background"
    )


@app.post("/api/executor/{executor_id}/run-sync", response_model=ExecutionResultResponse)
async def run_executor_sync(executor_id: str):
    """
    同步运行执行器（等待执行完成）
    
    直接执行并返回结果，适用于需要立即获取结果的场景
    """
    executor = executor_manager.get_executor(executor_id)
    if not executor:
        raise HTTPException(status_code=404, detail="Executor not found")
    
    # 更新状态
    executor_manager.executor_status[executor_id] = "running"
    
    try:
        result = await executor.execute()
        executor_manager.executor_status[executor_id] = "completed"
        
        return ExecutionResultResponse(
            executor_id=executor_id,
            status="completed",
            content=result.get("content"),
            tokens_usage=result.get("tokens_usage", {}),
            message="Execution completed"
        )
    except Exception as e:
        executor_manager.executor_status[executor_id] = "failed"
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/executor/{executor_id}/step")
async def step_executor(executor_id: str, request: StepExecutorRequest = None):
    """
    单步执行
    
    执行下一个待执行的节点，返回节点上下文
    """
    executor = executor_manager.get_executor(executor_id)
    if not executor:
        raise HTTPException(status_code=404, detail="Executor not found")
    
    try:
        # 执行单步
        context = await executor.execute_step()
        
        if context is None:
            return {
                "status": "completed",
                "message": "All nodes have been executed",
                "node_context": None,
                "progress": executor.get_execution_progress()
            }
        
        return {
            "status": "success",
            "message": f"Node {context.node_id} executed",
            "node_context": context.model_dump(),
            "progress": executor.get_execution_progress()
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/executor/{executor_id}/status", response_model=ExecutorStatusResponse)
async def get_executor_status(executor_id: str):
    """
    获取执行器状态
    
    返回整体状态和所有节点的执行状态
    """
    executor = executor_manager.get_executor(executor_id)
    if not executor:
        raise HTTPException(status_code=404, detail="Executor not found")
    
    overall_status = executor_manager.executor_status.get(executor_id, "unknown")
    
    return ExecutorStatusResponse(
        executor_id=executor_id,
        overall_status=overall_status,
        progress=executor.get_execution_progress(),
        node_states=[s.model_dump() for s in executor.get_all_node_states()]
    )


@app.get("/api/executor/{executor_id}/nodes/{node_id}/context")
async def get_node_context(executor_id: str, node_id: int):
    """
    获取节点上下文
    
    返回指定节点的详细执行上下文信息
    """
    executor = executor_manager.get_executor(executor_id)
    if not executor:
        raise HTTPException(status_code=404, detail="Executor not found")
    
    context = executor.get_node_context(node_id)
    if not context:
        raise HTTPException(status_code=404, detail=f"Context for node {node_id} not found")
    
    return context.model_dump()


@app.get("/api/executor/{executor_id}/messages")
async def get_executor_messages(executor_id: str, thread_id: str = None):
    """
    获取执行器的消息
    
    可选指定 thread_id 获取特定线程的消息
    """
    executor = executor_manager.get_executor(executor_id)
    if not executor:
        raise HTTPException(status_code=404, detail="Executor not found")
    
    if thread_id:
        messages = executor._get_thread_messages(thread_id)
        return {
            "thread_id": thread_id,
            "messages": executor._serialize_messages(messages)
        }
    else:
        # 返回所有线程的消息
        all_messages = {}
        for tid in executor.context["messages"]:
            all_messages[tid] = executor._serialize_messages(
                executor.context["messages"][tid]
            )
        return {"threads": all_messages}


@app.delete("/api/executor/{executor_id}")
async def terminate_executor(executor_id: str):
    """
    终止并删除执行器
    """
    executor = executor_manager.get_executor(executor_id)
    if not executor:
        raise HTTPException(status_code=404, detail="Executor not found")
    
    executor_manager.remove_executor(executor_id)
    
    return {
        "status": "terminated",
        "message": f"Executor {executor_id} has been terminated"
    }


@app.get("/api/executors")
async def list_executors():
    """
    列出所有执行器
    """
    executors = []
    for eid, executor in executor_manager.executors.items():
        executors.append({
            "executor_id": eid,
            "status": executor_manager.executor_status.get(eid, "unknown"),
            "progress": executor.get_execution_progress()
        })
    return {"executors": executors}


# =============================================================================
# 工具注册 API（用于动态注册工具）
# =============================================================================

@app.post("/api/tools/register")
async def register_tool_endpoint(
    tool_name: str,
    tool_module: str,
    tool_function: str,
    limit: int = 10
):
    """
    动态注册工具
    
    从指定模块导入工具函数并注册
    """
    try:
        import importlib
        module = importlib.import_module(tool_module)
        tool_func = getattr(module, tool_function)
        
        executor_manager.register_tool(tool_name, tool_func)
        
        return {
            "status": "success",
            "message": f"Tool '{tool_name}' registered successfully"
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


# =============================================================================
# 用于测试的辅助函数
# =============================================================================

def setup_test_tools():
    """设置测试工具（用于开发测试）"""
    from langchain_core.tools import tool
    
    @tool
    def add(a: int, b: int) -> int:
        """Add two numbers"""
        return a + b
    
    @tool
    def multiply(a: int, b: int) -> int:
        """Multiply two numbers"""
        return a * b
    
    executor_manager.register_tool("add", add)
    executor_manager.register_tool("multiply", multiply)


def setup_llm_factory(
    api_key: str = None,
    model: str = "qwen-plus-2025-12-01",
    api_base: str = "https://dashscope.aliyuncs.com/compatible-mode/v1",
    **kwargs
):
    """
    设置 LLM 工厂函数

    支持阿里云 DashScope API (通义千问) 和 OpenAI API

    Args:
        api_key: API密钥 (DashScope API Key 或 OpenAI API Key)。如果不传，尝试从环境读取。
        model: 模型名称，默认 "qwen-plus"
            - 通义千问: "qwen-plus", "qwen-max", "qwen-turbo" 等
            - OpenAI: "gpt-4", "gpt-3.5-turbo" 等
        api_base: API基础URL
            - 阿里云: "https://dashscope.aliyuncs.com/compatible-mode/v1"
            - OpenAI: "https://api.openai.com/v1" (默认)
        **kwargs: 其他参数如 temperature, top_p 等
    """
    # 尝试从环境变量读取 API Key
    if not api_key:
        api_key = os.getenv("DASHSCOPE_API_KEY") or os.getenv("OPENAI_API_KEY")

    if not api_key:
        print("⚠️ Warning: No API key found. Please set DASHSCOPE_API_KEY or OPENAI_API_KEY environment variable.")

    # 使用 lambda 捕获所有参数，确保闭包正确捕获变量
    factory = lambda: _create_llm_instance(
        model=model,
        api_key=api_key,
        api_base=api_base,
        **kwargs
    )

    executor_manager.set_llm_factory(factory)


def _create_llm_instance(
    model: str,
    api_key: str,
    api_base: str,
    **kwargs
):
    """
    创建 LLM 实例的辅助函数

    Args:
        model: 模型名称
        api_key: API密钥
        api_base: API基础URL
        **kwargs: 其他参数

    Returns:
        ChatOpenAI 实例
    """
    try:
        from langchain_openai import ChatOpenAI

        # 使用 OpenAI 兼容模式，支持阿里云 DashScope 和 OpenAI
        return ChatOpenAI(
            model=model,
            openai_api_key=api_key,
            openai_api_base=api_base,
            temperature=kwargs.get('temperature', 0.7),
            top_p=kwargs.get('top_p', 0.9)
        )
    except ImportError:
        raise ValueError("langchain_openai not installed. Run: pip install langchain-openai")


# =============================================================================
# 启动入口
# =============================================================================

if __name__ == "__main__":
    import uvicorn
    
    # 1. 设置 LLM 工厂 (优先)
    setup_llm_factory()
    
    # 2. 设置测试工具
    # setup_test_tools()
    # 测试 LLM  链接
    # llm = executor_manager._llm_factory()
    # print(llm.invoke("Hello, how are you?"))
    # Try to import global config from main.py
    try:
        import config
        port = getattr(config, "BACKEND_PORT", 8001)
        print(f"⚙️  Loaded configuration from main.py: Port {port}")
    except ImportError:
        port = 8001
        print("⚠️  Warning: Could not import BACKEND_PORT from main.py, using default 8001")

    print("🚀 Starting Simple LLM Playground API...")
    print(f"📍 API docs available at: http://localhost:{port}/docs")

    uvicorn.run(app, host="0.0.0.0", port=port)
