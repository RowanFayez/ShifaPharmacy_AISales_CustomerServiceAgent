from langchain_core.messages import AIMessage, HumanMessage

from agent.nodes import synthesizer as synthesizer_module


def test_synthesizer_uses_grounded_llm_for_natural_sales_reply(app, monkeypatch):
    captured = {}

    class FakeModel:
        def invoke(self, messages):
            captured["system"] = messages[0].content
            return AIMessage(content="Yes—Panadol 500 mg is available for EGP 58.00. Would you like one?")

    monkeypatch.setenv("LLM_SYNTHESIZER_IN_TESTS", "true")
    monkeypatch.setattr(synthesizer_module, "get_chat_model", lambda model_name=None: FakeModel())
    state = {
        "language": "en",
        "messages": [HumanMessage(content="Do you have Panadol?")],
        "plan": {"intent": "sales", "rationale": "catalog availability or price question"},
        "catalog_results": [{"name": "Panadol 500 mg Tablets 24", "price": "58.00", "stock_quantity": 10, "requires_prescription": False}],
        "tool_results": [{"name": "search_products", "ok": True, "data": [{"name": "Panadol 500 mg Tablets 24", "price": "58.00", "stock_quantity": 10}]}],
    }
    with app.app_context():
        result = synthesizer_module.synthesizer(state)

    assert result["response"].startswith("Yes—Panadol")
    assert "Panadol 500 mg Tablets 24" in captured["system"]
    assert "58.00" in captured["system"]


def test_safety_response_never_delegates_to_llm(app, monkeypatch):
    def fail_if_called(*_args, **_kwargs):
        raise AssertionError("safety response must remain deterministic")

    monkeypatch.setenv("LLM_SYNTHESIZER_IN_TESTS", "true")
    monkeypatch.setattr(synthesizer_module, "get_chat_model", fail_if_called)
    state = {
        "language": "en",
        "response": "A pharmacist should review this request.",
        "symptom_tier": "tier2",
        "needs_human": True,
        "messages": [HumanMessage(content="I have chest pain")],
    }
    with app.app_context():
        result = synthesizer_module.synthesizer(state)

    assert result["response"] == "A pharmacist should review this request."
