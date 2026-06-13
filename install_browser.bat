@echo off
REM ============================================================
REM  Playwright Chromium 浏览器安装脚本 (国内镜像版)
REM  Usage: 双击运行，或在命令行执行 install_browser.bat
REM ============================================================

echo.
echo ============================================================
echo   正在安装 Playwright 浏览器（使用国内镜像）...
echo   Installing Playwright Chromium (China mirror)...
echo ============================================================
echo.

REM 设置环境变量（只对当前脚本生效）
set PLAYWRIGHT_DOWNLOAD_HOST=https://playwright-zh.oss-cn-hangzhou.aliyuncs.com
set npm_config_registry=https://registry.npmmirror.com
set PLAYWRIGHT_BROWSERS_PATH=%USERPROFILE%\.cache\ms-playwright

echo [步骤 1/3] 检查 Python 和 Playwright...
where python >nul 2>nul
if errorlevel 1 (
    echo [错误] 未检测到 Python，请先安装 Python 3.9+
    echo [ERROR] Python not detected. Please install Python 3.9+
    pause
    exit /b 1
)

python -c "import playwright" 2>nul
if errorlevel 1 (
    echo   playwright 未安装，正在安装...
    python -m pip install -i https://pypi.tuna.tsinghua.edu.cn/simple playwright
    if errorlevel 1 (
        echo [错误] playwright 安装失败
        pause
        exit /b 1
    )
)
echo   ✓ Python 和 Playwright 正常
echo.

echo [步骤 2/3] 运行安装脚本...
python "%~dp0install_browser.py"
set RESULT=%ERRORLEVEL%
echo.

if %RESULT% EQU 0 (
    echo ============================================================
    echo   ✓ 浏览器安装成功！
    echo   现在可以运行 GUI: python gui_downloader.py
    echo   或打包: build_exe.bat
    echo ============================================================
) else (
    echo ============================================================
    echo   ✗ 安装失败，请检查上方日志
    echo   Installation failed, check logs above
    echo ============================================================
)
echo.
pause
