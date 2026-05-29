from fastapi import APIRouter
from pydantic import BaseModel

from app.schemas.common import ApiResponse
from app.services.confirmation_service import confirmation_service

router = APIRouter(prefix="/api", tags=["confirmation"])


class ConfirmRequest(BaseModel):
    approved: bool


@router.post("/tool-confirm/{confirmation_id}")
async def confirm_tool(confirmation_id: str, request: ConfirmRequest):
    found = confirmation_service.respond(confirmation_id, request.approved)
    if not found:
        return ApiResponse.success(data={"status": "not_found"})
    return ApiResponse.success(data={"status": "ok", "approved": request.approved})
