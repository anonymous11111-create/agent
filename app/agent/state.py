from typing import TypedDict, Optional, Annotated
from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages


class AgentState(TypedDict, total=False):
    messages: Annotated[list[BaseMessage], add_messages]
    step_count: int
    terminated: bool
    tool_call_history: list[str]  # dedup keys: "toolName:args"
    start_time: float
    error: Optional[str]
    compacted_summary: Optional[str]  # cached summary from context compaction
