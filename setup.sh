#!/usr/bin/env bash
set -e
echo "=== CCConfigManager 安装 ==="

python3 --version >/dev/null 2>&1 || { echo "[错误] 未找到 Python 3.10+"; exit 1; }

if [ ! -d venv ]; then
    echo "[1/4] 创建虚拟环境..."
    python3 -m venv venv
fi

echo "[2/4] 安装 Python 依赖..."
source venv/bin/activate
pip install -e . -q

# Node.js
if command -v node &>/dev/null; then
    echo "[3/4] 安装前端依赖..."
    npm install

    echo "[4/4] 构建前端..."
    npm run build
else
    echo "[警告] 未找到 Node.js，跳过前端构建"
    echo "  https://nodejs.org/"
fi

echo "=== 完成 ==="
echo "运行 ./start.sh 启动 → http://127.0.0.1:8900"
