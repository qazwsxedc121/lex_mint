"""Simple and reliable LLM log viewer."""

import json
from pathlib import Path
from datetime import datetime
import sys
import io
import re

# Fix Windows console encoding
if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')


def parse_log_file(log_path):
    """Parse log file and extract JSON entries."""
    with open(log_path, 'r', encoding='utf-8') as f:
        content = f.read()

    # Use regex to find all JSON objects
    json_pattern = r'\{[\s\S]*?"timestamp"[\s\S]*?\}\n(?:=|$)'
    matches = re.finditer(json_pattern, content)

    entries = []
    for match in matches:
        json_str = match.group().rstrip('\n=').strip()
        try:
            data = json.loads(json_str)
            entries.append(data)
        except json.JSONDecodeError as e:
            print(f"Warning: Could not parse JSON: {e}")
            continue

    return entries


def view_logs(log_file=None):
    """View all log entries in summary format."""
    if log_file is None:
        today = datetime.now().strftime("%Y%m%d")
        log_file = f"logs/llm_interactions_{today}.log"

    log_path = Path(log_file)

    if not log_path.exists():
        print(f"❌ 日志文件不存在: {log_file}\n")
        logs_dir = Path("logs")
        if logs_dir.exists():
            log_files = sorted(logs_dir.glob("llm_interactions_*.log"), reverse=True)
            if log_files:
                print("可用的日志文件:")
                for f in log_files:
                    print(f"  - {f.name}")
            else:
                print("还没有日志文件")
        else:
            print("logs/ 目录不存在")
        return

    print(f"\n📖 日志文件: {log_file}")
    print("=" * 100)

    entries = parse_log_file(log_path)

    if not entries:
        print("\n⚠️  没有找到日志记录\n")
        return

    for idx, entry in enumerate(entries, 1):
        print(f"\n🔄 交互 #{idx}")
        print(f"⏰ 时间: {entry['timestamp']}")
        print(f"🆔 会话: {entry['session_id']}")
        print(f"🤖 模型: {entry['model']}")

        request = entry['request']
        print(f"\n📤 发送给 DeepSeek ({request['message_count']} 条消息):")
        print("-" * 100)

        for i, msg in enumerate(request['messages'], 1):
            role = "👤 用户" if msg['type'] == "HumanMessage" else "🤖 助手"
            content = msg['content']
            preview = content[:150] + '...' if len(content) > 150 else content
            print(f"\n{role} - 消息 {i}:")
            print(f"   {preview}")

        response = entry['response']
        content = response['content']
        preview = content[:150] + '...' if len(content) > 150 else content
        print(f"\n📥 DeepSeek 回复:")
        print("-" * 100)
        print(f"🤖 {preview}")

        print("\n" + "=" * 100)

    print(f"\n✅ 共 {len(entries)} 条交互记录\n")


def view_interaction(log_file=None, num=1):
    """View a specific interaction in full detail."""
    if log_file is None:
        today = datetime.now().strftime("%Y%m%d")
        log_file = f"logs/llm_interactions_{today}.log"

    log_path = Path(log_file)

    if not log_path.exists():
        print(f"❌ 日志文件不存在: {log_file}")
        return

    entries = parse_log_file(log_path)

    if num < 1 or num > len(entries):
        print(f"❌ 交互 #{num} 不存在 (共 {len(entries)} 条记录)")
        return

    entry = entries[num - 1]

    print(f"\n{'=' * 100}")
    print(f"完整交互记录 #{num}")
    print(f"{'=' * 100}\n")

    print(f"⏰ 时间: {entry['timestamp']}")
    print(f"🆔 会话ID: {entry['session_id']}")
    print(f"🤖 模型: {entry['model']}\n")

    print("📤 发送的消息:")
    print("-" * 100)
    for i, msg in enumerate(entry['request']['messages'], 1):
        role = "👤 用户" if msg['type'] == "HumanMessage" else "🤖 助手"
        print(f"\n{role} 消息 {i} ({msg['type']}):")
        print(msg['content'])

    print(f"\n{'=' * 100}")
    print("📥 DeepSeek 的完整回复:")
    print("-" * 100)
    print(entry['response']['content'])
    print(f"\n{'=' * 100}\n")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="查看 LLM 交互日志")
    parser.add_argument("-f", "--file", help="日志文件路径")
    parser.add_argument("-i", "--interaction", type=int, help="查看特定交互的完整详情")

    args = parser.parse_args()

    if args.interaction:
        view_interaction(args.file, args.interaction)
    else:
        view_logs(args.file)
