import asyncio
import logging
import time
from pathlib import Path

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from langchain_core.messages import AIMessage, SystemMessage, ToolMessage

from app.api.deps import get_db
from app.schemas.common import ApiResponse
from app.schemas.chat_message import (
    CreateChatMessageRequest,
    UpdateChatMessageRequest,
    GetChatMessagesResponse,
    CreateChatMessageResponse,
)
from app.schemas.sse_event import SseMessage, SsePayload, SsePayloadMessage, SseMetadata
from app.services.chat_service import ChatService
from app.services.sse_service import sse_service
from app.services.skill_service import skill_registry
from app.agent.graph import build_agent_graph
from app.agent.state import AgentState
from app.tools.registry import get_tools_for_agent
from app.llm.registry import get_chat_model
from app.hooks import HookManager
from app.memory import MemoryManager
from app.tasks import TaskManager
from app.background import AsyncBackgroundManager
from app.tools import background as background_tools
from app.mcp import PluginLoader, MCPToolRouter, AsyncMCPClient
from app.services.mcp_server_service import MCPServerService
from app.config import settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["chat-messages"])

# Track running sessions to prevent concurrent agent executions
_running_sessions: set[str] = set()


@router.get("/chat-messages/session/{session_id}")
async def get_chat_messages(session_id: str, db: AsyncSession = Depends(get_db)):
    svc = ChatService(db)
    messages = await svc.list_messages(session_id)
    return ApiResponse.success(GetChatMessagesResponse(chatMessages=messages))


@router.post("/chat-messages")
async def create_chat_message(
    request: CreateChatMessageRequest, db: AsyncSession = Depends(get_db)
):
    svc = ChatService(db)

    # Persist user message
    msg = await svc.create_message(
        session_id=request.sessionId,
        role="user",
        content=request.content,
    )
    await db.commit()

    # Trigger agent execution in background
    session_id = request.sessionId
    agent_id = request.agentId
    asyncio.create_task(
        _run_agent(session_id, agent_id),
    )

    return ApiResponse.success(CreateChatMessageResponse(chatMessageId=str(msg.id)))


@router.delete("/chat-messages/{chat_message_id}")
async def delete_chat_message(chat_message_id: str, db: AsyncSession = Depends(get_db)):
    svc = ChatService(db)
    await svc.delete_message(chat_message_id)
    await db.commit()
    return ApiResponse.success()


@router.patch("/chat-messages/{chat_message_id}")
async def update_chat_message(
    chat_message_id: str,
    request: UpdateChatMessageRequest,
    db: AsyncSession = Depends(get_db),
):
    # Simple update - not commonly used
    return ApiResponse.success()


async def _run_agent(session_id: str, agent_id: str):
    """Background task: run the agent loop for a chat session."""
    if session_id in _running_sessions:
        logger.warning("Session %s already has agent running, skipping", session_id)
        return

    _running_sessions.add(session_id)
    try:
        # Wait for SSE connection before starting (avoid race condition where
        # agent finishes before frontend subscribes and all events are dropped)
        for _ in range(30):  # up to 15 seconds
            if session_id in sse_service._clients:
                break
            await asyncio.sleep(0.5)

        from app.db.engine import async_session_factory

        # Initialize hook manager
        hook_manager = HookManager()

        # Initialize memory manager
        memory_manager = MemoryManager()
        memory_manager.load_all()

        # Initialize task manager
        task_manager = TaskManager(Path.cwd() / ".tasks", session_id=session_id, agent_id=agent_id)

        # Initialize background manager
        background_manager = AsyncBackgroundManager()
        background_tools.background_manager = background_manager

        # Fire SessionStart hooks
        await hook_manager.run_hooks("SessionStart", {"tool_name": "", "tool_input": {}})

        async with async_session_factory() as db:
            svc = ChatService(db)

            # Load agent config
            agent_entity = await svc.get_agent_entity(agent_id)
            model_name = agent_entity.model or "deepseek-chat"
            chat_model = get_chat_model(model_name)

            # Initialize MCP plugin loader and router
            mcp_router = MCPToolRouter()

            # 1. Connect MCP servers from database (frontend-configured)
            mcp_svc = MCPServerService(db)
            db_servers = await mcp_svc.list_servers()
            for server in db_servers:
                if not server.enabled:
                    continue
                mcp_client = AsyncMCPClient(
                    server.name,
                    server.command,
                    server.args or [],
                    server.env,
                )
                if await mcp_client.connect():
                    await mcp_client.list_tools()
                    mcp_router.register_client(mcp_client)
                    logger.info("MCP connected from DB: %s", server.name)
                else:
                    logger.warning("MCP connection failed from DB: %s", server.name)

            # 2. Also scan .claude-plugin/ for file-based plugins (optional fallback)
            plugin_loader = PluginLoader()
            found_plugins = plugin_loader.scan()
            if found_plugins:
                logger.info("Plugins loaded: %s", ", ".join(found_plugins))
            for server_name, server_config in plugin_loader.get_mcp_servers().items():
                # Skip if already connected from DB with same name
                if server_name in mcp_router.clients:
                    continue
                mcp_client = AsyncMCPClient(
                    server_name,
                    server_config.get("command", ""),
                    server_config.get("args", []),
                    server_config.get("env"),
                )
                if await mcp_client.connect():
                    await mcp_client.list_tools()
                    mcp_router.register_client(mcp_client)
                    logger.info("MCP connected from plugin: %s", server_name)
                else:
                    logger.warning("MCP connection failed from plugin: %s", server_name)

            # Resolve tools (native + MCP)
            tools = get_tools_for_agent(agent_entity, mcp_router=mcp_router)
            tools_map = {t.name: t for t in tools}
            logger.info(
                "Agent %s allowed_tools=%s -> resolved tools=%s",
                agent_id, agent_entity.allowed_tools, [t.name for t in tools],
            )

            # Load memory
            chat_options = agent_entity.chat_options if agent_entity.chat_options else {}
            message_length = chat_options.get("messageLength", settings.CHAT_MEMORY_WINDOW_SIZE)
            memory_messages = await svc.load_memory(session_id, message_length)

            # Build KB list string
            kb_list_str = "[]"
            if agent_entity.allowed_kbs:
                import json
                kb_list_str = json.dumps(agent_entity.allowed_kbs)

            # Build graph
            graph = build_agent_graph()

            initial_messages = []
            if agent_entity.system_prompt:
                initial_messages.append(SystemMessage(content=agent_entity.system_prompt))
            initial_messages.extend(memory_messages)

            initial_state: AgentState = {
                "messages": initial_messages,
                "step_count": 0,
                "terminated": False,
                "tool_call_history": [],
                "start_time": time.monotonic(),
                "error": None,
            }

            # Persist and SSE callback – uses its own DB session to avoid
            # concurrent-access errors when LangGraph calls this from multiple
            # coroutines / retries.
            async def persist_fn(msg):
                async with async_session_factory() as persist_db:
                    persist_svc = ChatService(persist_db)
                    if isinstance(msg, AIMessage):
                        meta = {"toolCalls": msg.tool_calls} if msg.tool_calls else {}
                        saved = await persist_svc.create_message(
                            session_id=session_id,
                            role="assistant",
                            content=msg.content or "",
                            metadata=meta,
                        )
                        await persist_db.commit()
                        vo = persist_svc._message_to_vo(saved)
                        sse_service.send(
                            session_id,
                            SseMessage(
                                type="AI_GENERATED_CONTENT",
                                payload=SsePayload(
                                    message=SsePayloadMessage(
                                        id=vo.id,
                                        sessionId=vo.sessionId,
                                        role=vo.role,
                                        content=vo.content,
                                        metadata=vo.metadata,
                                        createdAt=str(vo.createdAt) if vo.createdAt else None,
                                        updatedAt=str(vo.updatedAt) if vo.updatedAt else None,
                                    )
                                ),
                                metadata=SseMetadata(chatMessageId=vo.id),
                            ),
                        )
                    elif isinstance(msg, ToolMessage):
                        meta = {
                            "toolResponse": {
                                "id": msg.tool_call_id,
                                "name": msg.name,
                                "response": msg.content,
                            }
                        }
                        saved = await persist_svc.create_message(
                            session_id=session_id,
                            role="tool",
                            content=msg.content,
                            metadata=meta,
                        )
                        await persist_db.commit()
                        vo = persist_svc._message_to_vo(saved)
                        sse_service.send(
                            session_id,
                            SseMessage(
                                type="AI_GENERATED_CONTENT",
                                payload=SsePayload(
                                    message=SsePayloadMessage(
                                        id=vo.id,
                                        sessionId=vo.sessionId,
                                        role=vo.role,
                                        content=vo.content,
                                        metadata=vo.metadata,
                                        createdAt=str(vo.createdAt) if vo.createdAt else None,
                                        updatedAt=str(vo.updatedAt) if vo.updatedAt else None,
                                    )
                                ),
                                metadata=SseMetadata(chatMessageId=vo.id),
                            ),
                        )

            config = {
                "configurable": {
                    "chat_model": chat_model,
                    "tools": tools,
                    "tools_map": tools_map,
                    "agent_id": agent_id,
                    "db_session": db,
                    "kb_list": kb_list_str,
                    "skill_catalog": skill_registry.describe_available(),
                    "persist_fn": persist_fn,
                    "sse_fn": sse_service.send,
                    "parent_session_id": session_id,
                    "hook_manager": hook_manager,
                    "memory_manager": memory_manager,
                    "task_manager": task_manager,
                    "background_manager": background_manager,
                    "mcp_router": mcp_router,
                }
            }

            timeout = settings.AGENT_TIMEOUT_SECONDS + 30  # extra 30s buffer for cleanup
            await asyncio.wait_for(
                graph.ainvoke(initial_state, config),
                timeout=timeout,
            )

            # Send agent done event
            sse_service.send(
                session_id,
                SseMessage(type="AGENT_DONE", payload=None, metadata=SseMetadata()),
            )

    except asyncio.TimeoutError:
        logger.error("Agent execution timed out: session=%s, timeout=%ds", session_id, settings.AGENT_TIMEOUT_SECONDS + 30)
        sse_service.send(
            session_id,
            SseMessage(
                type="AGENT_ERROR",
                payload=SsePayload(
                    message=SsePayloadMessage(
                        id="",
                        sessionId=session_id,
                        role="system",
                        content="Agent 执行超时，请稍后重试。",
                    )
                ),
                metadata=SseMetadata(),
            ),
        )
    except Exception as e:
        import traceback
        tb = traceback.format_exc()
        logger.error("Agent execution failed: session=%s, error=%s", session_id, e, exc_info=True)
        sse_service.send(
            session_id,
            SseMessage(
                type="AGENT_ERROR",
                payload=SsePayload(
                    message=SsePayloadMessage(
                        id="",
                        sessionId=session_id,
                        role="system",
                        content=f"Agent 执行出错: {e}\n{tb}",
                    )
                ),
                metadata=SseMetadata(),
            ),
        )
    finally:
        _running_sessions.discard(session_id)
        # Cleanup MCP connections
        try:
            if 'mcp_router' in locals():
                await mcp_router.disconnect_all()
        except Exception as e:
            logger.warning("MCP disconnect error: %s", e)
