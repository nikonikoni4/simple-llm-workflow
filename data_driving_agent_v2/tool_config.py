"""
工具和模型配置类

这个类用于管理自动执行所需的工具和模型创建。
提供统一的接口来收集 tools_map、tools_limit，以及使用 LangChain 创建模型。
"""

from typing import Callable, Dict, Optional
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.tools import BaseTool


class ToolConfig:
    """
    工具和模型配置管理类
    
    功能：
    1. 收集和管理工具映射 (tools_map)
    2. 管理工具调用次数限制 (tools_limit)
    3. 使用 LangChain 创建模型
    
    使用示例：
        ```python
        from tool_config import ToolConfig
        from function_example import add
        
        # 创建配置实例
        config = ToolConfig(api_key="your-api-key")
        
        # 注册工具
        config.register_tool("add", add, limit=5)
        
        # 获取工具映射和限制
        tools_map = config.get_tools_map()
        tools_limit = config.get_tools_limit()
        
        # 创建模型
        llm = config.create_llm(enable_search=False, enable_thinking=False)
        ```
    """
    
    def __init__(
        self,
        api_key: Optional[str] = None,
        model_name: str = "qwen-plus",
        default_tool_limit: int = 10
    ):
        """
        初始化工具配置
        
        Args:
            api_key: API密钥，用于创建模型。如果为None，将从环境变量读取
            model_name: 模型名称，默认为 "qwen-plus"
            default_tool_limit: 默认工具调用次数限制，默认为 10
        """
        self.api_key = api_key
        self.model_name = model_name
        self.default_tool_limit = default_tool_limit
        
        # 工具映射：工具名称 -> 工具函数/对象
        self._tools_map: Dict[str, Callable | BaseTool] = {}
        
        # 工具调用次数限制：工具名称 -> 调用次数
        self._tools_limit: Dict[str, int] = {}
    
    def register_tool(
        self,
        name: str,
        tool: Callable | BaseTool,
        limit: Optional[int] = None
    ) -> "ToolConfig":
        """
        注册一个工具
        
        Args:
            name: 工具名称
            tool: 工具函数或 LangChain Tool 对象
            limit: 该工具的调用次数限制。如果为 None，使用 default_tool_limit
        
        Returns:
            self: 返回自身，支持链式调用
        
        Example:
            ```python
            config.register_tool("add", add, limit=5)
                  .register_tool("multiply", multiply, limit=3)
            ```
        """
        self._tools_map[name] = tool
        self._tools_limit[name] = limit if limit is not None else self.default_tool_limit
        return self
    
    def register_tools(
        self,
        tools: Dict[str, Callable | BaseTool],
        limits: Optional[Dict[str, int]] = None
    ) -> "ToolConfig":
        """
        批量注册工具
        
        Args:
            tools: 工具字典，格式为 {工具名称: 工具函数/对象}
            limits: 工具限制字典，格式为 {工具名称: 调用次数}。
                   如果某个工具未指定限制，使用 default_tool_limit
        
        Returns:
            self: 返回自身，支持链式调用
        
        Example:
            ```python
            config.register_tools(
                tools={"add": add, "multiply": multiply},
                limits={"add": 5, "multiply": 3}
            )
            ```
        """
        limits = limits or {}
        for name, tool in tools.items():
            limit = limits.get(name, self.default_tool_limit)
            self.register_tool(name, tool, limit)
        return self
    
    def unregister_tool(self, name: str) -> "ToolConfig":
        """
        取消注册一个工具
        
        Args:
            name: 要取消注册的工具名称
        
        Returns:
            self: 返回自身，支持链式调用
        """
        self._tools_map.pop(name, None)
        self._tools_limit.pop(name, None)
        return self
    
    def get_tools_map(self) -> Dict[str, Callable | BaseTool]:
        """
        获取工具映射
        
        Returns:
            工具映射字典的副本
        """
        return self._tools_map.copy()
    
    def get_tools_limit(self) -> Dict[str, int]:
        """
        获取工具调用次数限制
        
        Returns:
            工具限制字典的副本
        """
        return self._tools_limit.copy()
    
    def set_tool_limit(self, name: str, limit: int) -> "ToolConfig":
        """
        设置特定工具的调用次数限制
        
        Args:
            name: 工具名称
            limit: 新的调用次数限制
        
        Returns:
            self: 返回自身，支持链式调用
        
        Raises:
            KeyError: 如果工具未注册
        """
        if name not in self._tools_map:
            raise KeyError(f"工具 '{name}' 未注册")
        self._tools_limit[name] = limit
        return self
    
    def create_llm(
        self,
        enable_search: bool = False,
        enable_thinking: bool = False,
        temperature: Optional[float] = None,
        **kwargs
    ) -> BaseChatModel:
        """
        使用 LangChain 创建模型

        Args:
            enable_search: 是否启用搜索功能
            enable_thinking: 是否启用思考功能
            temperature: 温度参数，控制输出的随机性
            **kwargs: 其他传递给模型的参数

        Returns:
            创建的 LangChain 模型实例

        Example:
            ```python
            llm = config.create_llm(
                enable_search=False,
                enable_thinking=True,
                temperature=0.7
            )
            ```
        """
        from .llm_factory import create_qwen_llm

        # 准备参数
        model_kwargs = {
            "api_key": self.api_key,
            "model": self.model_name,
            "enable_search": enable_search,
            "enable_thinking": enable_thinking,
            "temperature": temperature if temperature is not None else 0.7,
        }

        # 添加其他参数
        model_kwargs.update(kwargs)

        return create_qwen_llm(**model_kwargs)
    
    def get_tool_count(self) -> int:
        """
        获取已注册的工具数量
        
        Returns:
            工具数量
        """
        return len(self._tools_map)
    
    def list_tools(self) -> list[str]:
        """
        列出所有已注册的工具名称
        
        Returns:
            工具名称列表
        """
        return list(self._tools_map.keys())
    
    def get_tool_info(self) -> Dict[str, Dict[str, any]]:
        """
        获取所有工具的详细信息
        
        Returns:
            工具信息字典，格式为：
            {
                "tool_name": {
                    "tool": <tool_object>,
                    "limit": <call_limit>,
                    "type": <tool_type>
                }
            }
        """
        info = {}
        for name in self._tools_map:
            tool = self._tools_map[name]
            info[name] = {
                "tool": tool,
                "limit": self._tools_limit.get(name, self.default_tool_limit),
                "type": type(tool).__name__
            }
        return info
    
    def __repr__(self) -> str:
        """字符串表示"""
        return (
            f"ToolConfig(tools={len(self._tools_map)}, "
            f"model='{self.model_name}', "
            f"default_limit={self.default_tool_limit})"
        )
    
    def __str__(self) -> str:
        """友好的字符串表示"""
        tools_str = ", ".join(self.list_tools()) if self._tools_map else "无"
        return (
            f"工具配置:\n"
            f"  - 已注册工具: {tools_str}\n"
            f"  - 工具数量: {len(self._tools_map)}\n"
            f"  - 模型名称: {self.model_name}\n"
            f"  - 默认限制: {self.default_tool_limit}"
        )


# =============================================================================
# 便捷函数
# =============================================================================

def create_default_config(
    api_key: Optional[str] = None,
    include_examples: bool = False
) -> ToolConfig:
    """
    创建默认的工具配置
    
    Args:
        api_key: API密钥
        include_examples: 是否包含示例工具
    
    Returns:
        配置好的 ToolConfig 实例
    """
    config = ToolConfig(api_key=api_key)
    
    if include_examples:
        # 导入示例工具
        try:
            from .function_example import add
            config.register_tool("add", add, limit=5)
        except ImportError:
            pass
    
    return config


# =============================================================================
# 使用示例
# =============================================================================

if __name__ == "__main__":
    # 示例1：基本使用
    print("=" * 60)
    print("示例1：基本使用")
    print("=" * 60)
    
    from .function_example import add

    
    config = ToolConfig(api_key="your-api-key")
    config.register_tool("add", add, limit=5)
    
    print(config)
    print(f"\n工具映射: {config.get_tools_map()}")
    print(f"工具限制: {config.get_tools_limit()}")
    
    # 示例2：链式调用
    print("\n" + "=" * 60)
    print("示例2：链式调用")
    print("=" * 60)
    
    config2 = (ToolConfig(api_key="your-api-key")
               .register_tool("add", add, limit=5)
               .register_tool("add2", add, limit=3))
    
    print(config2)
    
    # 示例3：批量注册
    print("\n" + "=" * 60)
    print("示例3：批量注册")
    print("=" * 60)
    
    config3 = ToolConfig(api_key="your-api-key")
    config3.register_tools(
        tools={"add": add, "add2": add},
        limits={"add": 5, "add2": 3}
    )
    
    print(config3)
    print(f"\n工具信息: {config3.get_tool_info()}")
    
    # 示例4：创建模型
    print("\n" + "=" * 60)
    print("示例4：创建模型")
    print("=" * 60)
    
    try:
        llm = config.create_llm(enable_search=False, enable_thinking=False)
        print(f"模型创建成功: {type(llm).__name__}")
    except Exception as e:
        print(f"模型创建失败: {e}")
