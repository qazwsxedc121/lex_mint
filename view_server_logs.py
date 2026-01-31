"""View server logs utility"""

import sys
from pathlib import Path

def view_logs(lines: int = 50):
    """View the latest server logs.

    Args:
        lines: Number of lines to display (default: 50, 0 for all)
    """
    log_file = Path("logs/server.log")

    if not log_file.exists():
        print("No log file found. Server hasn't been started yet.")
        print(f"Expected location: {log_file.absolute()}")
        return

    print(f"Reading from: {log_file.absolute()}")
    print("=" * 80)

    try:
        with open(log_file, 'r', encoding='utf-8') as f:
            if lines == 0:
                # Read all lines
                content = f.read()
                print(content)
            else:
                # Read last N lines
                all_lines = f.readlines()
                recent_lines = all_lines[-lines:] if len(all_lines) > lines else all_lines
                print(''.join(recent_lines))
    except Exception as e:
        print(f"Error reading log file: {e}")

if __name__ == "__main__":
    # Parse command line arguments
    if len(sys.argv) > 1:
        try:
            lines = int(sys.argv[1])
            view_logs(lines)
        except ValueError:
            print("Usage: python view_server_logs.py [lines]")
            print("  lines: Number of lines to display (default: 50, 0 for all)")
    else:
        view_logs()
