"""Last deterministic safety pass before an answer reaches a customer."""
from agent.prompts import ar, en, masri

def final_guardrail(state):
    text = state.get("response", "")
    prompt = {"ar": ar, "masri": masri}.get(state.get("language"), en)
    if state.get("safety_flag") == "rx_required": text = prompt.RX
    # A safe OTC disclaimer legitimately contains words such as "diagnosis".
    # Only block actionable treatment/dosage language here, not the disclaimer
    # attached to a catalog response.
    if any(term in text.casefold() for term in ("take ", "dosage", "جرعة", "خذ ", "خد ")): text = prompt.SAFETY
    return {"response": text}
