#!/usr/bin/env bash
set -e
echo "=== CCConfigManager 安装 ==="

python3 --version >/dev/null 2>&1 || { echo "[错误] 未找到 Python 3"; exit 1; }

if [ ! -d venv ]; then
    echo "[1/3] 创建虚拟环境..."
    python3 -m venv venv
fi

echo "[2/3] 安装..."
source venv/bin/activate
pip install -e . -q

echo "[3/3] 创建启动脚本..."
cat > start.sh << 'SCRIPT'
#!/usr/bin/env bash
cd "$(dirname "$0")"
source venv/bin/activate
echo "CCConfigManager → http://127.0.0.1:8900"
ccpm
SCRIPT
chmod +x start.sh

echo "=== 完成 ==="
echo "运行 ./start.sh 启动 → http://127.0.0.1:8900"
