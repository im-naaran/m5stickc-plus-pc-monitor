from __future__ import annotations

import asyncio
import platform

from commands.context import CommandContext


OP_CODE = "OP-WIN-NEXT"


def _next_window_keys() -> tuple[str, ...]:
    if platform.system() == "Darwin":
        return ("command", "tab")

    return ("alt", "tab")


async def run(context: CommandContext) -> None:
    import pyautogui

    await asyncio.to_thread(pyautogui.hotkey, *_next_window_keys())
    context.logger.info("executed next window")
