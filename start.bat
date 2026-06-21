@echo off
chcp 65001 >nul
cd /d "%~dp0"
set DEV_MODE=0
if "%1"=="--dev" set DEV_MODE=1
if "%1"=="-d" set DEV_MODE=1

echo.
echo ╔══════════════════════════════════╗
echo ║     CCConfigManager 启动        ║
if %DEV_MODE%==1 echo ║     开发模式 (热重载)           ║
echo ╚══════════════════════════════════╝
echo.

:: === Python ===
python --version >nul 2>&1
if errorlevel 1 (
    echo [错误] 未找到 Python 3.10+
    echo https://www.python.org/downloads/
    pause
    exit /b 1
)

if not exist "venv\Scripts\python.exe" (
    echo [1/5] 创建 Python 虚拟环境...
    python -m venv venv
)

echo [2/5] 安装 Python 依赖...
call venv\Scripts\activate.bat
pip install -e . -q

:: === Node.js ===
node --version >nul 2>&1
if errorlevel 1 (
    echo [警告] 未找到 Node.js，使用旧版前端
    echo https://nodejs.org/
    goto start
)

if not exist "node_modules\" (
    echo [3/5] 安装前端依赖...
    call npm install
    if errorlevel 1 (
        echo npm install 失败
        goto start
    )
)

if %DEV_MODE%==1 (
    echo [4/5] 开发模式 — 跳过前端构建
    echo [5/5] 启动服务...
    echo.
    start "CCConfigManager Backend" cmd /c "python -m ccconfigmanager"
    timeout /t 2 /nobreak >nul
    echo 后端已启动 → http://localhost:8900
    echo.
    echo 在另一个终端运行: npm run dev
    echo 前端开发服务器 → http://localhost:8920
    echo 关闭此窗口不影响服务运行。
    pause
    exit /b 0
)

echo [4/5] 构建前端...
call npm run build
if errorlevel 1 (
    echo 构建失败，使用已有版本
)

:: === Start ===
:start
echo [5/5] 启动服务...
echo.
start "CCConfigManager" cmd /c "python -m ccconfigmanager"
timeout /t 2 /nobreak >nul
start http://localhost:8900

echo 已启动 → http://localhost:8900
echo 关闭此窗口不影响服务运行。
