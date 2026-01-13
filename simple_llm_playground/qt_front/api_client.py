import requests
import json
from PyQt5.QtCore import QObject, QThread, pyqtSignal

# 默认端口配置
try:
    from config import BACKEND_PORT
except ImportError:
    try:
        from ..config import BACKEND_PORT
    except ImportError:
        BACKEND_PORT = 8001

class APIWorker(QThread):
    """
    通用工作线程，用于在后台执行阻塞的 API 调用。
    """
    finished = pyqtSignal(object)  # 发送成功结果 (通常是 dict/list)
    error = pyqtSignal(str)        # 发送错误消息

    def __init__(self, func, *args, **kwargs):
        super().__init__()
        self.func = func
        self.args = args
        self.kwargs = kwargs

    def run(self):
        try:
            result = self.func(*self.args, **self.kwargs)
            self.finished.emit(result)
        except Exception as e:
            self.error.emit(str(e))


class ApiClient(QObject):
    """
    单例 API 客户端，用于处理与后端的通信。
    支持同步和异步（基于信号）调用。
    """
    _instance = None

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super(ApiClient, cls).__new__(cls)
            # 仅初始化一次 QObject 部分
            super(ApiClient, cls._instance).__init__()
            cls._instance._initialized = False
        return cls._instance

    def __init__(self, base_url=None):
        # 确保 __init__ 只运行一次
        if getattr(self, '_initialized', False):
            return
            
        self._initialized = True
        
        if base_url:
            self.base_url = base_url.rstrip('/')
        else:
            self.base_url = f"http://localhost:{BACKEND_PORT}"
            
        self.timeout = 5.0 # 默认超时时间（秒）

    def _get_url(self, endpoint):
        if endpoint.startswith("http"):
            return endpoint
        return f"{self.base_url}/{endpoint.lstrip('/')}"

    # --- 同步方法 (阻塞) ---

    def get_sync(self, endpoint, params=None):
        """
        执行同步 GET 请求。
        返回解析后的 JSON 或抛出异常。
        """
        try:
            url = self._get_url(endpoint)
            response = requests.get(url, params=params, timeout=self.timeout)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            raise Exception(f"API Request Failed: {e}")

    def post_sync(self, endpoint, data=None):
        """
        执行同步 POST 请求。
        返回解析后的 JSON 或抛出异常。
        """
        try:
            url = self._get_url(endpoint)
            response = requests.post(url, json=data, timeout=self.timeout)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            raise Exception(f"API Request Failed: {e}")

    # --- 异步方法 (非阻塞) ---
    
    def async_get(self, endpoint, callback=None, error_callback=None, params=None):
        """
        启动后台线程执行 GET 请求。
        api_client.async_get('/api/node/1', self.success_handler)
        
        返回工作线程实例 (如果需要可以保留引用，
        但通常如果连接了回调函数，则不是严格必需的)。
        """
        worker = APIWorker(self.get_sync, endpoint, params=params)
        
        if callback:
            worker.finished.connect(callback)
        if error_callback:
            worker.error.connect(error_callback)
            
        # 完成后自动清理线程
        worker.finished.connect(worker.deleteLater)
        worker.error.connect(worker.deleteLater)
        
        worker.start()
        return worker

    def async_post(self, endpoint, callback=None, error_callback=None, data=None):
        """
        启动后台线程执行 POST 请求。
        """
        worker = APIWorker(self.post_sync, endpoint, data=data)
        
        if callback:
            worker.finished.connect(callback)
        if error_callback:
            worker.error.connect(error_callback)
            
        worker.finished.connect(worker.deleteLater)
        worker.error.connect(worker.deleteLater)
        
        worker.start()
        return worker

    # --- 特定业务逻辑方法封装 ---

    def fetch_node_context(self, run_id, node_id, callback, error_callback=None):
        """
        获取特定节点的执行上下文。
        """
        endpoint = f"/api/context/{run_id}/{node_id}"
        return self.async_get(endpoint, callback, error_callback)

    def trigger_run(self, plan_data, callback, error_callback=None):
        """
        开始执行一个计划。
        """
        return self.async_post("/api/run", callback, error_callback, data=plan_data)
