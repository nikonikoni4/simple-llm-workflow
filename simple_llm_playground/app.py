"""
Simple LLM Playground - 统一入口

这是打包成exe后的主入口文件。
同时启动后端服务（FastAPI）和前端UI（PyQt5）。

用法：
1. 将 simple-llm-playground.exe 放到你的项目目录
2. 创建 tools_config.py 文件定义你的tools
3. 双击 exe 启动
"""

import sys
import os
import threading
import time
from pathlib import Path

# 确保能找到包
if getattr(sys, 'frozen', False):
    # 打包后的exe
    BASE_DIR = Path(sys.executable).parent
else:
    # 开发模式
    BASE_DIR = Path(__file__).parent.parent

# 将工作目录切换到exe所在位置（或当前目录）
os.chdir(BASE_DIR)


def start_backend(port: int = 8001):
    """启动后端服务"""
    import uvicorn
    from simple_llm_playground.server.backend_api import app
    
    # 禁用uvicorn的日志输出到stdout（避免打包后的窗口问题）
    config = uvicorn.Config(
        app, 
        host="127.0.0.1",  # 只监听本地
        port=port,
        log_level="warning"
    )
    server = uvicorn.Server(config)
    server.run()


def start_frontend():
    """启动前端UI"""
    from PyQt5.QtWidgets import QApplication
    from simple_llm_playground.qt_front.main_ui import MainWindow
    from simple_llm_playground.qt_front.utils import DARK_STYLESHEET
    
    app = QApplication(sys.argv)
    app.setStyleSheet(DARK_STYLESHEET)
    
    window = MainWindow()
    window.show()
    
    sys.exit(app.exec_())


def setup_from_config():
    """从 tools_config.py 加载配置"""
    from simple_llm_playground.tool_loader import find_tools_config, load_tools_from_file
    from simple_llm_playground.server.executor_manager import executor_manager
    from simple_llm_playground.main import create_llm_factory, setup_test_tools
    
    # 查找并加载配置文件
    config_path = find_tools_config()
    
    if config_path:
        config = load_tools_from_file(config_path)
        
        # 注册tools
        for name, tool in config["tools"].items():
            executor_manager.register_tool(name, tool)
        
        # 设置LLM工厂
        if config["llm_factory"]:
            executor_manager.set_llm_factory(config["llm_factory"])
        elif config["llm_config"]:
            # 从配置创建LLM工厂
            llm_factory = create_llm_factory(**config["llm_config"])
            executor_manager.set_llm_factory(llm_factory)
        else:
            # 使用默认LLM配置
            llm_factory = create_llm_factory()
            executor_manager.set_llm_factory(llm_factory)
    else:
        # 没有找到配置文件，使用内置测试工具
        from simple_llm_playground.main import setup_llm_factory
        setup_llm_factory()
        setup_test_tools()


def main():
    """主入口"""
    import traceback
    
    try:
        print("=" * 60)
        print("  Simple LLM Playground")
        print("=" * 60)
        print()
        
        # 加载配置
        print("📦 正在加载配置...")
        setup_from_config()
        print()
        
        # 从config获取端口
        try:
            from simple_llm_playground import config
            port = getattr(config, "BACKEND_PORT", 8001)
        except:
            port = 8001
        
        # 在后台线程启动后端
        print(f"🚀 正在启动后端服务 (端口 {port})...")
        backend_thread = threading.Thread(target=start_backend, args=(port,), daemon=True)
        backend_thread.start()
        
        # 等待后端启动
        time.sleep(1.5)
        
        # 启动前端（阻塞主线程）
        print("🎨 正在启动前端UI...")
        print()
        start_frontend()
        
    except Exception as e:
        print()
        print("=" * 60)
        print("  ❌ 程序启动失败！")
        print("=" * 60)
        print()
        print("错误信息：")
        print(str(e))
        print()
        print("详细堆栈：")
        traceback.print_exc()
        print()
        print("=" * 60)
        input("按回车键退出...")
        sys.exit(1)


if __name__ == "__main__":
    main()
