@echo off
setlocal

echo ============================================================
echo   Simple LLM Workflow - Build Script
echo ============================================================
echo.

:: 检查 PyInstaller
python -c "import PyInstaller" 2>nul
if errorlevel 1 (
    echo [INFO] Installing PyInstaller...
    pip install pyinstaller
)

:: 检查 UPX（可选，用于压缩）
where upx >nul 2>&1
if errorlevel 1 (
    echo [WARN] UPX not found. Install it for smaller exe size.
    echo        https://github.com/upx/upx/releases
    echo.
)

:: 执行打包
echo [INFO] Building...
pyinstaller build.spec --clean

echo.
echo ============================================================
if errorlevel 1 (
    echo   BUILD FAILED!
) else (
    echo   BUILD SUCCESS!
    echo   Output: dist\simple-llm-workflow\
    echo.
    echo   Usage:
    echo   1. Copy the entire 'dist\simple-llm-workflow' folder
    echo   2. Create 'tools_config.py' in the same folder
    echo   3. Run 'simple-llm-workflow.exe'
)
echo ============================================================
echo.
pause
