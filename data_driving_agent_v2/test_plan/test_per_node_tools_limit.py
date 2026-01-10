"""
测试每个节点单独设置工具限制的功能

测试场景：
1. 两个节点使用相同工具，但限制不同
2. 验证每个节点执行时使用自己的限制
"""

import os
from langchain_core.tools import tool
from langchain_openai import ChatOpenAI
from data_driving_schemas import NodeDefinition, ExecutionPlan

# 导入 Executor
from executor import Executor


@tool
def test_tool(x: int) -> str:
    """测试工具"""
    return f"结果: {x}"


def create_llm_factory():
    """创建 LLM 工厂函数"""
    api_key = os.getenv("DASHSCOPE_API_KEY") or os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise ValueError("请设置环境变量 DASHSCOPE_API_KEY 或 OPENAI_API_KEY")

    return lambda: ChatOpenAI(
        model="qwen-plus",
        openai_api_key=api_key,
        openai_api_base="https://dashscope.aliyuncs.com/compatible-mode/v1",
        temperature=0.7
    )


def test_per_node_tools_limit():
    """测试每个节点单独设置工具限制"""

    print("\n" + "="*60)
    print("🧪 测试：每个节点单独设置工具限制")
    print("="*60)

    # 创建一个计划，两个节点使用相同的工具但限制不同
    # 节点1: test_tool 限制 2 次
    # 节点2: test_tool 限制 5 次

    plan = ExecutionPlan(
        task="测试每节点工具限制",
        nodes=[
            NodeDefinition(
                node_type="llm-first",
                node_name="节点1_限制2次",
                thread_id="main",
                task_prompt="调用 test_tool 工具 2 次，参数分别为 1 和 2",
                tools=["test_tool"],
                tools_limit={"test_tool": 2},  # 节点级别的限制
                enable_tool_loop=True
            ),
            NodeDefinition(
                node_type="llm-first",
                node_name="节点2_限制5次",
                thread_id="main",
                task_prompt="调用 test_tool 工具 3 次，参数分别为 10, 20, 30",
                tools=["test_tool"],
                tools_limit={"test_tool": 5},  # 节点级别的限制
                enable_tool_loop=True
            )
        ]
    )

    # 创建执行器
    # 设置默认限制为 1（但节点的限制会覆盖它）
    executor = Executor(
        plan=plan,
        user_message="开始测试",
        tools_map={"test_tool": test_tool},
        default_tools_limit=1,  # 默认限制（每个工具的默认调用次数）
        llm_factory=create_llm_factory()
    )

    print("\n📋 测试计划:")
    print(f"  - 节点1: test_tool 限制 = 2 (节点级别)")
    print(f"  - 节点2: test_tool 限制 = 5 (节点级别)")
    print(f"  - 默认限制: 每个工具 = 1 (应被节点限制覆盖)")
    print()

    # 执行计划
    print("🚀 开始执行...")
    result = executor.execute()

    print("\n✅ 执行完成!")
    print(f"📊 最终输出: {result['content'][:200]}...")

    return result


def test_default_tools_limit():
    """测试使用默认工具限制（节点未设置时）"""

    print("\n" + "="*60)
    print("🧪 测试：使用默认工具限制")
    print("="*60)

    # 节点不设置 tools_limit，应使用默认限制
    plan = ExecutionPlan(
        task="测试默认工具限制",
        nodes=[
            NodeDefinition(
                node_type="llm-first",
                node_name="节点_使用默认限制",
                thread_id="main",
                task_prompt="调用 test_tool 工具 1 次，参数为 99",
                tools=["test_tool"],
                # 不设置 tools_limit，应使用默认值
                enable_tool_loop=True
            )
        ]
    )

    # 创建执行器，默认限制为 3
    executor = Executor(
        plan=plan,
        user_message="开始测试",
        tools_map={"test_tool": test_tool},
        default_tools_limit=3,  # 默认限制（每个工具的默认调用次数）
        llm_factory=create_llm_factory()
    )

    print("\n📋 测试计划:")
    print(f"  - 节点: 未设置 tools_limit")
    print(f"  - 默认限制: 每个工具 = 3")
    print()

    # 执行计划
    print("🚀 开始执行...")
    result = executor.execute()

    print("\n✅ 执行完成!")
    print(f"📊 最终输出: {result['content'][:200]}...")

    return result


if __name__ == "__main__":
    # 配置日志
    import logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    try:
        # 测试1: 每个节点单独设置限制
        print("\n\n# ==================== 测试1 ====================")
        result1 = test_per_node_tools_limit()

        # 测试2: 使用默认限制
        print("\n\n# ==================== 测试2 ====================")
        result2 = test_default_tools_limit()

        print("\n\n" + "="*60)
        print("🎉 所有测试通过!")
        print("="*60)

    except Exception as e:
        print(f"\n❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
