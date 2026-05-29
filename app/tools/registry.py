import logging
from typing import Optional

from langchain_core.tools import BaseTool

from app.tools.terminate import terminate
from app.tools.knowledge_search import knowledge_query
from app.tools.database import database_query
from app.tools.email import send_email
from app.tools.skill import load_skill
from app.tools.subagent import delegate_task
from app.tools.memory import save_memory
from app.tools.tasks import task_create, task_update, task_list, task_get, task_delete
from app.tools.teams import (
    send_message,
    read_inbox,
    broadcast,
    spawn_teammate,
    list_teammates,
    shutdown_request,
    plan_approval,
)
from app.tools.background import backgroundRun, checkBackground
from app.tools.mcp_wrapper import create_mcp_tools

# Legacy web_search removed; search capability is now provided by Tavily MCP (tavily_search)

logger = logging.getLogger(__name__)

FIXED_TOOLS = [terminate, knowledge_query]
OPTIONAL_TOOLS_MAP = {
    "databaseQuery": database_query,
    "sendEmail": send_email,
    "loadSkill": load_skill,
    "delegateTask": delegate_task,
    "saveMemory": save_memory,
    "taskCreate": task_create,
    "taskUpdate": task_update,
    "taskList": task_list,
    "taskGet": task_get,
    "taskDelete": task_delete,
    "sendMessage": send_message,
    "readInbox": read_inbox,
    "broadcast": broadcast,
    "spawnTeammate": spawn_teammate,
    "listTeammates": list_teammates,
    "shutdownRequest": shutdown_request,
    "planApproval": plan_approval,
    "backgroundRun": backgroundRun,
    "checkBackground": checkBackground,
    # 兼容旧配置名称
    "subAgentSpawner": delegate_task,
    "subagentTool": delegate_task,
    "dataBaseTool": database_query,
    "emailTool": send_email,
    "skillTool": load_skill,
    "weatherTool": delegate_task,
    "dateTool": delegate_task,
    "cityTool": delegate_task,
}

# 工具分类定义
TOOL_CATEGORIES = {
    "data": "数据查询",
    "email": "邮件通信",
    "skill": "技能加载",
    "task": "任务管理",
    "team": "团队协作",
    "agent": "子代理",
    "memory": "记忆管理",
    "background": "后台任务",
}

TOOL_CATEGORY_MAP = {
    "databaseQuery": "data",
    "sendEmail": "email",
    "loadSkill": "skill",
    "taskCreate": "task",
    "taskUpdate": "task",
    "taskList": "task",
    "taskGet": "task",
    "taskDelete": "task",
    "delegateTask": "agent",
    "saveMemory": "memory",
    "sendMessage": "team",
    "readInbox": "team",
    "broadcast": "team",
    "spawnTeammate": "team",
    "listTeammates": "team",
    "shutdownRequest": "team",
    "planApproval": "team",
    "backgroundRun": "background",
    "checkBackground": "background",
}

PRIMARY_TOOL_NAMES = set(TOOL_CATEGORY_MAP.keys())


def _extract_parameters(tool: BaseTool) -> list[dict]:
    args_schema = tool.args
    if not args_schema or "properties" not in args_schema:
        return []
    properties = args_schema["properties"]
    required = set(args_schema.get("required", []))
    params = []
    for name, schema in properties.items():
        params.append({
            "name": name,
            "type": schema.get("type", "string"),
            "required": name in required,
            "description": schema.get("description", ""),
        })
    return params


ALL_OPTIONAL_TOOLS = [
    {
        "name": name,
        "description": tool.description,
        "category": TOOL_CATEGORY_MAP.get(name, "other"),
        "parameters": _extract_parameters(tool),
    }
    for name, tool in OPTIONAL_TOOLS_MAP.items()
    if name in PRIMARY_TOOL_NAMES
]

# 虚拟 MCP 工具开关：勾选后 agent 运行时会动态加载所有已配置的 MCP 服务器工具
ALL_OPTIONAL_TOOLS.append({
    "name": "mcpTool",
    "description": "启用所有已配置的 MCP 服务器工具（包括联网搜索、网页浏览、GitHub 搜索等外部能力）。需要在 MCP 服务器设置中预先添加服务器。",
    "category": "mcp",
    "parameters": [],
})


def get_tools_for_agent(
    agent_entity,
    exclude_tool_names: Optional[set[str]] = None,
    mcp_router=None,
) -> list[BaseTool]:
    """Resolve tools for an agent: FIXED + configured OPTIONAL tools + MCP tools.

    Args:
        agent_entity: Agent ORM object with allowed_tools JSON field.
        exclude_tool_names: Tool names to exclude (e.g., for sub-agents).
        mcp_router: Optional MCPToolRouter to add discovered MCP tools.
    """
    tools = list(FIXED_TOOLS)
    seen_names = {t.name for t in tools}

    allowed_tools = agent_entity.allowed_tools or []
    for tool_name in allowed_tools:
        tool = OPTIONAL_TOOLS_MAP.get(tool_name)
        if tool and tool.name not in seen_names:
            tools.append(tool)
            seen_names.add(tool.name)

    # Add MCP tools if router provided and MCP tools are allowed
    if mcp_router and allowed_tools and any(
        t.startswith("mcp") or t == "mcpTool" for t in allowed_tools
    ):
        mcp_tools = create_mcp_tools(mcp_router)
        for mcp_tool in mcp_tools:
            if mcp_tool.name not in seen_names:
                tools.append(mcp_tool)
                seen_names.add(mcp_tool.name)

    # Remove excluded tools
    if exclude_tool_names:
        tools = [t for t in tools if t.name not in exclude_tool_names]

    return tools
