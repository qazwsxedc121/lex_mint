"""LLM interaction logger for debugging and auditing."""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import List, Any, Dict


class LLMLogger:
    """Logger for LLM API interactions with detailed request/response tracking."""

    def __init__(self, log_dir: str = "logs"):
        """Initialize LLM logger.

        Args:
            log_dir: Directory to store log files
        """
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(exist_ok=True)

        # Create logger
        self.logger = logging.getLogger("llm_interactions")
        self.logger.setLevel(logging.DEBUG)

        # Prevent duplicate handlers
        if not self.logger.handlers:
            # File handler for detailed JSON logs
            log_file = self.log_dir / f"llm_interactions_{datetime.now().strftime('%Y%m%d')}.log"
            fh = logging.FileHandler(log_file, encoding='utf-8')
            fh.setLevel(logging.DEBUG)

            # Console handler for summary
            ch = logging.StreamHandler()
            ch.setLevel(logging.INFO)

            # Formatters
            file_formatter = logging.Formatter('%(message)s')
            console_formatter = logging.Formatter('[%(levelname)s] %(message)s')

            fh.setFormatter(file_formatter)
            ch.setFormatter(console_formatter)

            self.logger.addHandler(fh)
            self.logger.addHandler(ch)

    def log_interaction(
        self,
        session_id: str,
        messages_sent: List[Any],
        response_received: Any,
        model: str = "deepseek-chat",
        extra_params: Dict[str, Any] = None
    ) -> None:
        """Log a complete LLM interaction.

        Args:
            session_id: Session identifier
            messages_sent: List of messages sent to the LLM
            response_received: Response object from the LLM
            model: Model name used
            extra_params: Additional parameters (reasoning, extra_body, etc.)
        """
        timestamp = datetime.now().isoformat()

        # Convert LangChain messages to dict for logging
        messages_dict = []
        for msg in messages_sent:
            messages_dict.append({
                "type": msg.__class__.__name__,
                "content": msg.content,
                "role": getattr(msg, 'role', getattr(msg, 'type', 'unknown'))
            })

        # Build log entry
        log_entry = {
            "timestamp": timestamp,
            "session_id": session_id,
            "model": model,
            "request": {
                "message_count": len(messages_sent),
                "messages": messages_dict
            },
            "response": {
                "type": response_received.__class__.__name__,
                "content": response_received.content,
                "role": getattr(response_received, 'role', getattr(response_received, 'type', 'unknown'))
            }
        }

        # Add extra params if provided
        if extra_params:
            log_entry["extra_params"] = extra_params

        # Log as formatted JSON
        log_json = json.dumps(log_entry, ensure_ascii=False, indent=2)
        separator = "=" * 80

        self.logger.debug(f"\n{separator}")
        self.logger.debug(f"LLM INTERACTION @ {timestamp}")
        self.logger.debug(separator)
        self.logger.debug(log_json)
        self.logger.debug(f"{separator}\n")

        # Console summary
        self.logger.info(
            f"LLM Call | Session: {session_id[:8]}... | "
            f"Sent: {len(messages_sent)} msgs | "
            f"Received: {len(response_received.content)} chars"
        )

    def log_raw_request(self, session_id: str, raw_data: Dict[str, Any]) -> None:
        """Log raw API request data.

        Args:
            session_id: Session identifier
            raw_data: Raw request data dict
        """
        timestamp = datetime.now().isoformat()
        log_entry = {
            "timestamp": timestamp,
            "type": "RAW_REQUEST",
            "session_id": session_id,
            "data": raw_data
        }
        self.logger.debug(json.dumps(log_entry, ensure_ascii=False, indent=2))

    def log_error(self, session_id: str, error: Exception, context: str = "") -> None:
        """Log LLM interaction error.

        Args:
            session_id: Session identifier
            error: Exception that occurred
            context: Additional context about the error
        """
        timestamp = datetime.now().isoformat()
        log_entry = {
            "timestamp": timestamp,
            "type": "ERROR",
            "session_id": session_id,
            "error": {
                "type": error.__class__.__name__,
                "message": str(error),
                "context": context
            }
        }
        self.logger.error(json.dumps(log_entry, ensure_ascii=False, indent=2))


# Global logger instance
_llm_logger = None


def get_llm_logger() -> LLMLogger:
    """Get or create the global LLM logger instance.

    Returns:
        LLMLogger instance
    """
    global _llm_logger
    if _llm_logger is None:
        _llm_logger = LLMLogger()
    return _llm_logger
