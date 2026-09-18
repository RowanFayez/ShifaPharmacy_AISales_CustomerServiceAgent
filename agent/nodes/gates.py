def rx_gate(state):
    if any(item.get("requires_prescription") for item in state.get("catalog_results", [])): return {"safety_flag": "rx_required"}
    return {"safety_flag": None}
def confirmation_gate(state):
    if state.get("pending_action"): return {}
    plan = state.get("plan") or {}; items = [{"product_id": p["id"], "quantity": plan.get("quantities", {}).get(p["name"], 1)} for p in state.get("catalog_results", [])[:1]]
    return {"pending_action": {"customer_ref": str(state.get("customer_id") or ""), "items": items, "address": "Confirm delivery address"}}
def safety_handler(state):
    return {"response": "I can’t provide diagnosis or dosage advice. Please speak with a pharmacist.", "needs_human": True}
