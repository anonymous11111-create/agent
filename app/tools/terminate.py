from langchain_core.tools import tool


@tool
def terminate():
    """仅在用户明确说"结束"/"再见"/"不聊了"时调用此工具。不要在未给出完整回答前调用。"""
    return "TERMINATE"
