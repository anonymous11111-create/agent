import logging
from typing import Any

from langchain_core.tools import StructuredTool
from pydantic import BaseModel, Field, create_model
from typing import Optional, Union

logger = logging.getLogger(__name__)


def _map_json_type(prop_schema: dict):
    """Map a JSON Schema property to a Python type annotation.

    Handles enum constraints by using Literal types when possible,
    and falls back to the base type with Optional for non-required fields.
    """
    json_type = prop_schema.get("type", "string")

    # Handle enum: use the base type (enum validation done server-side)
    # We still set the correct base type so the LLM generates valid values.
    type_map = {
        "string": str,
        "integer": int,
        "number": float,
        "boolean": bool,
        "array": list,
        "object": dict,
    }
    return type_map.get(json_type, str)


def _json_schema_to_model(name: str, schema: dict) -> type[BaseModel]:
    """Dynamically create a permissive Pydantic BaseModel from a JSON Schema dict.

    All fields use type ``Any`` so that LLM-generated values (which may have
    mismatched types like string "true" for boolean) pass Pydantic validation.
    The actual type checking is delegated to the MCP server.

    Field descriptions include enum values and defaults to guide the LLM.
    """
    properties = schema.get("properties", {})
    required = set(schema.get("required", []))
    fields = {}
    for prop_name, prop_schema in properties.items():
        is_required = prop_name in required

        # Build a rich description including type hint, enum values and defaults
        desc_parts = []
        json_type = prop_schema.get("type", "string")
        desc_parts.append(f"(type: {json_type})")
        if prop_schema.get("description"):
            desc_parts.append(prop_schema["description"])
        if prop_schema.get("enum"):
            desc_parts.append(f"Allowed values: {prop_schema['enum']}")
        rich_desc = " ".join(desc_parts)

        if is_required:
            fields[prop_name] = (
                Any,
                Field(description=rich_desc),
            )
        else:
            default_val = prop_schema.get("default", None)
            fields[prop_name] = (
                Any,
                Field(description=rich_desc, default=default_val),
            )

    safe_name = "".join(c if c.isalnum() else "_" for c in name)
    return create_model(safe_name, **fields)


def create_mcp_tools(mcp_router) -> list:
    """
    Dynamically create LangChain tools from discovered MCP tools.

    Each MCP tool is wrapped as an async function with the prefix
    mcp__{server_name}__{tool_name}.
    """
    tools = []
    raw_tools = mcp_router.get_all_tools()

    for tool_def in raw_tools:
        name = tool_def["name"]
        description = tool_def.get("description", "")
        input_schema = tool_def.get("input_schema", {"type": "object", "properties": {}})

        wrapper = _make_mcp_tool_wrapper(mcp_router, name, description, input_schema)
        tools.append(wrapper)

    logger.info("Created %d MCP tools", len(tools))
    return tools


def _make_mcp_tool_wrapper(mcp_router, full_name: str, description: str, input_schema: dict):
    """Create a single MCP tool wrapper using StructuredTool.

    Uses the short tool name (last segment after __) so the LLM sees
    familiar names like ``tavily_search`` instead of ``mcp__tavily__tavily_search``.
    Routing still uses the full prefixed name internally.
    """
    args_model = _json_schema_to_model(f"Args_{full_name}", input_schema)
    short_name = full_name.split("__")[-1]
    # Truncate overly long descriptions to help the model focus
    clean_description = (description or f"MCP tool {short_name}")[:300]

    async def _arun(**kwargs) -> str:
        # Filter out None values so MCP server uses its own defaults
        filtered = {k: v for k, v in kwargs.items() if v is not None}
        return await mcp_router.call(full_name, filtered)

    def _run(**kwargs) -> str:
        raise NotImplementedError("MCP tools only support async execution")

    return StructuredTool.from_function(
        name=short_name,
        description=clean_description,
        func=_run,
        coroutine=_arun,
        args_schema=args_model,
    )
