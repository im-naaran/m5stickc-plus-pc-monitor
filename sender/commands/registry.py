from __future__ import annotations

from typing import Awaitable, Callable

from commands import op_cp, op_lock, op_pa, op_win_next
from commands.context import CommandContext


CommandHandler = Callable[[CommandContext], Awaitable[None]]


async def execute(op_code: str, context: CommandContext) -> None:
    handler = COMMANDS.get(op_code)
    if not handler:
        context.logger.warn(f"unknown op: {op_code}")
        return

    try:
        await handler(context)
    except Exception as error:
        context.logger.warn(f"command failed for {op_code}: {error}")


COMMANDS: dict[str, CommandHandler] = {
    op_cp.OP_CODE: op_cp.run,
    op_pa.OP_CODE: op_pa.run,
    op_lock.OP_CODE: op_lock.run,
    op_win_next.OP_CODE: op_win_next.run,
}
