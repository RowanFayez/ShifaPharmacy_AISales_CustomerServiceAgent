from langchain_core.messages import HumanMessage
from agent.graph import build_graph

def test_graph_safety_branch_uses_no_llm(app):
    with app.app_context():
        graph = build_graph()
        result = graph.invoke({"messages": [HumanMessage(content="Please diagnose my symptoms")], "conversation_id": None}, config={"configurable": {"thread_id": "safety-test"}})
    assert result["needs_human"] is True
    assert "pharmacist" in result["response"].casefold()

def test_graph_has_prescription_gate(app, pharmacy_data, monkeypatch):
    from agent.nodes import reasoner as reasoner_module
    class FakeStructured:
        def invoke(self, _):
            from agent.schemas import Plan
            return Plan(intent="sales", language="en", needs_catalog_lookup=True, product_mentions=["Panadol"], wants_to_order=True, rationale="test")
    class FakeModel:
        def with_structured_output(self, _): return FakeStructured()
    monkeypatch.setattr(reasoner_module, "get_chat_model", lambda: FakeModel())
    with app.app_context():
        from app.extensions import db
        from app.models import Product
        db.session.get(Product, pharmacy_data["product_id"]).requires_prescription = True; db.session.commit()
        result = build_graph().invoke({"messages": [HumanMessage(content="I want Panadol")], "conversation_id": None, "customer_id": pharmacy_data["customer_id"]}, config={"configurable": {"thread_id": "rx-test"}})
    assert result["safety_flag"] == "rx_required"
    assert "prescription" in result["response"].casefold()

def test_graph_confirmation_creates_a_real_order(app, pharmacy_data):
    with app.app_context():
        result = build_graph().invoke({"messages": [HumanMessage(content="yes")], "conversation_id": None, "customer_id": pharmacy_data["customer_id"], "pending_action": {"customer_ref": str(pharmacy_data["customer_id"]), "items": [{"product_id": pharmacy_data["product_id"], "quantity": 1}], "address": "Cairo"}}, config={"configurable": {"thread_id": "confirmation-test"}})
    assert result["tool_results"][-1]["ok"] is True
    assert "created" in result["response"].casefold()
