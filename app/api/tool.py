from fastapi import APIRouter

from app.schemas.common import ApiResponse
from app.tools.registry import ALL_OPTIONAL_TOOLS, FIXED_TOOLS

router = APIRouter(prefix="/api", tags=["tools"])


@router.get("/tools")
async def get_optional_tools():
    fixed = [
        {
            "name": t.name,
            "description": t.description,
            "category": "fixed",
            "parameters": [],
            "fixed": True,
        }
        for t in FIXED_TOOLS
    ]
    return ApiResponse.success(fixed + ALL_OPTIONAL_TOOLS)
