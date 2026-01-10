# 前端 API 客户端
# 封装与后端 FastAPI 服务的通信

import asyncio
import aiohttp
from typing import Optional, Any
from dataclasses import dataclass
from enum import Enum
try:
    from config import BACKEND_PORT
except ImportError:
    try:
        from ..config import BACKEND_PORT
    except ImportError:
        BACKEND_PORT = 8001

class ExecutorStatus(str, Enum):
    """执行器状态"""
    INITIALIZED = "initialized"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class NodeState:
    """节点状态"""
    node_id: int
    node_name: str
    status: str
    start_time: Optional[str] = None
    end_time: Optional[str] = None
    error: Optional[str] = None


@dataclass
class NodeContext:
    """节点上下文"""
    node_id: int
    node_name: str
    thread_id: str
    thread_messages_before: list
    thread_messages_after: list
    llm_input: str
    llm_output: str
    tool_calls: list
    data_out_content: Optional[str] = None


@dataclass
class ExecutionProgress:
    """执行进度"""
    total: int
    completed: int
    failed: int
    running: int
    pending: int
    progress_percent: float


class APIError(Exception):
    """API 错误"""
    def __init__(self, status_code: int, message: str):
        self.status_code = status_code
        self.message = message
        super().__init__(f"API Error {status_code}: {message}")


class ExecutorAPIClient:
    """
    执行器 API 客户端
    
    用于与后端 FastAPI 服务通信，支持同步和异步调用
    """
    
    def __init__(self, base_url: str = f"http://localhost:{BACKEND_PORT}"):
        self.base_url = base_url.rstrip("/")
        self._session: Optional[aiohttp.ClientSession] = None
    
    async def _get_session(self) -> aiohttp.ClientSession:
        """获取或创建 aiohttp session"""
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession()
        return self._session
    
    async def close(self):
        """关闭 session"""
        if self._session and not self._session.closed:
            await self._session.close()
    
    async def _request(
        self, 
        method: str, 
        endpoint: str, 
        json_data: dict = None,
        params: dict = None
    ) -> dict:
        """发送 HTTP 请求"""
        session = await self._get_session()
        url = f"{self.base_url}{endpoint}"
        
        try:
            async with session.request(
                method, 
                url, 
                json=json_data,
                params=params
            ) as response:
                data = await response.json()
                
                if response.status >= 400:
                    error_detail = data.get("detail", str(data))
                    raise APIError(response.status, error_detail)
                
                return data
                
        except aiohttp.ClientError as e:
            raise APIError(0, f"Connection error: {str(e)}")
    
    # =========================================================================
    # 健康检查
    # =========================================================================
    
    async def health_check(self) -> dict:
        """检查后端服务是否运行"""
        return await self._request("GET", "/")
    
    # =========================================================================
    # 工具管理
    # =========================================================================
    
    async def list_tools(self) -> list[dict]:
        """获取已注册的工具列表"""
        result = await self._request("GET", "/api/tools")
        return result.get("tools", [])
    
    # =========================================================================
    # 执行器生命周期
    # =========================================================================
    
    async def init_executor(
        self,
        plan: dict,
        user_message: str,
        tools_config: list[dict] = None,
        model_config: dict = None
    ) -> dict:
        """
        初始化执行器
        
        Args:
            plan: 执行计划 (ExecutionPlan 的字典形式)
            user_message: 用户消息
            tools_config: 工具配置列表 [{"name": "xxx", "limit": 10}, ...]
            model_config: 模型配置
            
        Returns:
            dict: 包含 executor_id, status, node_count, message
        """
        data = {
            "plan": plan,
            "user_message": user_message
        }
        if tools_config:
            data["tools_config"] = tools_config
        if model_config:
            data["model_config"] = model_config
            
        return await self._request("POST", "/api/executor/init", json_data=data)
    
    async def run_executor(self, executor_id: str, sync: bool = False) -> dict:
        """
        运行执行器
        
        Args:
            executor_id: 执行器 ID
            sync: 是否同步执行（等待完成）
            
        Returns:
            dict: 执行结果
        """
        endpoint = f"/api/executor/{executor_id}/run"
        if sync:
            endpoint = f"/api/executor/{executor_id}/run-sync"
        
        return await self._request("POST", endpoint)
    
    async def step_executor(self, executor_id: str, node_id: int = None) -> dict:
        """
        单步执行
        
        Args:
            executor_id: 执行器 ID
            node_id: 可选，指定要执行的节点 ID
            
        Returns:
            dict: 包含 status, message, node_context, progress
        """
        data = {}
        if node_id is not None:
            data["node_id"] = node_id
            
        return await self._request(
            "POST", 
            f"/api/executor/{executor_id}/step",
            json_data=data if data else None
        )
    
    async def get_executor_status(self, executor_id: str) -> dict:
        """
        获取执行器状态
        
        Args:
            executor_id: 执行器 ID
            
        Returns:
            dict: 包含 executor_id, overall_status, progress, node_states
        """
        return await self._request("GET", f"/api/executor/{executor_id}/status")
    
    async def terminate_executor(self, executor_id: str) -> dict:
        """
        终止执行器
        
        Args:
            executor_id: 执行器 ID
            
        Returns:
            dict: 包含 status, message
        """
        return await self._request("DELETE", f"/api/executor/{executor_id}")
    
    async def list_executors(self) -> list[dict]:
        """
        列出所有执行器
        
        Returns:
            list: 执行器信息列表
        """
        result = await self._request("GET", "/api/executors")
        return result.get("executors", [])
    
    # =========================================================================
    # 节点上下文
    # =========================================================================
    
    async def get_node_context(self, executor_id: str, node_id: int) -> dict:
        """
        获取节点上下文
        
        Args:
            executor_id: 执行器 ID
            node_id: 节点 ID
            
        Returns:
            dict: 节点上下文信息
        """
        return await self._request(
            "GET", 
            f"/api/executor/{executor_id}/nodes/{node_id}/context"
        )
    
    async def get_executor_messages(
        self, 
        executor_id: str, 
        thread_id: str = None
    ) -> dict:
        """
        获取执行器消息
        
        Args:
            executor_id: 执行器 ID
            thread_id: 可选，指定线程 ID
            
        Returns:
            dict: 消息数据
        """
        params = {}
        if thread_id:
            params["thread_id"] = thread_id
            
        return await self._request(
            "GET",
            f"/api/executor/{executor_id}/messages",
            params=params if params else None
        )
    
    # =========================================================================
    # 同步包装器（用于非异步环境）
    # =========================================================================
    
    def sync_health_check(self) -> dict:
        """同步健康检查"""
        return asyncio.run(self.health_check())
    
    def sync_init_executor(
        self,
        plan: dict,
        user_message: str,
        tools_config: list[dict] = None,
        model_config: dict = None
    ) -> dict:
        """同步初始化执行器"""
        return asyncio.run(self.init_executor(plan, user_message, tools_config, model_config))
    
    def sync_run_executor(self, executor_id: str, sync: bool = False) -> dict:
        """同步运行执行器"""
        return asyncio.run(self.run_executor(executor_id, sync))
    
    def sync_step_executor(self, executor_id: str, node_id: int = None) -> dict:
        """同步单步执行"""
        return asyncio.run(self.step_executor(executor_id, node_id))
    
    def sync_get_executor_status(self, executor_id: str) -> dict:
        """同步获取执行器状态"""
        return asyncio.run(self.get_executor_status(executor_id))
    
    def sync_get_node_context(self, executor_id: str, node_id: int) -> dict:
        """同步获取节点上下文"""
        return asyncio.run(self.get_node_context(executor_id, node_id))
    
    def sync_terminate_executor(self, executor_id: str) -> dict:
        """同步终止执行器"""
        return asyncio.run(self.terminate_executor(executor_id))


# =============================================================================
# PyQt 异步工作线程
# =============================================================================

try:
    from PyQt5.QtCore import QThread, pyqtSignal, QObject
    
    class AsyncWorker(QThread):
        """
        异步任务工作线程
        
        在独立线程中运行 asyncio 事件循环，用于 PyQt 应用
        """
        
        # 信号定义
        taskCompleted = pyqtSignal(str, object)  # (task_id, result)
        taskFailed = pyqtSignal(str, str)  # (task_id, error_message)
        
        def __init__(self, parent=None):
            super().__init__(parent)
            self.loop: Optional[asyncio.AbstractEventLoop] = None
            self._running = False
            self._pending_tasks: dict[str, asyncio.Future] = {}
        
        def run(self):
            """线程主函数"""
            self.loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self.loop)
            self._running = True
            
            try:
                self.loop.run_forever()
            finally:
                self.loop.close()
                self._running = False
        
        def stop(self):
            """停止事件循环"""
            if self.loop and self._running:
                self.loop.call_soon_threadsafe(self.loop.stop)
        
        def run_async(self, coro, task_id: str = None) -> asyncio.Future:
            """
            在事件循环中运行协程
            
            Args:
                coro: 要运行的协程
                task_id: 任务标识符（用于结果回调）
                
            Returns:
                Future 对象
            """
            if not self.loop or not self._running:
                raise RuntimeError("Event loop is not running")
            
            future = asyncio.run_coroutine_threadsafe(coro, self.loop)
            
            if task_id:
                self._pending_tasks[task_id] = future
                
                def on_done(f):
                    try:
                        result = f.result()
                        self.taskCompleted.emit(task_id, result)
                    except Exception as e:
                        self.taskFailed.emit(task_id, str(e))
                    finally:
                        self._pending_tasks.pop(task_id, None)
                
                future.add_done_callback(on_done)
            
            return future
    
    
    class ExecutorController(QObject):
        """
        执行器控制器
        
        封装 API 客户端和异步工作线程，提供 PyQt 友好的接口
        """
        
        # 信号定义
        initCompleted = pyqtSignal(dict)
        initFailed = pyqtSignal(str)
        stepCompleted = pyqtSignal(dict)
        stepFailed = pyqtSignal(str)
        runCompleted = pyqtSignal(dict)
        runFailed = pyqtSignal(str)
        statusUpdated = pyqtSignal(dict)
        contextLoaded = pyqtSignal(dict)
        contextFailed = pyqtSignal(str)
        
        def __init__(self, base_url: str = f"http://localhost:{BACKEND_PORT}", parent=None):
            super().__init__(parent)
            self.api_client = ExecutorAPIClient(base_url)
            self.worker = AsyncWorker()
            self.current_executor_id: Optional[str] = None
            
            # 连接工作线程信号
            self.worker.taskCompleted.connect(self._on_task_completed)
            self.worker.taskFailed.connect(self._on_task_failed)
            
            # 启动工作线程
            self.worker.start()
        
        def cleanup(self):
            """清理资源"""
            self.worker.stop()
            self.worker.wait()
            asyncio.run(self.api_client.close())

        def reset_session(self):
            """重置会话 (用于处理 404 等由于后端重启导致的 ID 失效)"""
            self.current_executor_id = None
        
        def _on_task_completed(self, task_id: str, result):
            """处理任务完成"""
            if task_id == "init":
                self.current_executor_id = result.get("executor_id")
                self.initCompleted.emit(result)
            elif task_id == "step":
                self.stepCompleted.emit(result)
            elif task_id == "run":
                self.runCompleted.emit(result)
            elif task_id == "status":
                self.statusUpdated.emit(result)
            elif task_id.startswith("context_"):
                self.contextLoaded.emit(result)
        
        def _on_task_failed(self, task_id: str, error: str):
            """处理任务失败"""
            if task_id == "init":
                self.initFailed.emit(error)
            elif task_id == "step":
                self.stepFailed.emit(error)
            elif task_id == "run":
                self.runFailed.emit(error)
            elif task_id.startswith("context_"):
                self.contextFailed.emit(error)
        
        def init_executor(self, plan: dict, user_message: str, tools_config: list = None):
            """初始化执行器"""
            coro = self.api_client.init_executor(plan, user_message, tools_config)
            self.worker.run_async(coro, "init")
        
        def step_executor(self):
            """单步执行"""
            if not self.current_executor_id:
                self.stepFailed.emit("No executor initialized")
                return
            coro = self.api_client.step_executor(self.current_executor_id)
            self.worker.run_async(coro, "step")
        
        def run_executor(self, sync: bool = True):
            """运行执行器"""
            if not self.current_executor_id:
                self.runFailed.emit("No executor initialized")
                return
            coro = self.api_client.run_executor(self.current_executor_id, sync)
            self.worker.run_async(coro, "run")
        
        def get_status(self):
            """获取执行器状态"""
            if not self.current_executor_id:
                return
            coro = self.api_client.get_executor_status(self.current_executor_id)
            self.worker.run_async(coro, "status")
        
        def get_node_context(self, node_id: int):
            """获取节点上下文"""
            if not self.current_executor_id:
                self.contextFailed.emit("No executor initialized")
                return
            coro = self.api_client.get_node_context(self.current_executor_id, node_id)
            self.worker.run_async(coro, f"context_{node_id}")
        
        def terminate(self):
            """终止当前执行器"""
            if self.current_executor_id:
                coro = self.api_client.terminate_executor(self.current_executor_id)
                self.worker.run_async(coro, "terminate")
                self.current_executor_id = None


except ImportError:
    # PyQt6 未安装时，提供占位类
    class AsyncWorker:
        pass
    
    class ExecutorController:
        pass


# =============================================================================
# 测试代码
# =============================================================================

if __name__ == "__main__":
    async def test():
        client = ExecutorAPIClient()
        
        # 健康检查
        try:
            result = await client.health_check()
            print(f"Health check: {result}")
        except APIError as e:
            print(f"Health check failed: {e}")
        
        await client.close()
    
    asyncio.run(test())
