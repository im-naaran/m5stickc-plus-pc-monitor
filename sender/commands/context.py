from __future__ import annotations

from dataclasses import dataclass

from config import Config


@dataclass(frozen=True)
class CommandContext:
    logger: object
    config: Config
