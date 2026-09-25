"""LangGraph wiring only; node behavior lives in agent.nodes."""
from langgraph.graph import END, START, StateGraph
from agent.state import AgentState
from agent.nodes.context import load_context, persist_turn
from agent.nodes.order_details import order_details
from agent.nodes.symptom_router import symptom_router
from agent.nodes.reasoner import reasoner
from agent.nodes.executor import escalation_exec, executor_catalog, executor_product_info, executor_order_status, executor_rag, executor_tools
from agent.nodes.gates import confirmation_gate, rx_gate, safety_handler
from agent.nodes.synthesizer import synthesizer
from agent.nodes.guardrail import final_guardrail
def route_plan(state):
    intent = (state.get("plan") or {}).get("intent")
    rationale = (state.get("plan") or {}).get("rationale")
    if rationale == "product info follow-up": return "executor_product_info"
    if rationale == "order intent without product": return "synthesizer"
    return "safety_handler" if intent == "safety" else "escalation_exec" if intent == "escalation" else "executor_order_status" if intent == "order_status" else "confirmation_gate" if intent == "order_action" else "executor_catalog" if intent == "sales" else "executor_rag"
def route_symptom(state):
    tier = state.get("symptom_tier")
    return "safety_handler" if tier == "tier2" else "synthesizer" if tier == "clarify" else "reasoner"
def route_after_order_details(state): return "synthesizer" if state.get("order_details_handled") else "symptom_router"
def route_after_catalog(state): return "safety_handler" if state.get("safety_flag") == "rx_required" else "confirmation_gate" if (state.get("plan") or {}).get("wants_to_order") else "synthesizer"
def route_confirmation(state): return "executor_tools" if (state.get("plan") or {}).get("confirming_previous_action") else "synthesizer"
def build_graph(checkpointer=None):
    if checkpointer is None:
        import sqlite3
        from pathlib import Path
        from langgraph.checkpoint.sqlite import SqliteSaver
        path = Path("data/cache/agent_checkpoints.db"); path.parent.mkdir(parents=True, exist_ok=True)
        checkpointer = SqliteSaver(sqlite3.connect(path, check_same_thread=False))
    graph = StateGraph(AgentState)
    for name, node in [("load_context", load_context), ("order_details", order_details), ("symptom_router", symptom_router), ("reasoner", reasoner), ("executor_catalog", executor_catalog), ("executor_product_info", executor_product_info), ("executor_rag", executor_rag), ("executor_order_status", executor_order_status), ("escalation_exec", escalation_exec), ("rx_gate", rx_gate), ("confirmation_gate", confirmation_gate), ("executor_tools", executor_tools), ("safety_handler", safety_handler), ("synthesizer", synthesizer), ("final_guardrail", final_guardrail), ("persist_turn", persist_turn)]: graph.add_node(name, node)
    graph.add_edge(START, "load_context"); graph.add_edge("load_context", "order_details"); graph.add_conditional_edges("order_details", route_after_order_details); graph.add_conditional_edges("symptom_router", route_symptom); graph.add_conditional_edges("reasoner", route_plan); graph.add_edge("executor_catalog", "rx_gate"); graph.add_conditional_edges("rx_gate", route_after_catalog); graph.add_edge("executor_product_info", "synthesizer"); graph.add_edge("executor_rag", "synthesizer"); graph.add_edge("executor_order_status", "synthesizer"); graph.add_edge("escalation_exec", "synthesizer"); graph.add_conditional_edges("confirmation_gate", route_confirmation); graph.add_edge("executor_tools", "synthesizer"); graph.add_edge("safety_handler", "synthesizer"); graph.add_edge("synthesizer", "final_guardrail"); graph.add_edge("final_guardrail", "persist_turn"); graph.add_edge("persist_turn", END)
    return graph.compile(checkpointer=checkpointer)
