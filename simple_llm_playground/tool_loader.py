"""
动态Tool加载器

从指定目录或文件中加载用户定义的tools。
支持从 tools_config.py 中读取 TOOLS 字典。
"""

import importlib.util
import os
import sys
from pathlib import Path
from typing import Any, Callable


def load_tools_from_file(file_path: str) -> dict[str, Any]:
    """
    从指定的Python文件中加载tools
    
    文件应该导出一个 TOOLS 字典，格式如：
    TOOLS = {
        "tool_name": tool_function,
        ...
    }
    
    也可以导出以下内容：
    - LLM_FACTORY: 可选的LLM工厂函数
    - LLM_CONFIG: 可选的LLM配置字典 (model, api_key, base_url等)
    
    Args:
        file_path: Python文件的路径
        
    Returns:
        包含加载配置的字典: {"tools": {...}, "llm_factory": ..., "llm_config": ...}
    """
    file_path = Path(file_path).resolve()
    
    if not file_path.exists():
        print(f"⚠️ 配置文件不存在: {file_path}")
        return {"tools": {}, "llm_factory": None, "llm_config": None}
    
    if not file_path.suffix == ".py":
        print(f"⚠️ 配置文件必须是.py文件: {file_path}")
        return {"tools": {}, "llm_factory": None, "llm_config": None}
    
    # 将配置文件所在目录添加到sys.path，以便导入用户项目的模块
    config_dir = str(file_path.parent)
    if config_dir not in sys.path:
        sys.path.insert(0, config_dir)
    
    try:
        # 动态加载模块
        spec = importlib.util.spec_from_file_location("tools_config", file_path)
        if spec is None or spec.loader is None:
            print(f"⚠️ 无法加载配置文件: {file_path}")
            return {"tools": {}, "llm_factory": None, "llm_config": None}
        
        module = importlib.util.module_from_spec(spec)
        sys.modules["tools_config"] = module
        spec.loader.exec_module(module)
        
        result = {
            "tools": {},
            "llm_factory": None,
            "llm_config": None
        }
        
        # 读取 TOOLS 字典
        if hasattr(module, "TOOLS"):
            tools = getattr(module, "TOOLS")
            if isinstance(tools, dict):
                result["tools"] = tools
                print(f"✅ 已加载 {len(tools)} 个工具: {list(tools.keys())}")
            else:
                print(f"⚠️ TOOLS 必须是字典，但收到了: {type(tools)}")
        else:
            print(f"⚠️ 配置文件中未找到 TOOLS 字典")
        
        # 读取可选的 LLM_FACTORY
        if hasattr(module, "LLM_FACTORY"):
            result["llm_factory"] = getattr(module, "LLM_FACTORY")
            print(f"✅ 已加载自定义 LLM_FACTORY")
        
        # 读取可选的 LLM_CONFIG
        if hasattr(module, "LLM_CONFIG"):
            result["llm_config"] = getattr(module, "LLM_CONFIG")
            print(f"✅ 已加载 LLM_CONFIG: {list(result['llm_config'].keys())}")
        
        return result
        
    except Exception as e:
        print(f"❌ 加载配置文件时出错: {e}")
        import traceback
        traceback.print_exc()
        return {"tools": {}, "llm_factory": None, "llm_config": None}


TOOLS_CONFIG_TEMPLATE = '''"""
tools_config.py - Tool 配置文件

将此文件放在 simple-llm-playground.exe 同目录下，
定义你要使用的 tools 和 LLM 配置。
"""

# ============================================================================
# 方式1：导入你项目中的tool
# ============================================================================
# from my_project.tools import search_tool, calculate_tool

# ============================================================================
# 方式2：直接定义tool（使用 langchain 的 @tool 装饰器）
# ============================================================================
from langchain_core.tools import tool

@tool
def example_tool(input: str) -> str:
    """示例工具 - 请替换为你自己的tool"""
    return f"你输入了: {input}"


# ============================================================================
# 导出 TOOLS 字典（必须）
# ============================================================================
TOOLS = {
    "example_tool": example_tool,
    # "search": search_tool,
    # "calculate": calculate_tool,
}


# ============================================================================
# 可选：自定义 LLM 配置
# ============================================================================
# LLM_CONFIG = {
#     "model": "gpt-4o",
#     "api_key": "sk-xxx",
#     "base_url": "https://api.openai.com/v1",
# }
'''


def create_tools_config_template(target_path: Path) -> bool:
    """
    创建 tools_config.py 模板文件
    
    Args:
        target_path: 目标文件路径
        
    Returns:
        是否创建成功
    """
    try:
        target_path.write_text(TOOLS_CONFIG_TEMPLATE, encoding="utf-8")
        print(f"✨ 已创建配置文件模板: {target_path}")
        print(f"   请编辑此文件添加你的 tools，然后重新运行程序")
        return True
    except Exception as e:
        print(f"❌ 创建配置文件失败: {e}")
        return False


def find_tools_config(auto_create: bool = True) -> str | None:
    """
    查找 tools_config.py 文件
    
    搜索顺序：
    1. 当前工作目录
    2. exe所在目录（如果是打包后运行）
    3. 脚本所在目录
    
    Args:
        auto_create: 如果找不到配置文件，是否自动创建模板
    
    Returns:
        找到的配置文件路径，如果未找到返回None
    """
    search_paths = [
        Path.cwd() / "tools_config.py",  # 当前工作目录
    ]
    
    # 如果是打包后的exe
    if getattr(sys, 'frozen', False):
        exe_dir = Path(sys.executable).parent
        search_paths.append(exe_dir / "tools_config.py")
    else:
        # 开发模式：脚本所在目录
        script_dir = Path(__file__).parent.parent
        search_paths.append(script_dir / "tools_config.py")
    
    for path in search_paths:
        if path.exists():
            print(f"📁 找到配置文件: {path}")
            return str(path)
    
    # 没有找到配置文件
    if auto_create:
        # 自动在当前工作目录创建模板
        default_path = Path.cwd() / "tools_config.py"
        if create_tools_config_template(default_path):
            return str(default_path)
    
    print(f"ℹ️ 未找到 tools_config.py，使用内置测试工具")
    print(f"   搜索路径: {[str(p) for p in search_paths]}")
    return None
