def final_guardrail(state):
    text = state.get("response", "")
    if state.get("safety_flag") == "rx_required": text = "A valid prescription is required before this medicine can be ordered."
    return {"response": text}
