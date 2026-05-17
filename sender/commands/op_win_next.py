from __future__ import annotations

from commands.context import CommandContext
from system_actions import press_shortcut


OP_CODE = "OP-WIN-NEXT"


async def run(context: CommandContext) -> None:
    await press_shortcut("command down", "tab")
    context.logger.info("executed next window")
