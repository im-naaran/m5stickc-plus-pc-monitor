from __future__ import annotations

from commands.context import CommandContext
from system_actions import lock_screen


OP_CODE = "OP-LOCK"


async def run(context: CommandContext) -> None:
    await lock_screen()
    context.logger.info("executed lock screen")
