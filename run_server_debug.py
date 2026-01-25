"""完全不用 uvicorn - 使用 hypercorn (另一个 ASGI 服务器)"""

import sys
import io
import asyncio

# Fix encoding
if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

from dotenv import load_dotenv
load_dotenv()

from src.api.logging_config import setup_logging
setup_logging()

print("=" * 80)
print("使用内置服务器运行 (调试模式)")
print("=" * 80)

from src.api.main import app
import socket

def is_port_in_use(port):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex(('localhost', port)) == 0

if __name__ == "__main__":
    port = 8000

    if is_port_in_use(port):
        print(f"⚠️  警告: 端口 {port} 已被占用!")
        print(f"   请先关闭占用端口的进程")
        print(f"   或修改端口号")
        import sys
        sys.exit(1)

    print(f"\n✅ 端口 {port} 可用")
    print(f"📡 启动服务器: http://0.0.0.0:{port}")
    print(f"🌐 前端连接: http://localhost:{port}")
    print("=" * 80)
    print()

    # 使用 uvicorn 但带所有可能的日志选项
    import uvicorn

    # 配置
    config = uvicorn.Config(
        app=app,
        host="0.0.0.0",
        port=port,
        log_level="trace",  # 最详细的日志级别
        access_log=True,
        use_colors=True,
        reload=True,
        reload_dirs=["src"],
    )

    server = uvicorn.Server(config)

    # 添加启动前的打印
    print("🚀 服务器正在启动...")
    print("📝 所有 HTTP 请求都会显示在下面")
    print("=" * 80)
    print()

    try:
        server.run()
    except KeyboardInterrupt:
        print("\n\n服务器已停止")
