import logging
from typing import Optional

from langchain_core.tools import tool

from app.background import AsyncBackgroundManager

logger = logging.getLogger(__name__)

# Global instance placeholder (injected at runtime)
background_manager: Optional[AsyncBackgroundManager] = None


@tool
async def backgroundRun(command: str) -> str:
    """Run a shell command in the background and return a task ID immediately.

    Use this when the command may take a long time or should not block
    the current turn.  Check status later with checkBackground.

    Note: On Windows, use "python" instead of "python3".
    """
    if background_manager is None:
        return "Error: Background manager not initialized."
    import platform
    if platform.system() == "Windows":
        command = command.replace("python3", "python")
    result = await background_manager.run(command)
    return result


@tool
async def checkBackground(task_id: Optional[str] = None) -> str:
    """Check the status of a background task.

    Args:
        task_id: Optional task ID. If omitted, lists all tasks.
    """
    if background_manager is None:
        return "Error: Background manager not initialized."
    return background_manager.check(task_id)
