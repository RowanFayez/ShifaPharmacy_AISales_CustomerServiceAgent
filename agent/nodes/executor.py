from langchain_core.messages import HumanMessage
from agent.tools import TOOL_REGISTRY
from app.services.kb_service import get_index
def _text(state): return next((m.content for m in reversed(state.get("messages", [])) if isinstance(m, HumanMessage)), "")
def executor_catalog(state):
    plan = state["plan"]; terms = plan.get("product_mentions") or [_text(state)]
    results = TOOL_REGISTRY["search_products"]({"query": " ".join(terms), "otc_only": False, "lang": state.get("language", "en")})
    return {"catalog_results": results.get("data") or [], "tool_results": [results]}
def executor_rag(state):
    return {"retrieved": get_index().retrieve(_text(state)), "tool_results": state.get("tool_results", [])}
def executor_tools(state):
    pending = state.get("pending_action") or {}; result = TOOL_REGISTRY["create_order"](pending)
    return {"tool_results": state.get("tool_results", []) + [result], "pending_action": None if result["ok"] else pending}
