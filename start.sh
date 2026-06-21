#!/usr/bin/env bash
set -e
cd "$(dirname "$0")"

DEV_MODE=0
if [ "$1" = "--dev" ] || [ "$1" = "-d" ]; then
    DEV_MODE=1
fi

echo
echo "╔══════════════════════════════════╗"
echo "║     CCConfigManager 启动         ║"
[ "$DEV_MODE" = 1 ] && echo "║     开发模式 (热重载)            ║"
echo "╚══════════════════════════════════╝"
echo

# Python
python3 --version >/dev/null 2>&1 || { echo "[错误] 未找到 Python 3.10+"; exit 1; }

if [ ! -d "venv" ]; then
    echo "[1/5] 创建 Python 虚拟环境..."
    python3 -m venv venv
fi

echo "[2/5] 安装 Python 依赖..."
source venv/bin/activate
pip install -e . -q

# Node.js
if command -v node &>/dev/null; then
    if [ ! -d "node_modules" ]; then
        echo "[3/5] 安装前端依赖..."
        npm install || true
    fi

    if [ "$DEV_MODE" = 1 ]; then
        echo "[4/5] 开发模式 — 跳过前端构建"
        echo "[5/5] 启动后端服务..."
        echo
        echo "后端已启动 → http://localhost:8900"
        echo "在另一个终端运行: npm run dev"
        echo "前端开发服务器 → http://localhost:8920"
        if [ -d "venv" ]; then
            source venv/bin/activate
            python3 -m ccconfigmanager
        else
            python3 -m ccconfigmanager
        fi
        exit 0
    fi

    echo "[4/5] 构建前端..."
    npm run build || echo "构建跳过"
else
    echo "[警告] 未找到 Node.js，使用旧版前端"
fi

echo "[5/5] 启动服务..."
echo
echo "已启动 → http://localhost:8900"

if [ -d "venv" ]; then
    source venv/bin/activate
    ccpm
else
    python3 -m ccconfigmanager
fi
