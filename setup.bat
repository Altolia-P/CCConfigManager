@echo off
chcp 65001 >nul
echo === Claude Code Project Manager 安装 ===
echo.

:: Check Python
python --version >nul 2>&1
if errorlevel 1 (
    echo [错误] 未找到 Python，请先安装 Python 3.10+
    echo 下载: https://www.python.org/downloads/
    pause
    exit /b 1
)

:: Create venv
if not exist venv (
    echo [1/3] 创建虚拟环境...
    python -m venv venv
)

:: Install
echo [2/3] 安装依赖...
call venv\Scripts\activate.bat
pip install -r requirements.txt -q

:: Create start script
echo [3/3] 创建启动脚本...
> start.bat echo @echo off
>> start.bat echo cd /d "%%~dp0"
>> start.bat echo call venv\Scripts\activate.bat
>> start.bat echo echo Project Manager → http://127.0.0.1:8900
>> start.bat echo start http://127.0.0.1:8900
>> start.bat echo python app.py
>> start.bat echo pause

echo.
echo === 安装完成 ===
echo 双击 start.bat 启动，浏览器打开 http://127.0.0.1:8900
echo.
pause
