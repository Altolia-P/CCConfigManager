"""Kill process occupying a given port (Windows). Usage: python kill_port.py [port]"""
import subprocess, sys

def kill_port(port: int = 8900) -> str:
    try:
        out = subprocess.check_output(
            f'netstat -ano | findstr :{port}', shell=True, text=True
        )
        pids = set()
        for line in out.strip().split('\n'):
            parts = line.strip().split()
            if len(parts) >= 5 and 'LISTENING' in line:
                pids.add(parts[-1])
        if not pids:
            return f"端口 {port} 未被占用"
        for pid in pids:
            subprocess.run(f'taskkill /F /PID {pid}', shell=True,
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return f"已释放端口 {port} (killed PIDs: {', '.join(pids)})"
    except subprocess.CalledProcessError:
        return f"端口 {port} 未被占用"

if __name__ == '__main__':
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8900
    print(kill_port(port))
