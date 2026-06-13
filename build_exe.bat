@echo off
REM ============================================================
REM  抖音 / TikTok 批量下载器 GUI - Windows 可执行文件打包脚本
REM  Usage: 双击运行，或在 cmd 中执行 build_exe.bat
REM ============================================================

setlocal enabledelayedexpansion

echo ============================================================
echo   抖音 / TikTok 批量下载器 GUI - 打包脚本
echo   Douyin / TikTok Batch Downloader GUI - Build Script
echo ============================================================
echo.

REM ------------------------------------------------------------
REM  Step 1: 检查 Python 是否可用
REM ------------------------------------------------------------
where python >nul 2>nul
if errorlevel 1 (
    echo [ERROR] 未检测到 Python，请先安装 Python 3.9+。
    echo [ERROR] Python not detected. Please install Python 3.9+.
    pause
    exit /b 1
)

echo [Step 1] 检查 Python 环境...
python --version
if errorlevel 1 (
    echo [ERROR] python --version 失败。
    pause
    exit /b 1
)
echo   OK
echo.

REM ------------------------------------------------------------
REM  Step 2: 检查并安装依赖
REM ------------------------------------------------------------
echo [Step 2] 检查依赖包 (playwright / Pillow / pyinstaller)...

python -c "import playwright" 2>nul
if errorlevel 1 (
    echo   - playwright 未安装，正在安装...
    python -m pip install playwright
) else (
    echo   - playwright: OK
)

python -c "import PIL" 2>nul
if errorlevel 1 (
    echo   - Pillow 未安装，正在安装...
    python -m pip install Pillow
) else (
    echo   - Pillow: OK
)

python -c "import PyInstaller" 2>nul
if errorlevel 1 (
    echo   - pyinstaller 未安装，正在安装...
    python -m pip install pyinstaller
) else (
    echo   - pyinstaller: OK
)
echo.

REM ------------------------------------------------------------
REM  Step 3: 清理旧的打包产物
REM ------------------------------------------------------------
echo [Step 3] 清理旧的打包产物...
if exist "dist" (
    echo   - 删除 dist 目录
    rmdir /s /q "dist"
)
if exist "build" (
    echo   - 删除 build 目录
    rmdir /s /q "build"
)
if exist "MediaDownloader_GUI.spec" (
    echo   - 删除 .spec 文件
    del /q "MediaDownloader_GUI.spec"
)
echo   OK
echo.

REM ------------------------------------------------------------
REM  Step 4: PyInstaller 打包
REM  --onefile      单文件输出
REM  --noconsole    不显示命令行窗口 (GUI 应用)
REM  --name         输出文件名
REM  --collect-all  确保 playwright / PIL 的所有资源被打包
REM  --clean        构建前清理缓存
REM  --noconfirm    覆盖输出不提示
REM ------------------------------------------------------------
echo [Step 4] 开始打包 (PyInstaller)...
echo   这可能需要 1-3 分钟，请耐心等待...
echo.

python -m PyInstaller ^
    --noconfirm ^
    --onefile ^
    --noconsole ^
    --name "MediaDownloader_GUI" ^
    --collect-all playwright ^
    --collect-all PIL ^
    --clean ^
    gui_downloader.py

if errorlevel 1 (
    echo.
    echo [ERROR] 打包失败！请检查上方日志获取详细信息。
    echo [ERROR] Build failed! Check logs above for details.
    pause
    exit /b 1
)

echo.
echo ============================================================
echo   打包成功！
echo   Build succeeded!
echo ============================================================
echo.
echo   输出文件: dist\MediaDownloader_GUI.exe
echo   Output: dist\MediaDownloader_GUI.exe
echo.
echo   首次运行时，程序会自动安装 Playwright Chromium 浏览器。
echo   On first run, the app will auto-install Playwright Chromium.
echo.
echo   按任意键打开 dist 目录...
pause >nul

REM 打开 dist 目录
if exist "dist" (
    start "" "dist"
)

endlocal
