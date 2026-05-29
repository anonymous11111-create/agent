import json
import time
from pathlib import Path

from langchain_core.messages import BaseMessage, HumanMessage, ToolMessage

TOOL_RESULTS_DIR = Path.cwd() / ".task_outputs" / "tool-results"
TRANSCRIPT_DIR = Path.cwd() / ".transcripts"

# Defaults (can be overridden via config)
KEEP_RECENT_TOOL_RESULTS = 3
PERSIST_THRESHOLD = 30000
PREVIEW_CHARS = 2000
CONTEXT_LIMIT = 50000


def _msg_to_dict(msg: BaseMessage) -> dict:
    """Serialize a BaseMessage to a plain dict for size estimation."""
    return {
        "type": type(msg).__name__,
        "content": msg.content,
        "tool_calls": getattr(msg, "tool_calls", None),
        "tool_call_id": getattr(msg, "tool_call_id", None),
        "name": getattr(msg, "name", None),
    }


class ContextCompactor:
    """
    Context compaction utilities.

    Three mechanisms:
    1. Large output persistence -- tool outputs > threshold are saved to disk.
    2. Micro-compaction -- old tool results are replaced with placeholders.
    3. History summarization -- when total context is too large, summarize it.
    """

    @staticmethod
    def persist_large_output(tool_use_id: str, output: str,
                             persist_threshold: int = PERSIST_THRESHOLD,
                             preview_chars: int = PREVIEW_CHARS) -> str:
        """Persist large tool output to disk and return a preview marker."""
        if len(output) <= persist_threshold:
            return output

        TOOL_RESULTS_DIR.mkdir(parents=True, exist_ok=True)
        stored_path = TOOL_RESULTS_DIR / f"{tool_use_id}.txt"
        if not stored_path.exists():
            stored_path.write_text(output, encoding="utf-8")

        preview = output[:preview_chars]
        try:
            rel_path = stored_path.relative_to(Path.cwd())
        except ValueError:
            rel_path = stored_path

        return (
            "<persisted-output>\n"
            f"Full output saved to: {rel_path}\n"
            "Preview:\n"
            f"{preview}\n"
            "</persisted-output>"
        )

    @staticmethod
    def estimate_context_size(messages: list[BaseMessage]) -> int:
        """Estimate the size of a message list when serialized."""
        return len(json.dumps([_msg_to_dict(m) for m in messages], ensure_ascii=False, default=str))

    @staticmethod
    def micro_compact(messages: list[BaseMessage],
                      keep_recent: int = KEEP_RECENT_TOOL_RESULTS) -> list[BaseMessage]:
        """
        Replace old ToolMessage contents with placeholders.

        Returns a new list; the original is not modified.
        """
        tool_indices = [
            i for i, msg in enumerate(messages)
            if isinstance(msg, ToolMessage)
        ]
        if len(tool_indices) <= keep_recent:
            return list(messages)

        new_messages = list(messages)
        for idx in tool_indices[:-keep_recent]:
            msg = new_messages[idx]
            content = msg.content
            if not isinstance(content, str) or len(content) <= 120:
                continue
            new_messages[idx] = ToolMessage(
                content="[Earlier tool result compacted. Re-run the tool if you need full detail.]",
                tool_call_id=msg.tool_call_id,
                name=msg.name,
            )
        return new_messages

    @staticmethod
    def write_transcript(messages: list[BaseMessage]) -> Path:
        """Save the current message list as a JSONL transcript."""
        TRANSCRIPT_DIR.mkdir(parents=True, exist_ok=True)
        path = TRANSCRIPT_DIR / f"transcript_{int(time.time())}.jsonl"
        with path.open("w", encoding="utf-8") as handle:
            for msg in messages:
                handle.write(json.dumps(_msg_to_dict(msg), ensure_ascii=False, default=str) + "\n")
        return path

    @staticmethod
    async def compact_history(
        messages: list[BaseMessage],
        chat_model,
        context_limit: int = CONTEXT_LIMIT,
    ) -> str:
        """
        Summarize the conversation history using an LLM.

        Returns the summary text.
        """
        transcript_path = ContextCompactor.write_transcript(messages)
        print(f"[transcript saved: {transcript_path}]")

        # Build a truncated conversation string for the summary prompt
        conversation = json.dumps([_msg_to_dict(m) for m in messages], ensure_ascii=False, default=str)
        conversation = conversation[:80000]

        prompt = (
            "Summarize this coding-agent conversation so work can continue.\n"
            "Preserve:\n"
            "1. The current goal\n"
            "2. Important findings and decisions\n"
            "3. Files read or changed\n"
            "4. Remaining work\n"
            "5. User constraints and preferences\n"
            "Be compact but concrete.\n\n"
            f"{conversation}"
        )

        summary_msg = HumanMessage(content=prompt)
        response = await chat_model.ainvoke([summary_msg])
        summary = response.content.strip() if isinstance(response.content, str) else str(response.content).strip()
        print(f"[context compacted: {len(summary)} chars]")
        return summary
