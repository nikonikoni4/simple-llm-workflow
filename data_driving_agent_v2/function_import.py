"""
工具和模型导入示例

提供两种方式：
1. 传统方式：直接定义 tools_map 和 tools_limit（向后兼容）
2. 新方式：使用 ToolConfig 类（推荐）

同时也展示了使用新的 llm_factory 创建 LLM 的方法
"""

# =============================================================================
# 方式1：传统方式（向后兼容）
# =============================================================================
from .function_example import add


tools_map = {
    "add": add
}

tools_limit = {
    "add": 1
}


# =============================================================================
# 方式2：使用 ToolConfig 类（推荐）
# =============================================================================
from .tool_config import ToolConfig


# 创建工具配置实例
tool_config = ToolConfig(
    api_key=None,  # 可以在这里设置 API key，或从环境变量读取
    model_name="qwen-plus",
    default_tool_limit=10
)

# 注册工具（支持链式调用）
tool_config.register_tool("add", add, limit=1)

# 或者批量注册
# tool_config.register_tools(
#     tools={"add": add},
#     limits={"add": 1}
# )

# 获取工具映射和限制（与传统方式兼容）
# tools_map = tool_config.get_tools_map()
# tools_limit = tool_config.get_tools_limit()

# 创建模型（通过 ToolConfig）
# llm = tool_config.create_llm(enable_search=False, enable_thinking=False)


# =============================================================================
# 方式3：直接使用 llm_factory（最灵活）
# =============================================================================
from .llm_factory import create_qwen_llm, create_llm_factory


# 直接创建 LLM 实例
# llm = create_qwen_llm(
#     api_key=None,  # 从环境变量读取
#     model="qwen-plus",
#     enable_search=False,
#     enable_thinking=True
# )

# 创建 LLM 工厂函数（推荐用于 Executor）
# llm_factory = create_llm_factory(
#     model_type="qwen",
#     model="qwen-plus"
# )
# 使用时: llm = llm_factory()


# =============================================================================
# 使用示例
# =============================================================================
if __name__ == "__main__":
    print("传统方式:")
    print(f"  tools_map: {tools_map}")
    print(f"  tools_limit: {tools_limit}")

    print("\n使用 ToolConfig 类:")
    print(f"  {tool_config}")
    print(f"  工具列表: {tool_config.list_tools()}")
    print(f"  工具信息: {tool_config.get_tool_info()}")

    print("\n使用 llm_factory:")
    factory = create_llm_factory(model_type="qwen", model="qwen-plus")
    print(f"  工厂函数: {factory}")
    print(f"  调用工厂将返回 LLM 实例")
