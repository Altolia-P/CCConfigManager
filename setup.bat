@echo off
chcp 65001 >nul
echo === CCConfigManager 安装 ===

:: --- Python ---
python --version >nul 2>&1
if errorlevel 1 (
    echo [错误] 未找到 Python 3.10+
    echo https://www.python.org/downloads/
    pause
    exit /b 1
)

if not exist venv (
    echo [1/4] 创建 Python 虚拟环境...
    python -m venv venv
)

echo [2/4] 安装 Python 依赖...
call venv\Scripts\activate.bat
pip install -e . -q

:: --- Node.js ---
node --version >nul 2>&1
if errorlevel 1 (
    echo [警告] 未找到 Node.js，跳过前端构建
    echo https://nodejs.org/
) else (
    echo [3/4] 安装前端依赖...
    call npm install

    echo [4/4] 构建前端...
    call npm run build
)

echo.
echo === 完成 ===
echo 双击 start.bat 启动 → http://127.0.0.1:8900
pause
