@echo off
cd /d "%~dp0"
echo === CCConfigManager 开发模式 ===
echo.
echo 后端 :8900 ^| 前端 :8920 (HMR)
echo.

start "CC-Backend" cmd /c "python -m ccconfigmanager"
timeout /t 2 /nobreak >nul
start "CC-Frontend" cmd /c "npm run dev"
timeout /t 3 /nobreak >nul
start http://localhost:8920

echo 已启动。关闭窗口停止服务。
