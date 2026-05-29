"""Initialize database: create tables + seed data."""
import asyncio
import os
import uuid
import json

from app.db.engine import engine, async_session_factory
from app.models.base import Base


async def init():
    # 1. Create all tables
    async with engine.begin() as conn:
        await conn.execute(__import__("sqlalchemy").text("CREATE EXTENSION IF NOT EXISTS vector"))
        await conn.run_sync(Base.metadata.create_all)
        print("Tables created.")

    # 2. Seed: insert a default agent
    async with async_session_factory() as db:
        from sqlalchemy import select
        from app.models.agent import Agent

        result = await db.execute(select(Agent))
        if result.scalars().first():
            print("Agent already exists, skip seeding.")
            return

        agent = Agent(
            name="JChatMind 助手",
            description="通用智能助手，支持知识库检索、数据库查询、邮件发送、子智能体委派",
            system_prompt="你是一个智能助手，能够帮助用户完成各种任务。请用中文回复。",
            model="deepseek-chat",
            allowed_tools=["databaseQuery", "sendEmail", "delegateTask", "mcpTool"],
            allowed_kbs=[],
            chat_options={"temperature": 0.7, "topP": 1.0, "messageLength": 20},
        )
        db.add(agent)
        await db.commit()
        print(f"Agent created: id={agent.id}, name={agent.name}")

        # 3. Seed: create a default chat session
        from app.models.chat_session import ChatSession

        session = ChatSession(
            agent_id=agent.id,
            title="默认会话",
            type="NORMAL",
        )
        db.add(session)
        await db.commit()
        print(f"Session created: id={session.id}")

        # 4. Seed: insert built-in MCP servers
        from app.models.mcp_server import MCPServerConfig

        result = await db.execute(select(MCPServerConfig))
        if not result.scalars().first():
            tavily_api_key = os.environ.get("TAVILY_API_KEY", "")
            mcp_servers = []
            if tavily_api_key:
                mcp_servers.append(
                    MCPServerConfig(
                        name="tavily-remote-mcp",
                        command="cmd",
                        args=["/c", "npx", "-y", "mcp-remote", f"https://mcp.tavily.com/mcp/?tavilyApiKey={tavily_api_key}"],
                        env={},
                        enabled=True,
                        description="Tavily 联网搜索 MCP 服务器，提供网页搜索能力",
                    ),
                )
            for server in mcp_servers:
                db.add(server)
            await db.commit()
            print(f"MCP servers seeded: {[s.name for s in mcp_servers]}")

    print("Done.")


if __name__ == "__main__":
    asyncio.run(init())
