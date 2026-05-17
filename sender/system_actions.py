from __future__ import annotations

import asyncio
import platform


async def _run_command(*argv: str, fallback_message: str) -> None:
    process = await asyncio.create_subprocess_exec(
        *argv,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    _, stderr = await process.communicate()
    if process.returncode != 0:
        message = stderr.decode("utf-8", errors="replace").strip()
        raise RuntimeError(message or fallback_message)


async def lock_screen() -> None:
    if platform.system() != "Darwin":
        raise RuntimeError("lock screen is currently implemented for macOS only")

    await _run_command(
        "pmset",
        "displaysleepnow",
        fallback_message="pmset displaysleepnow failed",
    )
