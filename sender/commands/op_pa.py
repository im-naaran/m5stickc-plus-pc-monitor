from __future__ import annotations

import asyncio
import platform

from commands.context import CommandContext


OP_CODE = "OP-PA"


def _paste_keys() -> tuple[str, ...]:
    if platform.system() == "Darwin":
        return ("command", "v")

    return ("ctrl", "v")


async def run(context: CommandContext) -> None:
    import pyautogui

    await asyncio.to_thread(pyautogui.hotkey, *_paste_keys())
    context.logger.info("executed paste")
