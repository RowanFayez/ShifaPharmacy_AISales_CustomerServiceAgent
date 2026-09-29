from langchain_core.messages import AIMessage, HumanMessage

from agent.nodes import synthesizer as synthesizer_module


def test_llm_numeric_hallucination_falls_back_to_live_catalog(app, monkeypatch):
    class FakeModel:
        def invoke(self, _messages):
            return AIMessage(content="Panadol is available for EGP 999.00 with 999 units in stock.")

    monkeypatch.setenv("LLM_SYNTHESIZER_IN_TESTS", "true")
    monkeypatch.setattr(synthesizer_module, "get_chat_model", lambda model_name=None: FakeModel())
    state = {
        "language": "en",
        "messages": [HumanMessage(content="Do you have Panadol?")],
        "plan": {"intent": "sales", "rationale": "catalog availability or price question", "product_mentions": ["Panadol"]},
        "catalog_results": [{"name": "Panadol 500 mg Tablets 24", "price": "58.00", "stock_quantity": 10, "requires_prescription": False}],
        "tool_results": [{"name": "search_products", "ok": True, "data": [{"price": "58.00", "stock_quantity": 10}]}],
    }
    with app.app_context():
        result = synthesizer_module.synthesizer(state)

    assert "999" not in result["response"]
    assert "58.00" in result["response"]
