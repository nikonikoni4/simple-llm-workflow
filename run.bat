@echo off
setlocal

:: 设置基础目录为当前批处理文件所在目录
set "BASE_DIR=%~dp0"
cd /d "%BASE_DIR%"

echo [INFO] Init
echo [INFO] Starting Backend Server (main.py)...

start "Simple-LLM-Backend" cmd /k "python -m simple_llm_playground.main"

echo [INFO] Starting Debugger UI...
:: 在新窗口运行前端 UI
start "Simple-LLM-UI" cmd /k "python -m simple_llm_playground.qt_front.main_ui"
 
echo. 
echo ======================================================
echo  Simple LLM Workflow Running
echo ======================================================
echo  [backend] Backend API (port 8001)
echo  [frontend] Debugger UI (PyQt5)
echo.
echo  Please keep the backend window open, otherwise the UI will not work.
echo ======================================================
echo.
pause
