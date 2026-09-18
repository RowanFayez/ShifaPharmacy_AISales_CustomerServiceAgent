from typing import Annotated, TypedDict
from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages
class AgentState(TypedDict, total=False):
    messages: Annotated[list[BaseMessage], add_messages]; conversation_id: int | None; customer_id: int | None; language: str | None
    plan: dict | None; retrieved: list[dict]; catalog_results: list[dict]; tool_results: list[dict]; pending_action: dict | None
    safety_flag: str | None; needs_human: bool; error: str | None; response: str | None
