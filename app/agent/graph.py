import time
import logging
from typing import Optional

from langgraph.graph import StateGraph, END
from langchain_core.runnables import RunnableConfig

from app.agent.state import AgentState
from app.agent.think_node import think_node
from app.agent.execute_node import execute_node
from app.agent.router import should_continue

logger = logging.getLogger(__name__)


def build_agent_graph():
    """Build the LangGraph StateGraph for the agent think-execute loop.

    Topology:
        START -> think -> [should_continue]
                            |-"execute"-> execute -> think (loop)
                            |-"end"-> END
    """
    graph = StateGraph(AgentState)

    graph.add_node("think", think_node)
    graph.add_node("execute", execute_node)

    graph.set_entry_point("think")

    graph.add_conditional_edges(
        "think",
        should_continue,
        {"execute": "execute", "end": END},
    )

    graph.add_edge("execute", "think")

    return graph.compile()
