from __future__ import annotations

import asyncio
import platform

from commands.context import CommandContext


OP_CODE = "OP-CP"


def _copy_keys() -> tuple[str, ...]:
    if platform.system() == "Darwin":
        return ("command", "c")

    return ("ctrl", "c")


async def run(context: CommandContext) -> None:
    import pyautogui

    await asyncio.to_thread(pyautogui.hotkey, *_copy_keys())
    context.logger.info("executed copy")
