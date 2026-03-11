"""Centralized logging configuration module"""

from datetime import datetime
import logging
import sys
from pathlib import Path

from src.core.paths import logs_dir

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
        self.file = open(self.file_path, 'a', encoding='utf-8', buffering=1)

    def write(self, message):
        """Write to both console and file"""
        if self.original_stream:
            try:
                self.original_stream.write(message)
                self.original_stream.flush()
            except Exception:
                pass

        if self.file and not self.file.closed:
            try:
                self.file.write(message)
                self.file.flush()
            except Exception:
                pass

    def flush(self):
        """Flush both streams"""
        if self.original_stream:
            try:
                self.original_stream.flush()
            except Exception:
                pass
        if self.file and not self.file.closed:
            try:
                self.file.flush()
            except Exception:
                pass

    def close(self):
        """Close file"""
        if self.file and not self.file.closed:
            self.file.close()


def rotate_logs(logs_directory: Path, base_name: str = "server.log", keep_count: int = 3):
    """Manually rotate log files (keep latest N files)"""
    current_log = logs_directory / base_name

    if not current_log.exists() or current_log.stat().st_size < 10 * 1024 * 1024:
        return

    oldest = logs_directory / f"{base_name}.{keep_count}"
    if oldest.exists():
        oldest.unlink()

    for index in range(keep_count - 1, 0, -1):
        old_file = logs_directory / f"{base_name}.{index}"
        new_file = logs_directory / f"{base_name}.{index + 1}"
        if old_file.exists():
            old_file.rename(new_file)

    backup_file = logs_directory / f"{base_name}.1"
    current_log.rename(backup_file)


def setup_logging():
    """Configure application logging system and redirect stdout/stderr"""
    global _initialized

    if _initialized:
        return

    logs_directory = logs_dir()
    logs_directory.mkdir(parents=True, exist_ok=True)

    rotate_logs(logs_directory)

    log_file = logs_directory / "server.log"

    with open(log_file, 'a', encoding='utf-8') as file_handle:
        file_handle.write("\n" + "=" * 100 + "\n")
        file_handle.write(f"Server started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        file_handle.write("=" * 100 + "\n\n")

    stdout_tee = TeeOutput(log_file, sys.stdout)
    stderr_tee = TeeOutput(log_file, sys.stderr)

    stdout_tee.open()
    stderr_tee.open()

    sys.stdout = stdout_tee
    sys.stderr = stderr_tee

    console_handler = logging.StreamHandler(stdout_tee)
    console_handler.setLevel(logging.INFO)
    console_formatter = logging.Formatter(
        '[%(asctime)s] [%(levelname)s] %(name)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    console_handler.setFormatter(console_formatter)

    logging.basicConfig(
        level=logging.INFO,
        handlers=[console_handler],
        force=True
    )

    logging.getLogger('src').setLevel(logging.INFO)
    logging.getLogger('llm_interactions').setLevel(logging.INFO)

    logging.getLogger('uvicorn.access').setLevel(logging.WARNING)
    logging.getLogger('uvicorn.error').setLevel(logging.WARNING)
    logging.getLogger('uvicorn').setLevel(logging.WARNING)
    logging.getLogger('httpx').setLevel(logging.WARNING)
    logging.getLogger('httpcore').setLevel(logging.WARNING)

    _initialized = True

    print("=" * 80)
    print("Logging system initialized")
    print(f"All output (stdout/stderr) will be saved to: {log_file.absolute()}")
    print("Log rotation: max 10MB per file, keep 3 backups")
    print("=" * 80)
