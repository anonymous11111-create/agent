import asyncio
import json
import os
from pathlib import Path

WORKDIR = Path.cwd()

# The teaching version keeps only the three clearest events.
HOOK_EVENTS = ("PreToolUse", "PostToolUse", "SessionStart")
HOOK_TIMEOUT = 30  # seconds

# Workspace trust marker. Hooks only run if this file exists (or SDK mode).
TRUST_MARKER = WORKDIR / ".claude" / ".claude_trusted"


class HookManager:
    """
    Load and execute hooks from .hooks.json configuration.

    The hook manager does three simple jobs:
    - load hook definitions
    - run matching commands for an event
    - aggregate block / message results for the caller
    """

    def __init__(self, config_path: Path = None, sdk_mode: bool = False):
        self.hooks: dict[str, list[dict]] = {
            "PreToolUse": [],
            "PostToolUse": [],
            "SessionStart": [],
        }
        self._sdk_mode = sdk_mode
        config_path = config_path or (WORKDIR / ".hooks.json")
        if config_path.exists():
            try:
                config = json.loads(config_path.read_text(encoding="utf-8"))
                for event in HOOK_EVENTS:
                    self.hooks[event] = config.get("hooks", {}).get(event, [])
                print(f"[Hooks loaded from {config_path}]")
            except Exception as e:
                print(f"[Hook config error: {e}]")

    def _check_workspace_trust(self) -> bool:
        """
        Check whether the current workspace is trusted.

        The teaching version uses a simple trust marker file.
        In SDK mode, trust is treated as implicit.
        """
        if self._sdk_mode:
            return True
        return TRUST_MARKER.exists()

    async def run_hooks(self, event: str, context: dict = None) -> dict:
        """
        Execute all hooks for an event.

        Returns: {"blocked": bool, "messages": list[str], "block_reason": str}
          - blocked: True if any hook returned exit code 1
          - messages: stderr content from exit-code-2 hooks (to inject)
          - block_reason: reason for blocking
        """
        result = {"blocked": False, "messages": [], "block_reason": ""}

        # Trust gate: refuse to run hooks in untrusted workspaces
        if not self._check_workspace_trust():
            return result

        hooks = self.hooks.get(event, [])

        for hook_def in hooks:
            # Check matcher (tool name filter for PreToolUse/PostToolUse)
            matcher = hook_def.get("matcher")
            if matcher and context:
                tool_name = context.get("tool_name", "")
                if matcher != "*" and matcher != tool_name:
                    continue

            command = hook_def.get("command", "")
            if not command:
                continue

            # Build environment with hook context
            env = dict(os.environ)
            if context:
                env["HOOK_EVENT"] = event
                env["HOOK_TOOL_NAME"] = context.get("tool_name", "")
                env["HOOK_TOOL_INPUT"] = json.dumps(
                    context.get("tool_input", {}), ensure_ascii=False
                )[:10000]
                if "tool_output" in context:
                    env["HOOK_TOOL_OUTPUT"] = str(context["tool_output"])[:10000]

            try:
                proc = await asyncio.create_subprocess_shell(
                    command,
                    cwd=WORKDIR,
                    env=env,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )
                try:
                    stdout, stderr = await asyncio.wait_for(
                        proc.communicate(), timeout=HOOK_TIMEOUT
                    )
                except asyncio.TimeoutError:
                    proc.kill()
                    await proc.wait()
                    print(f"  [hook:{event}] Timeout ({HOOK_TIMEOUT}s)")
                    continue

                stdout_text = stdout.decode("utf-8", errors="replace").strip()
                stderr_text = stderr.decode("utf-8", errors="replace").strip()

                if proc.returncode == 0:
                    # Continue silently
                    if stdout_text:
                        print(f"  [hook:{event}] {stdout_text[:100]}")

                    # Optional structured stdout: small extension point that
                    # keeps the teaching contract simple.
                    try:
                        hook_output = json.loads(stdout_text)
                        if "updatedInput" in hook_output and context:
                            context["tool_input"] = hook_output["updatedInput"]
                        if "additionalContext" in hook_output:
                            result["messages"].append(hook_output["additionalContext"])
                        if "permissionDecision" in hook_output:
                            result["permission_override"] = hook_output["permissionDecision"]
                    except (json.JSONDecodeError, TypeError):
                        pass  # stdout was not JSON -- normal for simple hooks

                elif proc.returncode == 1:
                    # Block execution
                    result["blocked"] = True
                    reason = stderr_text or "Blocked by hook"
                    result["block_reason"] = reason
                    print(f"  [hook:{event}] BLOCKED: {reason[:200]}")

                elif proc.returncode == 2:
                    # Inject message
                    msg = stderr_text
                    if msg:
                        result["messages"].append(msg)
                        print(f"  [hook:{event}] INJECT: {msg[:200]}")

            except Exception as e:
                print(f"  [hook:{event}] Error: {e}")

        return result
