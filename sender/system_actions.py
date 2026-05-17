from __future__ import annotations

import asyncio
import platform


async def press_shortcut(*keys: str) -> None:
    if platform.system() != "Darwin":
        raise RuntimeError("shortcut actions are currently implemented for macOS only")

    modifiers = [key for key in keys[:-1]]
    key = keys[-1]
    modifier_text = ", ".join(modifiers)
    script = f'tell application "System Events" to keystroke "{key}"'
    if modifier_text:
        script += f" using {{{modifier_text}}}"

    process = await asyncio.create_subprocess_exec(
        "osascript",
        "-e",
        script,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    _, stderr = await process.communicate()
    if process.returncode != 0:
        message = stderr.decode("utf-8", errors="replace").strip()
        raise RuntimeError(message or "osascript shortcut failed")


async def lock_screen() -> None:
    if platform.system() != "Darwin":
        raise RuntimeError("lock screen is currently implemented for macOS only")

    process = await asyncio.create_subprocess_exec(
        "pmset",
        "displaysleepnow",
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    _, stderr = await process.communicate()
    if process.returncode != 0:
        message = stderr.decode("utf-8", errors="replace").strip()
        raise RuntimeError(message or "pmset displaysleepnow failed")
