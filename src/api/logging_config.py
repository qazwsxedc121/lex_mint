"""Centralized logging configuration module"""

import logging
import sys
from pathlib import Path
from logging.handlers import RotatingFileHandler
from datetime import datetime

# Whether already initialized
_initialized = False

class TeeOutput:
    """Redirect stdout/stderr to both console and file"""
    def __init__(self, file_path, original_stream):
        self.file = None
        self.file_path = file_path
        self.original_stream = original_stream
        self.encoding = 'utf-8'

    def open(self):
        """Open the log file"""
        self.file = open(self.file_path, 'a', encoding='utf-8', buffering=1)  # Line buffered

    def write(self, message):
        """Write to both console and file"""
        # Write to original stream (console)
        if self.original_stream:
            try:
                self.original_stream.write(message)
                self.original_stream.flush()
            except:
                pass

        # Write to file
        if self.file and not self.file.closed:
            try:
                self.file.write(message)
                self.file.flush()
            except:
                pass

    def flush(self):
        """Flush both streams"""
        if self.original_stream:
            try:
                self.original_stream.flush()
            except:
                pass
        if self.file and not self.file.closed:
            try:
                self.file.flush()
            except:
                pass

    def close(self):
        """Close file"""
        if self.file and not self.file.closed:
            self.file.close()

def rotate_logs(logs_dir: Path, base_name: str = "server.log", keep_count: int = 3):
    """Manually rotate log files (keep latest N files)"""
    current_log = logs_dir / base_name

    # If current log doesn't exist or is small, no need to rotate
    if not current_log.exists() or current_log.stat().st_size < 10 * 1024 * 1024:
        return

    # Delete oldest backup
    oldest = logs_dir / f"{base_name}.{keep_count}"
    if oldest.exists():
        oldest.unlink()

    # Shift existing backups
    for i in range(keep_count - 1, 0, -1):
        old_file = logs_dir / f"{base_name}.{i}"
        new_file = logs_dir / f"{base_name}.{i + 1}"
        if old_file.exists():
            old_file.rename(new_file)

    # Rename current to .1
    backup_file = logs_dir / f"{base_name}.1"
    current_log.rename(backup_file)

def setup_logging():
    """Configure application logging system and redirect stdout/stderr"""
    global _initialized

    if _initialized:
        return

    # Create logs directory
    logs_dir = Path("logs")
    logs_dir.mkdir(exist_ok=True)

    # Rotate logs if needed
    rotate_logs(logs_dir)

    # Get log file path
    log_file = logs_dir / "server.log"

    # Write session separator
    with open(log_file, 'a', encoding='utf-8') as f:
        f.write("\n" + "=" * 100 + "\n")
        f.write(f"Server started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write("=" * 100 + "\n\n")

    # Redirect stdout and stderr to both console and file
    stdout_tee = TeeOutput(log_file, sys.stdout)
    stderr_tee = TeeOutput(log_file, sys.stderr)

    stdout_tee.open()
    stderr_tee.open()

    sys.stdout = stdout_tee
    sys.stderr = stderr_tee

    # Also configure Python logging system
    console_handler = logging.StreamHandler(stdout_tee)
    console_handler.setLevel(logging.INFO)
    console_formatter = logging.Formatter(
        '[%(asctime)s] [%(levelname)s] %(name)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    console_handler.setFormatter(console_formatter)

    # Configure root logger
    logging.basicConfig(
        level=logging.INFO,
        handlers=[console_handler],
        force=True
    )

    # Set log levels for specific modules
    logging.getLogger('src').setLevel(logging.INFO)
    logging.getLogger('llm_interactions').setLevel(logging.INFO)

    # Reduce log level for third-party libraries
    logging.getLogger('uvicorn.access').setLevel(logging.WARNING)
    logging.getLogger('httpx').setLevel(logging.WARNING)
    logging.getLogger('httpcore').setLevel(logging.WARNING)

    _initialized = True

    print("=" * 80)
    print("Logging system initialized")
    print(f"All output (stdout/stderr) will be saved to: {log_file.absolute()}")
    print(f"Log rotation: max 10MB per file, keep 3 backups")
    print("=" * 80)

