from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from config import Config


class LoggerLike(Protocol):
    def info(self, message: str) -> None: ...
    def warn(self, message: str) -> None: ...


@dataclass(frozen=True)
class CommandContext:
    logger: LoggerLike
    config: Config
