"""
LLM 工厂函数模块

提供统一的 LLM 模型创建接口，支持多种模型提供商：
- 通义千问 (Qwen/DashScope)
- OpenAI
- 可扩展其他模型

使用示例:
    >>> from llm_factory import create_qwen_llm, create_llm_factory
    >>> llm = create_qwen_llm(api_key="your-key")
    >>> # 或者使用工厂函数
    >>> factory = create_llm_factory(model="qwen-plus")
    >>> llm = factory()
"""

import os
from typing import Callable, Optional

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_openai import ChatOpenAI


# =============================================================================
# 通义千问模型创建
# =============================================================================

def create_qwen_llm(
    api_key: Optional[str] = None,
    model: str = "qwen-plus",
    enable_search: bool = False,
    enable_thinking: bool = False,
    temperature: float = 0.7,
    **kwargs
) -> BaseChatModel:
    """
    创建通义千问模型实例

    Args:
        api_key: API密钥，如果为None则从环境变�� DASHSCOPE_API_KEY 读取
        model: 模型名称，默认 qwen-plus
               可选: qwen-turbo, qwen-plus, qwen-max, qwen-max-longcontext
        enable_search: 是否启用联网搜索（通过模型参数传递）
        enable_thinking: 是否启用思考模式（通过模型参数传递）
        temperature: 温度参数，控制输出随机性，范围 0-1
        **kwargs: 其他传递给 ChatOpenAI 的参数

    Returns:
        LangChain BaseChatModel 实例

    Example:
        >>> llm = create_qwen_llm(api_key="your-key", model="qwen-plus")
        >>> result = llm.invoke("你好")
    """
    # 获取 API key
    if api_key is None:
        api_key = os.getenv("DASHSCOPE_API_KEY") or os.getenv("OPENAI_API_KEY")

    if api_key is None:
        raise ValueError(
            "API key 未提供。请通过参数传入或设置环境变量 "
            "DASHSCOPE_API_KEY / OPENAI_API_KEY"
        )

    # 通义千问兼容 OpenAI API 的基础配置
    config = {
        "model": model,
        "api_key": api_key,
        "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
        "temperature": temperature,
    }

    # 添加可选参数
    if enable_search:
        config["enable_search"] = True
    if enable_thinking:
        # 通义千问的思考模式参数
        config["enable_thinking"] = True

    # 添加额外参数
    config.update(kwargs)

    return ChatOpenAI(**config)


# =============================================================================
# OpenAI 模型创建
# =============================================================================

def create_openai_llm(
    api_key: Optional[str] = None,
    model: str = "gpt-4o-mini",
    temperature: float = 0.7,
    base_url: Optional[str] = None,
    **kwargs
) -> BaseChatModel:
    """
    创建 OpenAI 模型实例

    Args:
        api_key: API密钥，如果为None则从环境变量 OPENAI_API_KEY 读取
        model: 模型名称，默认 gpt-4o-mini
               可选: gpt-4o, gpt-4o-mini, gpt-3.5-turbo 等
        temperature: 温度参数，控制输出随机性
        base_url: API 基础 URL，用于兼容其他 OpenAI 兼容服务
        **kwargs: 其他传递给 ChatOpenAI 的参数

    Returns:
        LangChain BaseChatModel 实例

    Example:
        >>> llm = create_openai_llm(model="gpt-4o")
        >>> result = llm.invoke("Hello")
    """
    # 获取 API key
    if api_key is None:
        api_key = os.getenv("OPENAI_API_KEY")

    if api_key is None:
        raise ValueError(
            "API key 未提供。请通过参数传入或设置环境变量 OPENAI_API_KEY"
        )

    config = {
        "model": model,
        "api_key": api_key,
        "temperature": temperature,
    }

    if base_url:
        config["base_url"] = base_url

    config.update(kwargs)

    return ChatOpenAI(**config)


# =============================================================================
# 通用 LLM 工厂函数
# =============================================================================

def create_llm_factory(
    model_type: str = "qwen",
    model: str = None,
    api_key: Optional[str] = None,
    temperature: float = 0.7,
    **kwargs
) -> Callable[[], BaseChatModel]:
    """
    创建 LLM 工厂函数，用于延迟创建模型实例

    这在需要多次创建相同配置模型的场景很有用，例如在 Executor 中。

    Args:
        model_type: 模型类型，可选 "qwen" 或 "openai"
        model: 模型名称，不同类型有不同默认值
        api_key: API密钥
        temperature: 温度参数
        **kwargs: 其他传递给模型创建函数的参数

    Returns:
        返回一个无参函数，调用时返回模型实例

    Example:
        >>> factory = create_llm_factory(model_type="qwen", model="qwen-plus")
        >>> llm1 = factory()
        >>> llm2 = factory()  # 创建相同配置的新实例
    """
    # 设置默认模型名称
    if model is None:
        model = "qwen-plus" if model_type == "qwen" else "gpt-4o-mini"

    # 根据类型选择创建函数
    if model_type == "qwen":
        creator_kwargs = {
            "api_key": api_key,
            "model": model,
            "temperature": temperature,
            **kwargs
        }
        return lambda: create_qwen_llm(**creator_kwargs)
    elif model_type == "openai":
        creator_kwargs = {
            "api_key": api_key,
            "model": model,
            "temperature": temperature,
            **kwargs
        }
        return lambda: create_openai_llm(**creator_kwargs)
    else:
        raise ValueError(
            f"不支持的 model_type: {model_type}，"
            f"支持的类型: 'qwen', 'openai'"
        )


# =============================================================================
# 便捷函数
# =============================================================================

def get_default_llm(
    model_type: str = None,
    api_key: Optional[str] = None
) -> BaseChatModel:
    """
    获取默认配置的 LLM 实例

    根据环境变量自动选择模型类型：
    - 如果设置了 DASHSCOPE_API_KEY，使用通义千问
    - 如果设置了 OPENAI_API_KEY，使用 OpenAI

    Args:
        model_type: 强制指定模型类型，如果为 None 则自动检测
        api_key: API密钥，如果为 None 则从环境变量读取

    Returns:
        LangChain BaseChatModel 实例
    """
    # 自动检测模型类型
    if model_type is None:
        if os.getenv("DASHSCOPE_API_KEY"):
            model_type = "qwen"
        elif os.getenv("OPENAI_API_KEY"):
            model_type = "openai"
        else:
            raise ValueError(
                "无法自动检测模型类型，请设置环境变量 "
                "DASHSCOPE_API_KEY 或 OPENAI_API_KEY"
            )

    if model_type == "qwen":
        return create_qwen_llm(api_key=api_key)
    elif model_type == "openai":
        return create_openai_llm(api_key=api_key)
    else:
        raise ValueError(f"不支持的 model_type: {model_type}")


# =============================================================================
# 测试代码
# =============================================================================

if __name__ == "__main__":
    print("=" * 60)
    print("测试 LLM 工厂模块")
    print("=" * 60)

    # 测试 1: 创建通义千问模型
    print("\n1. 测试创建通义千问模型:")
    try:
        llm = create_qwen_llm()
        print(f"   模型类型: {type(llm).__name__}")
        print(f"   模型配置: {llm.model_name}")
    except Exception as e:
        print(f"   创建失败: {e}")

    # 测试 2: 创建 OpenAI 模型
    print("\n2. 测试创建 OpenAI 模型:")
    try:
        llm = create_openai_llm()
        print(f"   模型类型: {type(llm).__name__}")
        print(f"   模型配置: {llm.model_name}")
    except Exception as e:
        print(f"   创建失败: {e}")

    # 测试 3: 工厂函数
    print("\n3. 测试工厂函数:")
    try:
        factory = create_llm_factory(model_type="qwen", model="qwen-plus")
        print(f"   工厂函数创建成功: {factory}")
    except Exception as e:
        print(f"   创建失败: {e}")

    # 测试 4: 默认 LLM
    print("\n4. 测试获取默认 LLM:")
    try:
        llm = get_default_llm()
        print(f"   模型类型: {type(llm).__name__}")
    except Exception as e:
        print(f"   获取失败: {e}")

    print("\n" + "=" * 60)
    print("测试完成")
    print("=" * 60)
