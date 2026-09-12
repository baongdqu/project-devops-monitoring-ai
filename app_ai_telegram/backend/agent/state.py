from typing import TypedDict, Annotated, Sequence
from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages

class AgentState(TypedDict):
    """Trạng thái trung tâm được chia sẻ giữa các nodes trong LangGraph"""
    messages: Annotated[Sequence[BaseMessage], add_messages]
    step_count: int
    is_complete: bool
    system_prompt: str | None
    user_id: str | None
    model: str | None
    disabled_tools: list[str] | None
