# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller 打包配置

用法：
    pyinstaller build.spec

生成的exe会在 dist/ 目录下
"""

import sys
from pathlib import Path

# 项目根目录
ROOT = Path(SPECPATH)

# 主入口
ENTRY_POINT = str(ROOT / 'simple_llm_playground' / 'app.py')

# ============================================================================
# 分析阶段
# ============================================================================
a = Analysis(
    [ENTRY_POINT],
    pathex=[
        str(ROOT),
        str(ROOT / 'llm_linear_executor'),  # submodule 根目录（包含 llm_linear_executor 包）
    ],
    binaries=[],
    
    # 需要包含的数据文件（如果有）
    datas=[
        # (源路径, 目标目录)
        # 例如: ('assets', 'assets'),
    ],
    
    # 隐式导入（PyInstaller可能检测不到的模块）
    hiddenimports=[
        # FastAPI 相关
        'uvicorn.logging',
        'uvicorn.loops',
        'uvicorn.loops.auto',
        'uvicorn.protocols',
        'uvicorn.protocols.http',
        'uvicorn.protocols.http.auto',
        'uvicorn.protocols.websockets',
        'uvicorn.protocols.websockets.auto',
        'uvicorn.lifespan',
        'uvicorn.lifespan.on',
        
        # PyQt5 相关
        'PyQt5.sip',
        'PyQt5.QtCore',
        'PyQt5.QtWidgets',
        'PyQt5.QtGui',
        
        # LangChain 相关
        'langchain_core.tools',
        'langchain_openai',
        
        # 项目模块
        'simple_llm_playground.server.backend_api',
        'simple_llm_playground.server.executor_manager',
        'simple_llm_playground.server.async_executor',
        'simple_llm_playground.qt_front.main_ui',
        'simple_llm_playground.qt_front.graph',
        'simple_llm_playground.qt_front.node_properties',
        'simple_llm_playground.qt_front.context_panel',
        'simple_llm_playground.qt_front.execution_panel',
        'simple_llm_playground.qt_front.api_client',
        'simple_llm_playground.qt_front.utils',
        'simple_llm_playground.schemas',
        'simple_llm_playground.main',
        'simple_llm_playground.tool_loader',
        'simple_llm_playground.config',
        
        # llm_linear_executor 子模块（完整导入）
        'llm_linear_executor',
        'llm_linear_executor.executor',
        'llm_linear_executor.schemas',
        'llm_linear_executor.os_plan',
        'llm_linear_executor.llm_factory',
    ],
    
    # =========================================================================
    # 排除的模块（精简包大小）
    # =========================================================================
    excludes=[
        # 测试相关
        'pytest',
        'pytest_asyncio',
        '_pytest',
        
        # 开发工具
        'black',
        'mypy',
        'isort',
        'flake8',
        'pylint',
        
        # 文档工具
        'sphinx',
        'docutils',
        
        # Jupyter相关（不需要）
        'jupyter',
        'notebook',
        'ipython',
        'IPython',
        'ipykernel',
        'ipywidgets',
        'nbformat',
        'nbconvert',
        
        # 大型科学计算库（如果不需要）
        'numpy',
        'pandas',
        'scipy',
        'matplotlib',
        'PIL',
        'cv2',
        
        # 其他不需要的
        'tkinter',
        'sqlite3',
        'test',
        'tests',
        'unittest',
        'xmlrpc',
        'multiprocessing.dummy',
        
        # 调试工具
        'pdb',
        'cProfile',
        'profile',
    ],
    
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    
    # 不收集的包
    noarchive=False,
)

# ============================================================================
# 打包为单个文件夹（比onefile启动快）
# ============================================================================
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],  # 空列表 = 非onefile模式，生成文件夹
    exclude_binaries=True,  # 二进制文件放在文件夹里
    name='simple-llm-playground',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,  # Windows上不strip
    upx=True,  # 使用UPX压缩
    console=True,  # 显示控制台（方便看日志）
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    
    # 图标（如果有的话）
    icon='asset\icon.ico',
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='simple-llm-playground',
)
