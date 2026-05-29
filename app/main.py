import asyncio
import logging
import sys
from contextlib import asynccontextmanager
# force reload

# Windows requires ProactorEventLoop for subprocess support (used by MCP clients).
# uvicorn --reload may default to SelectorEventLoop which raises NotImplementedError.
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.services.skill_service import skill_registry

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    logger.info("Starting JChatMind Python server...")

    # Initialize skill registry
    skill_registry.init()

    yield

    # Shutdown
    logger.info("Shutting down...")


def create_app() -> FastAPI:
    app = FastAPI(
        title="JChatMind",
        version="1.0.0",
        lifespan=lifespan,
    )

    # CORS for React frontend
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:5173", "http://localhost:5174", "http://localhost:5175", "http://localhost:5176", "http://localhost:5177", "http://localhost:3000", "http://localhost:8080"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Import and include routers
    from app.api.agent import router as agent_router
    from app.api.chat_session import router as chat_session_router
    from app.api.chat_message import router as chat_message_router
    from app.api.knowledge_base import router as kb_router
    from app.api.document import router as document_router
    from app.api.tool import router as tool_router
    from app.api.sse import router as sse_router
    from app.api.mcp_server import router as mcp_server_router
    from app.api.task import router as task_router
    from app.api.confirmation import router as confirmation_router
    from app.api.tool_call_log import router as tool_call_log_router
    from app.api.rag_query_log import router as rag_query_log_router

    app.include_router(agent_router)
    app.include_router(chat_session_router)
    app.include_router(chat_message_router)
    app.include_router(kb_router)
    app.include_router(document_router)
    app.include_router(tool_router)
    app.include_router(sse_router)
    app.include_router(mcp_server_router)
    app.include_router(task_router)
    app.include_router(confirmation_router)
    app.include_router(tool_call_log_router)
    app.include_router(rag_query_log_router)

    @app.get("/health")
    async def health():
        return {"status": "ok"}

    return app


app = create_app()
