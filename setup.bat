@echo off
chcp 65001 >nul
echo === CCConfigManager 安装 ===

python --version >nul 2>&1
if errorlevel 1 (
    echo [错误] 未找到 Python 3.10+
    echo https://www.python.org/downloads/
    pause
    exit /b 1
)

if not exist venv (
    echo [1/3] 创建虚拟环境...
    python -m venv venv
)

echo [2/3] 安装...
call venv\Scripts\activate.bat
pip install -e . -q

echo [3/3] 创建启动脚本...
> start.bat echo @echo off
>> start.bat echo cd /d "%%~dp0"
>> start.bat echo call venv\Scripts\activate.bat
>> start.bat echo start http://127.0.0.1:8900
>> start.bat echo ccpm
>> start.bat echo pause

echo === 完成 ===
echo 双击 start.bat 启动 → http://127.0.0.1:8900
pause
