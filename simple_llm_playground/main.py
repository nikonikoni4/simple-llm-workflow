from simple_llm_playground.server.executor_manager import executor_manager
import os
from typing import Optional, Type, Callable
from langchain_openai import ChatOpenAI
from langchain_core.language_models.chat_models import BaseChatModel
# 1. 设置 LLM 工厂

# =============================================================================
# 通用 LLM 工厂函数
# =============================================================================

def create_llm_factory(
    model: str = "qwen-plus-2025-12-01",
    api_key: Optional[str] = None,
    chat_model: Type[BaseChatModel] = ChatOpenAI, 
    enable_search: bool = False,
    enable_thinking: bool = False,
    **base_kwargs
) -> Callable[..., BaseChatModel]:
    """
    创建 LLM 工厂函数，返回的 callback 可创建新的 BaseChatModel 实例

    预先配置 api_key 和 model，返回的 callback 只需要传入 temperature 等运行时参数。

    Args:
        model: 模型名称，默认 qwen-plus-2025-12-01
        api_key: API密钥，如果为None则从环境变量读取
        enable_search: 是否启用联网搜索
        enable_thinking: 是否启用思考模式
        **base_kwargs: 其他预配置的参数

    Returns:
        返回一个函数，调用时传入 temperature 等参数即可创建新实例

    Example:
        >>> factory = create_llm_factory(model="qwen-plus")
        >>> llm1 = factory(temperature=0.3)  # 创建低温实例
        >>> llm2 = factory(temperature=0.9)  # 创建高温实例
    """
    # 获取 API key
    if api_key is None:
        api_key = os.getenv("DASHSCOPE_API_KEY") or os.getenv("OPENAI_API_KEY")

    # 預配置参数
    base_config = {
        "model": model,
        "api_key": api_key,
        "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
    }
    
    if not issubclass(chat_model, BaseChatModel):
        raise ValueError(f"chat_model 必须是 BaseChatModel 的子类，但收到了: {chat_model}")

    if enable_search:
        base_config["enable_search"] = True
    if enable_thinking:
        base_config["enable_thinking"] = True

    base_config.update(base_kwargs)

    def callback(
        temperature: float = 0.7,
        **kwargs
    ) -> BaseChatModel:
        """创建新的 LLM 实例"""
        config = {**base_config, "temperature": temperature}
        config.update(kwargs)
        return chat_model(**config)

    return callback

def setup_llm_factory():
    # api_key = "your_api_key"
    # model = "gpt-4o"
    # llm_factory = create_llm_factory(model,api_key,chat_model=ChatOpenAI)
    llm_factory = create_llm_factory(chat_model=ChatOpenAI)
    executor_manager.set_llm_factory(llm_factory)

 
# 2. 设置工具
# from your_path import ( tools )
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
    @tool
    def get_daily_stats(module: str = "all"):
        """
        获取今日统计数据。
        参数 module 可选值:
        - 'all': 获取全部数据
        - 'active_distribution': 1. 电脑使用时间占比
        - 'behavior_stats': 2. 行为数据统计
        - 'target_investment': 3. 目标时间投入
        - 'task_status': 4. 今日重点与任务
        - 'comparison': 5. 与前一天对比
        """
        sections = {
            "active_distribution": """1. 电脑使用时间占比
    电脑使用时间：
    - 0~1 : 0.0
    - 1~2 : 0.0
    - 2~3 : 0.0
    - 3~4 : 0.0
    - 4~5 : 0.0
    - 5~6 : 0.0
    - 6~7 : 0.0
    - 7~8 : 0.15
    - 8~9 : 0.42
    - 9~10 : 0.88
    - 10~11 : 0.95
    - 11~12 : 0.78
    - 12~13 : 0.22
    - 13~14 : 0.85
    - 14~15 : 0.91
    - 15~16 : 0.89
    - 16~17 : 0.84
    - 17~18 : 0.76
    - 18~19 : 0.45
    - 19~20 : 0.62
    - 20~21 : 0.88
    - 21~22 : 0.93
    - 22~23 : 0.81
    - 23~24 : 0.12""",
            
            "behavior_stats": """2. 行为数据统计
    - 时段1（2026-02-14 00:00:00 至 2026-02-14 05:59:59）
        - 分类占比:
        - 电脑空闲时间: 5小时59分钟（100.0%）
    - 时段2（2026-02-14 05:59:59 至 2026-02-14 11:59:59）
        - 分类占比:
        - 工作/学习: 4小时12分钟（70.0%）
            - 编程: 3小时25分钟（56.9%）
            - 文档撰写: 35分钟（9.7%）
            - 沟通: 12分钟（3.4%）
        - 电脑空闲时间: 1小时28分钟（24.4%）
        - 其他: 20分钟（5.6%）
        - 主要活动记录:
        - nebula-core - architecture - design_doc.md（vscode）: 45分钟
        - nebula-core - engine - optimizer.py（vscode）: 32分钟
        - nebula-explorer（msedge）: 18分钟
        - terminal - build engine（powershell）: 12分钟
        - slack - team sync（slack）: 10分钟
    - 时段3（2026-02-14 11:59:59 至 2026-02-14 17:59:59）
        - 分类占比:
        - 工作/学习: 3小时45分钟（62.5%）
            - 编程: 3小时10分钟（52.8%）
            - 调试: 25分钟（6.9%）
            - 计划: 10分钟（2.8%）
        - 电脑空闲时间: 1小时35分钟（26.4%）
        - 娱乐: 40分钟（11.1%）
            - 音乐: 40分钟（11.1%）
        - 主要活动记录:
        - nebula-core - tests - test_optimizer.py（vscode）: 55分钟
        - stackoverflow - python profile optimization（msedge）: 20分钟
        - nebula-core - engine - pipeline.py（vscode）: 15分钟
        - spotify（spotify）: 40分钟
        - jira - sprint planning（msedge）: 10分钟
    - 时段4（2026-02-14 17:59:59 至 2026-02-14 23:59:59）
        - 分类占比:
        - 娱乐: 3小时15分钟（54.2%）
            - 游戏: 2小时45分钟（45.8%）
            - 社交: 30分钟（8.4%）
        - 工作/学习: 1小时10分钟（19.4%）
            - 编程: 1小时10分钟（19.4%）
        - 电脑空闲时间: 1小时35分钟（26.4%）
        - 主要活动记录:
        - Cyberpunk 2077（game_exe）: 2小时20分钟
        - Discord - gaming community（discord）: 30分钟
        - nebula-core - hotfix - bug_fix.py（vscode）: 25分钟
        - Youtube - tech reviews（msedge）: 25分钟""",

            "target_investment": """3. 目标时间投入
    - 完成Nebula核心引擎: 8小时47分钟""",

            "task_status": """4. 今日重点与任务
    - focus : 1. 优化查询执行器性能
    2. 编写集成测试报告
    3. 重构日志管理模块
    - todos: 85%
    1. 修复内存泄露问题 completed
    2. 实现查询缓存机制 completed
    3. 补充文档注释 in_progress""",

            "comparison": """5. 与前一天对比
    ### 分类时间变化
    | 分类 | 上周期 | 本周期 | 变化 |
    |------|--------|--------|------|
    | 工作/学习 | 7.5h | 9.1h | +21.3% |
    | 娱乐 | 2.5h | 3.9h | +56.0% |
    | 其他 | 1.8h | 1.0h | -44.4% |

    ### 目标投入变化
    - 完成Nebula核心引擎: 6.8h → 8.8h (+2.0h)"""
        }

        if module == "all":
            return "\n\n".join(sections.values())
        
        return sections.get(module, f"错误: 未找到模块 '{module}'。可用选项: {list(sections.keys())}")

    executor_manager.register_tool("add", add)
    executor_manager.register_tool("multiply", multiply)
    executor_manager.register_tool("get_daily_stats", get_daily_stats)



# 3. 运行后端服务
if __name__ == "__main__":
    import uvicorn
    from simple_llm_playground.server.backend_api import app
    from simple_llm_playground.server.executor_manager import executor_manager
    from simple_llm_playground import config
    # 1. 设置 LLM 工厂
    setup_llm_factory()

    # 2. 设置工具
    setup_test_tools()

    # 3. 运行后端服务
    # 获取端口配置，如果 config.py 中没有定义则使用默认值 8001
    port = getattr(config, "BACKEND_PORT", 8001)
    
    print(f"🚀 Starting Backend Server from main.py on port {port}...")
    print(f"✅ Tools registered: {list(executor_manager._tools_registry.keys())}")
    
    uvicorn.run(app, host="0.0.0.0", port=port)