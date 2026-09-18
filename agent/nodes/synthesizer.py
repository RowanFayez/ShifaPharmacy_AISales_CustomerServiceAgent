from langchain_core.messages import AIMessage
def synthesizer(state):
    if state.get("response"): return {"messages": [AIMessage(content=state["response"])]}
    if state.get("safety_flag") == "rx_required": text = "This product requires a valid prescription. I can arrange pharmacist assistance."
    elif state.get("pending_action"): text = "Please confirm the order details before I create it."
    elif state.get("tool_results") and state["tool_results"][-1].get("ok") and state["tool_results"][-1].get("data", {}).get("order_number"): text = f"Your order {state['tool_results'][-1]['data']['order_number']} has been created."
    elif state.get("retrieved"): text = state["retrieved"][0]["content"]
    elif state.get("catalog_results"): text = "I found: " + ", ".join(f"{p['name']} — EGP {p['price']}" for p in state["catalog_results"])
    else: text = "I don't have that information. I can connect you with a pharmacist."
    return {"response": text, "messages": [AIMessage(content=text)]}
