"""Logger for sending log messages to the logging server."""

import asyncio
import aiohttp

from typing import Any
from typing import List
from typing import Optional

from rich.console import Console

from .enums import LogLevel

from .config import load_logger_config
from .config import DEFAULT_LOG_LEVEL
from .config import DEFAULT_REQUEST_TIMEOUT
from .config import DEFAULT_LOGGER_SERVER_URL


_GLOBAL_LOGGER_CONFIG = load_logger_config()


class MidoriAiLogger:
    """Async-friendly logger that sends log messages to the logging server."""

    def __init__(self, channel: Any, logger_url: Optional[str] = None, log_level: Optional[str] = None, name: Optional[str] = None) -> None:
        """Initialize the logger.

        Args:
            channel: Channel reference (kept for compatibility)
            logger_url: URL of the logging server. Defaults to config value or empty string (disabled)
            log_level: Comma-separated list of log levels to display (e.g., "normal, debug, warn, error")
            name: Logger name prefix for log messages
        """
        self.channel = channel
        self.name = name if name else ""
        self.haschanged = False
        self.last_message = ""
        self.message_history: List[str] = ["Starting Printout"]
        self.console = Console()
        self._configure(logger_url, log_level)

    def _configure(self, logger_url: Optional[str], log_level: Optional[str]) -> None:
        config_logger_url = _GLOBAL_LOGGER_CONFIG.get("logger_server_url")
        resolved_logger_url = DEFAULT_LOGGER_SERVER_URL
        if config_logger_url is not None:
            resolved_logger_url = config_logger_url
        if logger_url is not None:
            resolved_logger_url = logger_url

        config_log_level = _GLOBAL_LOGGER_CONFIG.get("log_level")
        resolved_log_level = DEFAULT_LOG_LEVEL
        if config_log_level is not None:
            resolved_log_level = config_log_level
        if log_level is not None:
            resolved_log_level = log_level

        config_timeout = _GLOBAL_LOGGER_CONFIG.get("request_timeout")
        resolved_timeout = DEFAULT_REQUEST_TIMEOUT
        if config_timeout is not None:
            resolved_timeout = config_timeout

        config_enabled = _GLOBAL_LOGGER_CONFIG.get("enabled", False)

        self.logger_url = resolved_logger_url if config_enabled else ""
        self._log_levels = set(level.strip() for level in resolved_log_level.split(","))
        self._request_timeout = aiohttp.ClientTimeout(total=resolved_timeout)

    def _send_sync(self, prefix: str, message: str, mode: str) -> None:
        if not self.logger_url:
            return
        try:
            try:
                loop = asyncio.get_running_loop()
                loop.create_task(self._send_async(prefix, message, mode))
            except RuntimeError:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                loop.run_until_complete(self._send_async(prefix, message, mode))
        except Exception:
            pass

    async def _send_async(self, prefix: str, message: str, mode: str) -> None:
        if not self.logger_url:
            return
        try:
            async with aiohttp.ClientSession() as session:
                json_obj = {"level": mode, "logger": self.name, "message": f"{prefix}{message}"}
                await session.post(f"{self.logger_url}/log", json=json_obj, timeout=self._request_timeout)
        except Exception:
            pass

    def _format_prefix(self, mode: str) -> str:
        if mode == "error":
            return f"{self.name} ([bold red]ERROR[/bold red]): "
        if mode == "warn":
            return f"{self.name} ([bold yellow]WARN[/bold yellow]): "
        if mode == "debug":
            return f"{self.name} ([bold green]DEBUG[/bold green]): "
        return f"{self.name} (INFO): "

    def true_print(self, message: str, mode: str = "normal") -> str:
        prefix = self._format_prefix(mode)
        if mode in self._log_levels:
            if len(str(message).strip()) > 2:
                self.message_history.append(message)
                self.message_history = self.message_history[-21:]
            self.haschanged = True
            self.console.print(f"{prefix}{message}")
        return prefix

    async def print(self, message: str, mode: str = "normal") -> None:
        prefix = self.true_print(message, mode)
        await self._send_async(prefix, message, mode)

    def rprint(self, message: str, mode: str = "normal") -> None:
        prefix = self.true_print(message, mode)
        self._send_sync(prefix, message, mode)


__all__ = ["MidoriAiLogger", "LogLevel"]
