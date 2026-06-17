#!/usr/bin/env bash
set -e
echo "=== Claude Code Project Manager 安装 ==="

# Check Python
python3 --version >/dev/null 2>&1 || { echo "[错误] 未找到 Python 3"; exit 1; }

# Create venv
if [ ! -d venv ]; then
    echo "[1/3] 创建虚拟环境..."
    python3 -m venv venv
fi

# Install
echo "[2/3] 安装依赖..."
source venv/bin/activate
pip install -r requirements.txt -q

# Create start script
echo "[3/3] 创建启动脚本..."
cat > start.sh << 'SCRIPT'
#!/usr/bin/env bash
cd "$(dirname "$0")"
source venv/bin/activate
echo "Project Manager → http://127.0.0.1:8900"
python app.py
SCRIPT
chmod +x start.sh

echo ""
echo "=== 安装完成 ==="
echo "运行 ./start.sh 启动，浏览器打开 http://127.0.0.1:8900"
