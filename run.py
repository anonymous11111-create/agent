"""Entry point that sets Windows event loop policy before uvicorn starts.

On Windows, uvicorn --reload may use SelectorEventLoop which does not support
subprocess creation (required by MCP clients). Setting ProactorEventLoopPolicy
here ensures it takes effect before uvicorn creates its event loop.
"""
import sys
import asyncio

if __name__ == "__main__":
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=8080, reload=True)
