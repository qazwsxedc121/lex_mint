"""完全不用 uvicorn - 使用 hypercorn (另一个 ASGI 服务器)"""

import io
import os
import socket
import sys

# Fix encoding
if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8")

from dotenv import load_dotenv

load_dotenv()

from src.api.logging_config import setup_logging

setup_logging()

print("=" * 80)
print("使用内置服务器运行 (调试模式)")
print("=" * 80)


def is_port_in_use(port):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex(("localhost", port)) == 0


if __name__ == "__main__":
    # 从环境变量读取端口配置（必须设置 API_PORT）
    port_value = os.getenv("API_PORT")
    if not port_value:
        print("❌ 未设置 API_PORT，请在根目录 .env 中配置")
        import sys

        sys.exit(1)
    port = int(port_value)

    if is_port_in_use(port):
        print(f"⚠️  警告: 端口 {port} 已被占用!")
        print("   请先关闭占用端口的进程")
        print("   或在 .env 文件中修改 API_PORT")
        import sys

        sys.exit(1)

    print(f"\n✅ 端口 {port} 可用")
    print(f"📡 启动服务器: http://0.0.0.0:{port}")
    print(f"🌐 前端连接: http://localhost:{port}")
    print("=" * 80)
    print()

    # 使用 uvicorn 但带所有可能的日志选项
    import uvicorn

    # 获取项目根目录的绝对路径
    project_root = os.path.dirname(os.path.abspath(__file__))
    src_dir = os.path.join(project_root, "src")

    # 添加启动前的打印
    print("🚌 服务器正在启动..")
    print("📑 所有 HTTP 请求都会显示在下面")
    print("=" * 80)
    print()

    log_level = os.getenv("UVICORN_LOG_LEVEL", "info")
    try:
        uvicorn.run(
            "src.api.main:app",
            host="0.0.0.0",
            port=port,
            log_level=log_level,
            access_log=True,
            use_colors=True,
            reload=True,
            reload_dirs=[src_dir],
        )
    except KeyboardInterrupt:
        print("\n\n服务器已停止")
