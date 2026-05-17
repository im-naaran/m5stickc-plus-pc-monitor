from __future__ import annotations

from commands.context import CommandContext
from system_actions import press_shortcut


OP_CODE = "OP-PA"


async def run(context: CommandContext) -> None:
    await press_shortcut("command down", "v")
    context.logger.info("executed paste")
