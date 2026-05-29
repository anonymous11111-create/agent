import asyncio
import json
import logging
import os
import shutil
import subprocess
import threading
from pathlib import Path

logger = logging.getLogger(__name__)


class AsyncMCPClient:
    """
    Async MCP client over stdio.

    Uses subprocess.Popen + threading for Windows compatibility.
    uvicorn --reload on Windows uses SelectorEventLoop which does
    not support asyncio.create_subprocess_exec, so we fall back to
    a synchronous subprocess with a reader thread.
    """

    def __init__(self, server_name: str, command: str, args: list = None, env: dict = None):
        self.server_name = server_name
        self.env = {**os.environ, **(env or {})}
        self.process = None
        self._request_id = 0
        self._tools = []
        self._reader_lock = threading.Lock()
        self._writer_lock = threading.Lock()

        # On Windows, .cmd/.bat files can't be exec'd directly;
        # wrap through cmd /c so subprocess.Popen works correctly.
        resolved = shutil.which(command)
        if os.name == "nt" and resolved and resolved.lower().endswith((".cmd", ".bat")):
            self.command = shutil.which("cmd")
            self.args = ["/c", resolved] + (args or [])
        else:
            self.command = resolved if resolved else command
            self.args = args or []

    async def connect(self) -> bool:
        """Start the MCP server process."""
        try:
            self.process = subprocess.Popen(
                [self.command] + self.args,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                env=self.env,
                bufsize=0,
            )
            logger.debug("MCP process started: pid=%s, cmd=%s", self.process.pid, self.command)
            # Send initialize request
            await self._send({"method": "initialize", "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {
                    "tools": {},
                },
                "clientInfo": {"name": "agent", "version": "1.0"},
            }})
            response = await self._recv()
            logger.debug("MCP initialize response: %s", response)
            if response and "result" in response:
                # Send initialized notification (no id)
                await self._send_notification({"method": "notifications/initialized"})
                logger.info("MCP server initialized: %s", self.server_name)
                return True
            else:
                logger.warning("MCP initialize failed for %s: no valid response", self.server_name)
        except FileNotFoundError:
            logger.error("MCP server command not found: %s", self.command)
        except Exception as e:
            logger.error("MCP connection failed for %s: %s (%s)", self.server_name, type(e).__name__, e, exc_info=True)
            # Try to read stderr for diagnostics
            if self.process and self.process.stderr:
                try:
                    stderr_data = self.process.stderr.read(4096)
                    if stderr_data:
                        logger.error("MCP stderr: %s", stderr_data.decode("utf-8", errors="replace")[:500])
                except Exception:
                    pass
        return False

    async def list_tools(self) -> list:
        """Fetch available tools from the server."""
        await self._send({"method": "tools/list", "params": {}})
        response = await self._recv()
        if response and "result" in response:
            self._tools = response["result"].get("tools", [])
        return self._tools

    async def call_tool(self, tool_name: str, arguments: dict) -> str:
        """Execute a tool on the server."""
        await self._send({"method": "tools/call", "params": {
            "name": tool_name,
            "arguments": arguments,
        }})
        # Tool calls may involve network I/O (web search, API calls, etc.)
        # so use a generous timeout.
        response = await self._recv(timeout=60.0, max_lines=30)
        if response and "result" in response:
            content = response["result"].get("content", [])
            return "\n".join(c.get("text", str(c)) for c in content)
        if response and "error" in response:
            return f"MCP Error: {response['error'].get('message', 'unknown')}"
        return "MCP Error: no response"

    def get_agent_tools(self) -> list:
        """
        Convert MCP tools to agent tool format.
        Prefixed as mcp__{server_name}__{tool_name}.
        """
        agent_tools = []
        for tool in self._tools:
            prefixed_name = f"mcp__{self.server_name}__{tool['name']}"
            agent_tools.append({
                "name": prefixed_name,
                "description": tool.get("description", ""),
                "input_schema": tool.get("inputSchema", {"type": "object", "properties": {}}),
                "_mcp_server": self.server_name,
                "_mcp_tool": tool["name"],
            })
        return agent_tools

    async def disconnect(self):
        """Shut down the server process."""
        if self.process:
            try:
                await self._send({"method": "shutdown"})
                self.process.terminate()
                self.process.wait(timeout=5)
            except Exception:
                self.process.kill()
            self.process = None

    async def _send(self, message: dict):
        """Send a JSON-RPC request (with auto-increment id)."""
        if not self.process or self.process.returncode is not None:
            return
        self._request_id += 1
        envelope = {"jsonrpc": "2.0", "id": self._request_id, **message}
        line = json.dumps(envelope).encode("utf-8") + b"\n"
        try:
            loop = asyncio.get_running_loop()
            await loop.run_in_executor(None, self._write_sync, line)
        except (BrokenPipeError, OSError):
            pass

    async def _send_notification(self, message: dict):
        """Send a JSON-RPC notification (no id field)."""
        if not self.process or self.process.returncode is not None:
            return
        envelope = {"jsonrpc": "2.0", **message}
        line = json.dumps(envelope).encode("utf-8") + b"\n"
        try:
            loop = asyncio.get_running_loop()
            await loop.run_in_executor(None, self._write_sync, line)
        except (BrokenPipeError, OSError):
            pass

    def _write_sync(self, data: bytes):
        """Synchronous write to stdin (called via run_in_executor)."""
        with self._writer_lock:
            self.process.stdin.write(data)
            self.process.stdin.flush()

    async def _recv(self, timeout: float = 5.0, max_lines: int = 10) -> dict | None:
        if not self.process or self.process.returncode is not None:
            return None
        try:
            loop = asyncio.get_running_loop()
            for _ in range(max_lines):
                raw = await asyncio.wait_for(
                    loop.run_in_executor(None, self._readline_sync),
                    timeout=timeout,
                )
                if not raw:
                    logger.debug("_recv: EOF reached")
                    return None
                raw = raw.strip()
                logger.debug("_recv raw: %s", raw[:200])
                try:
                    return json.loads(raw)
                except json.JSONDecodeError:
                    continue
        except asyncio.TimeoutError:
            logger.debug("_recv: timeout")
        except OSError as e:
            logger.debug("_recv: OSError %s", e)
        return None

    def _readline_sync(self) -> str:
        """Synchronous readline from stdout (called via run_in_executor)."""
        with self._reader_lock:
            line = self.process.stdout.readline()
            return line.decode("utf-8") if line else ""
