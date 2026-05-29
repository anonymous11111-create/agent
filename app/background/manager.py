import asyncio
import json
import logging
import time
import uuid
from pathlib import Path

logger = logging.getLogger(__name__)

RUNTIME_DIR = Path.cwd() / ".runtime-tasks"
RUNTIME_DIR.mkdir(exist_ok=True)
STALL_THRESHOLD_S = 45


class NotificationQueue:
    """
    Priority-based notification queue with same-key folding.

    Folding means a newer message can replace an older message with the
    same key, so the context is not flooded with stale updates.
    """

    PRIORITIES = {"immediate": 0, "high": 1, "medium": 2, "low": 3}

    def __init__(self):
        self._queue: list[tuple[int, str | None, str]] = []
        self._lock = asyncio.Lock()

    async def push(self, message: str, priority: str = "medium", key: str = None):
        """Add a message to the queue, folding if key matches an existing entry."""
        async with self._lock:
            if key:
                self._queue = [(p, k, m) for p, k, m in self._queue if k != key]
            self._queue.append((self.PRIORITIES.get(priority, 2), key, message))
            self._queue.sort(key=lambda x: x[0])

    async def drain(self) -> list[str]:
        """Return all pending messages in priority order and clear the queue."""
        async with self._lock:
            messages = [m for _, _, m in self._queue]
            self._queue.clear()
            return messages


class AsyncBackgroundManager:
    """
    Async background task execution with notification queue.

    Tasks run via asyncio subprocess so they do not block the event loop.
    Completed tasks push notifications that can be drained on the next
    think-node pass.
    """

    def __init__(self):
        self.dir = RUNTIME_DIR
        self.tasks: dict[str, dict] = {}
        self._notification_queue: list[dict] = []
        self._lock = asyncio.Lock()

    def _record_path(self, task_id: str) -> Path:
        return self.dir / f"{task_id}.json"

    def _output_path(self, task_id: str) -> Path:
        return self.dir / f"{task_id}.log"

    def _persist_task(self, task_id: str):
        record = dict(self.tasks[task_id])
        self._record_path(task_id).write_text(
            json.dumps(record, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

    def _preview(self, output: str, limit: int = 500) -> str:
        compact = " ".join((output or "(no output)").split())
        return compact[:limit]

    async def run(self, command: str) -> str:
        """Start a background task, return task_id immediately."""
        task_id = str(uuid.uuid4())[:8]
        output_file = self._output_path(task_id)
        self.tasks[task_id] = {
            "id": task_id,
            "status": "running",
            "result": None,
            "command": command,
            "started_at": time.time(),
            "finished_at": None,
            "result_preview": "",
            "output_file": str(output_file.relative_to(Path.cwd())),
        }
        self._persist_task(task_id)
        asyncio.create_task(self._execute(task_id, command))
        return (
            f"Background task {task_id} started: {command[:80]} "
            f"(output_file={output_file.relative_to(Path.cwd())})"
        )

    async def _execute(self, task_id: str, command: str):
        """Async task target: run subprocess, capture output, push to queue."""
        try:
            proc = await asyncio.create_subprocess_shell(
                command,
                cwd=Path.cwd(),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            try:
                stdout, stderr = await asyncio.wait_for(
                    proc.communicate(), timeout=300
                )
                output = (stdout.decode("utf-8", errors="replace") +
                          stderr.decode("utf-8", errors="replace")).strip()[:50000]
                status = "completed" if proc.returncode == 0 else f"exit_{proc.returncode}"
            except asyncio.TimeoutError:
                proc.kill()
                await proc.wait()
                output = "Error: Timeout (300s)"
                status = "timeout"
        except Exception as e:
            output = f"Error: {e}"
            status = "error"

        final_output = output or "(no output)"
        preview = self._preview(final_output)
        output_path = self._output_path(task_id)
        output_path.write_text(final_output, encoding="utf-8")

        self.tasks[task_id]["status"] = status
        self.tasks[task_id]["result"] = final_output
        self.tasks[task_id]["finished_at"] = time.time()
        self.tasks[task_id]["result_preview"] = preview
        self._persist_task(task_id)

        async with self._lock:
            self._notification_queue.append({
                "task_id": task_id,
                "status": status,
                "command": command[:80],
                "preview": preview,
                "output_file": str(output_path.relative_to(Path.cwd())),
            })
        logger.info("Background task %s finished: %s", task_id, status)

    def check(self, task_id: str = None) -> str:
        """Check status of one task or list all."""
        if task_id:
            t = self.tasks.get(task_id)
            if not t:
                return f"Error: Unknown task {task_id}"
            visible = {
                "id": t["id"],
                "status": t["status"],
                "command": t["command"],
                "result_preview": t.get("result_preview", ""),
                "output_file": t.get("output_file", ""),
            }
            return json.dumps(visible, indent=2, ensure_ascii=False)
        lines = []
        for tid, t in self.tasks.items():
            lines.append(
                f"{tid}: [{t['status']}] {t['command'][:60]} "
                f"-> {t.get('result_preview') or '(running)'}"
            )
        return "\n".join(lines) if lines else "No background tasks."

    async def drain_notifications(self) -> list[dict]:
        """Return and clear all pending completion notifications."""
        async with self._lock:
            notifs = list(self._notification_queue)
            self._notification_queue.clear()
            return notifs

    def detect_stalled(self) -> list[str]:
        """Return task IDs that have been running longer than STALL_THRESHOLD_S."""
        now = time.time()
        stalled = []
        for task_id, info in self.tasks.items():
            if info["status"] != "running":
                continue
            elapsed = now - info.get("started_at", now)
            if elapsed > STALL_THRESHOLD_S:
                stalled.append(task_id)
        return stalled
