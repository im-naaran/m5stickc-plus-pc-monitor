from __future__ import annotations

from commands.context import CommandContext
from system_actions import press_shortcut


OP_CODE = "OP-CP"


async def run(context: CommandContext) -> None:
    await press_shortcut("command down", "c")
    context.logger.info("executed copy")
