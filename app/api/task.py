from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Query

from app.schemas.common import ApiResponse
from app.schemas.task import (
    CreateTaskRequest,
    UpdateTaskRequest,
    TaskVO,
    GetTasksResponse,
)
from app.tasks import TaskManager

router = APIRouter(prefix="/api", tags=["tasks"])

TASKS_DIR = Path.cwd() / ".tasks"


def _get_manager() -> TaskManager:
    return TaskManager(TASKS_DIR)


@router.get("/tasks")
async def get_tasks(
    session_id: Optional[str] = Query(None, alias="sessionId"),
    status: Optional[str] = Query(None),
):
    tm = _get_manager()
    tasks = tm.list_dicts(session_id=session_id, status=status)
    task_vos = [TaskVO(**t) for t in tasks]
    return ApiResponse.success(GetTasksResponse(tasks=task_vos))


@router.get("/tasks/{task_id}")
async def get_task(task_id: int):
    tm = _get_manager()
    try:
        task = tm.get_dict(task_id)
    except ValueError as e:
        return ApiResponse.success(data=None)
    return ApiResponse.success(TaskVO(**task))


@router.post("/tasks")
async def create_task(request: CreateTaskRequest):
    tm = _get_manager()
    result = tm.create(
        subject=request.subject,
        description=request.description or "",
        priority=request.priority or "medium",
        tags=request.tags or [],
        session_id=request.sessionId,
    )
    import json
    task_dict = json.loads(result)
    return ApiResponse.success(TaskVO(**task_dict))


@router.patch("/tasks/{task_id}")
async def update_task(task_id: int, request: UpdateTaskRequest):
    tm = _get_manager()
    try:
        result = tm.update(
            task_id,
            status=request.status,
            owner=request.owner,
            subject=request.subject,
            description=request.description,
            priority=request.priority,
            tags=request.tags,
            progress=request.progress,
            add_blocked_by=request.addBlockedBy,
            add_blocks=request.addBlocks,
        )
    except ValueError as e:
        return ApiResponse.success(data=None)
    import json
    task_dict = json.loads(result)
    return ApiResponse.success(TaskVO(**task_dict))


@router.delete("/tasks/{task_id}")
async def delete_task(task_id: int):
    tm = _get_manager()
    try:
        tm.delete(task_id)
    except ValueError:
        pass
    return ApiResponse.success()


@router.post("/tasks/cleanup")
async def cleanup_tasks():
    tm = _get_manager()
    deleted = tm.list_dicts(status="deleted")
    for task in deleted:
        try:
            tm.delete(task["id"])
        except (ValueError, OSError):
            pass
    return ApiResponse.success(data={"cleaned": len(deleted)})
