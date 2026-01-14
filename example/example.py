import sys
import os
from os import path
# Add parent directory to sys.path
current_dir = path.dirname(path.abspath(__file__))
parent_dir = path.dirname(current_dir)
project_root = path.dirname(parent_dir)
if project_root not in sys.path:
    sys.path.append(project_root)

from llm_linear_executor.executor import Executor
from llm_linear_executor.os_plan import load_plan_from_template
from llm_linear_executor.llm_factory import create_qwen_llm, create_llm_factory
from langchain_core.tools import tool
from os import path
import logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
__file__ = path.dirname(path.abspath(__file__))
# ==================================================
# 1. 导入你的工具，使用 langchian @tool包装
# 创建工具函数映射
# from your_tools import YourTool
# ==================================================
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

tools_map = {"get_daily_stats": get_daily_stats}
logger.info(f"1. tools_map ✓ : {tools_map}")

# # ==================================================
# # 2. 创建一个langchain的chatmodel
# # ==================================================
# from langchain_openai import ChatOpenAI
# llm = ChatOpenAI()
llm = create_qwen_llm(model="qwen-plus-2025-12-01") 
logger.info(f"2. llm ✓ ")

# # ==================================================
# # 3. 生成一个plan（可选）
# # ==================================================
# 
# 再一个AI IDE中使用plan-creator-zh/en 让模型生成一个plan
# 

# ==================================================
# 4. 加载plan
# ==================================================
plan = load_plan_from_template(
    pattern_name="custom",
    json_path=path.join(__file__, "example.json")
)
logger.info(f"4. load_plan_from_template ✓ : {plan}")

# ==================================================
# 5. 执行plan
# ==================================================
# executor = Executor(
#     user_message="总结今天我做了什么",
#     plan=plan,
#     tools_map=tools_map, # 工具函数映射
#     llm_factory=create_llm_factory(model = "qwen-plus-2025-12-01") # 创建chatmodel的函数工程 
# )
# output = executor.execute()
# logger.info(f"6. executor.execute() ✓ : {output}")
# # 保存输出 (content字段)
# with open(path.join(__file__, "output.md"), "w", encoding="utf-8") as f:
#     f.write(output["content"])



# ==================================================
# 5. 异步调用
# ==================================================

async def main():
    logger.info("-" * 50)
    logger.info("5. 开始异步执行演示 (Async Execution)")
    
    # 重新创建一个 executor 实例 (或者重用上面的配置)
    async_executor = Executor(
        plan=plan,
        tools_map=tools_map,
        llm_factory=create_llm_factory(model="qwen-plus-2025-12-01")
    )
    
    # 使用 await 调用 aexecute()
    result = await async_executor.aexecute()
    logger.info(f"7. async_executor.aexecute() ✓ : {result['content'][:100]}...") # 打印前100个字符
    return result

# 运行异步主函数
if __name__ == "__main__":
  import asyncio
  asyncio.run(main())

