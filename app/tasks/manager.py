import json
import threading
from datetime import datetime
from pathlib import Path
from typing import Optional


class TaskManager:
    """Persistent TaskRecord store.

    Think "work graph on disk", not "currently running worker".
    """

    VALID_STATUSES = ("pending", "in_progress", "completed", "deleted")
    VALID_PRIORITIES = ("low", "medium", "high", "critical")

    def __init__(
        self,
        tasks_dir: Path,
        session_id: Optional[str] = None,
        agent_id: Optional[str] = None,
    ):
        self.dir = tasks_dir
        self.dir.mkdir(exist_ok=True)
        self._session_id = session_id
        self._agent_id = agent_id
        self._lock = threading.Lock()
        self._next_id = self._max_id() + 1

    # ── helpers ──────────────────────────────────────────────

    def _max_id(self) -> int:
        ids = []
        for f in self.dir.glob("task_*.json"):
            try:
                ids.append(int(f.stem.split("_")[1]))
            except (ValueError, IndexError):
                continue
        return max(ids) if ids else 0

    def _load(self, task_id: int) -> dict:
        path = self.dir / f"task_{task_id}.json"
        if not path.exists():
            raise ValueError(f"Task {task_id} not found")
        task = json.loads(path.read_text(encoding="utf-8"))
        return self._migrate_task(task)

    def _save(self, task: dict):
        path = self.dir / f"task_{task['id']}.json"
        path.write_text(
            json.dumps(task, indent=2, ensure_ascii=False), encoding="utf-8"
        )

    @staticmethod
    def _migrate_task(task: dict) -> dict:
        """Fill default values for fields missing in old-format files."""
        defaults = {
            "priority": "medium",
            "tags": [],
            "progress": 0,
            "sessionId": None,
            "agentId": None,
            "createdAt": None,
            "updatedAt": None,
        }
        for key, default in defaults.items():
            task.setdefault(key, default)
        return task

    def _broadcast_sse(self, config: dict, action: str, task: dict):
        """Send a TASK_UPDATED SSE event if sse_fn is available."""
        sse_fn = config.get("sse_fn")
        session_id = config.get("parent_session_id")
        if not sse_fn or not session_id:
            return
        try:
            from app.schemas.sse_event import SseMessage, SsePayload, SseMetadata, SseTaskUpdate

            sse_fn(
                session_id,
                SseMessage(
                    type="TASK_UPDATED",
                    payload=SsePayload(
                        taskUpdate=SseTaskUpdate(action=action, task=task)
                    ),
                    metadata=SseMetadata(),
                ),
            )
        except Exception:
            pass  # SSE is best-effort

    # ── CRUD ─────────────────────────────────────────────────

    def create(
        self,
        subject: str,
        description: str = "",
        priority: str = "medium",
        tags: Optional[list] = None,
        session_id: Optional[str] = None,
        agent_id: Optional[str] = None,
        config: Optional[dict] = None,
    ) -> str:
        now = datetime.now().isoformat()
        if priority not in self.VALID_PRIORITIES:
            priority = "medium"
        task = {
            "id": self._next_id,
            "subject": subject,
            "description": description,
            "status": "pending",
            "priority": priority,
            "blockedBy": [],
            "blocks": [],
            "owner": "",
            "tags": tags or [],
            "progress": 0,
            "sessionId": session_id or self._session_id,
            "agentId": agent_id or self._agent_id,
            "createdAt": now,
            "updatedAt": now,
        }
        with self._lock:
            self._save(task)
            self._next_id += 1
        if config:
            self._broadcast_sse(config, "created", task)
        return json.dumps(task, indent=2, ensure_ascii=False)

    def get(self, task_id: int) -> str:
        return json.dumps(self._load(task_id), indent=2, ensure_ascii=False)

    def get_dict(self, task_id: int) -> dict:
        """Return task as a plain dict (for REST API)."""
        return self._load(task_id)

    def update(
        self,
        task_id: int,
        status: str = None,
        owner: str = None,
        subject: str = None,
        description: str = None,
        priority: str = None,
        tags: list = None,
        progress: int = None,
        add_blocked_by: list = None,
        add_blocks: list = None,
        config: Optional[dict] = None,
    ) -> str:
        with self._lock:
            task = self._load(task_id)
            if subject is not None:
                task["subject"] = subject
            if description is not None:
                task["description"] = description
            if priority is not None:
                if priority not in self.VALID_PRIORITIES:
                    raise ValueError(f"Invalid priority: {priority}")
                task["priority"] = priority
            if owner is not None:
                task["owner"] = owner
            if tags is not None:
                task["tags"] = tags
            if progress is not None:
                task["progress"] = max(0, min(100, int(progress)))
            if status:
                if status not in self.VALID_STATUSES:
                    raise ValueError(f"Invalid status: {status}")
                task["status"] = status
                if status == "completed":
                    self._clear_dependency(task_id)
            if add_blocked_by:
                task["blockedBy"] = list(set(task["blockedBy"] + add_blocked_by))
            if add_blocks:
                task["blocks"] = list(set(task["blocks"] + add_blocks))
                for blocked_id in add_blocks:
                    try:
                        blocked = self._load(blocked_id)
                        if task_id not in blocked["blockedBy"]:
                            blocked["blockedBy"].append(task_id)
                            self._save(blocked)
                    except ValueError:
                        pass
            task["updatedAt"] = datetime.now().isoformat()
            self._save(task)
        if config:
            self._broadcast_sse(config, "updated", task)
        return json.dumps(task, indent=2, ensure_ascii=False)

    def delete(self, task_id: int, config: Optional[dict] = None) -> str:
        """Physically remove a task file and clean up references."""
        with self._lock:
            task = self._load(task_id)
            path = self.dir / f"task_{task_id}.json"
            # Remove from other tasks' dependency lists
            self._clear_dependency(task_id)
            # Remove from other tasks' blocks lists
            for blocked_id in task.get("blocks", []):
                try:
                    blocked = self._load(blocked_id)
                    if task_id in blocked.get("blockedBy", []):
                        blocked["blockedBy"].remove(task_id)
                        self._save(blocked)
                except (ValueError, OSError):
                    pass
            path.unlink(missing_ok=True)
        if config:
            self._broadcast_sse(config, "deleted", {"id": task_id})
        return json.dumps({"id": task_id, "deleted": True})

    # ── queries ──────────────────────────────────────────────

    def _load_all_tasks(self) -> list[dict]:
        tasks = []
        for f in sorted(self.dir.glob("task_*.json")):
            try:
                tasks.append(self._migrate_task(json.loads(f.read_text(encoding="utf-8"))))
            except (json.JSONDecodeError, OSError):
                continue
        return tasks

    def list_all(self) -> str:
        """Return formatted text summary (for agent tools)."""
        tasks = self._load_all_tasks()
        if not tasks:
            return "No tasks."
        lines = []
        for t in tasks:
            marker = {
                "pending": "[ ]",
                "in_progress": "[>]",
                "completed": "[x]",
                "deleted": "[-]",
            }.get(t["status"], "[?]")
            blocked = f" (blocked by: {t['blockedBy']})" if t.get("blockedBy") else ""
            owner = f" owner={t['owner']}" if t.get("owner") else ""
            priority = f" [{t['priority']}]" if t.get("priority", "medium") != "medium" else ""
            progress = f" {t['progress']}%" if t.get("progress", 0) > 0 else ""
            lines.append(f"{marker} #{t['id']}: {t['subject']}{priority}{progress}{owner}{blocked}")
        return "\n".join(lines)

    def list_dicts(
        self,
        session_id: Optional[str] = None,
        status: Optional[str] = None,
    ) -> list[dict]:
        """Return structured list (for REST API)."""
        tasks = self._load_all_tasks()
        if session_id:
            tasks = [t for t in tasks if t.get("sessionId") == session_id]
        if status:
            tasks = [t for t in tasks if t.get("status") == status]
        return tasks

    def _clear_dependency(self, completed_id: int):
        """Remove completed_id from all other tasks' blockedBy lists."""
        for f in self.dir.glob("task_*.json"):
            try:
                task = json.loads(f.read_text(encoding="utf-8"))
                if completed_id in task.get("blockedBy", []):
                    task["blockedBy"].remove(completed_id)
                    self._save(task)
            except (json.JSONDecodeError, OSError):
                continue
