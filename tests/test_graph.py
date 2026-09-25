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
        from app.models import Lead
        assert db.session.query(Lead).filter_by(lead_type="prescription_request").count() == 1
    assert result["safety_flag"] == "rx_required"
    assert "prescription" in result["response"].casefold()

def test_graph_confirmation_creates_a_real_order(app, pharmacy_data):
    with app.app_context():
        result = build_graph().invoke({"messages": [HumanMessage(content="yes")], "conversation_id": None, "customer_id": pharmacy_data["customer_id"], "pending_action": {"customer_ref": str(pharmacy_data["customer_id"]), "items": [{"product_id": pharmacy_data["product_id"], "quantity": 1}], "address": "Cairo"}}, config={"configurable": {"thread_id": "confirmation-test"}})
    assert result["tool_results"][-1]["ok"] is True
    assert "created" in result["response"].casefold()

def test_checkpointer_keeps_pending_order_between_turns(app, pharmacy_data, monkeypatch):
    from agent.nodes import reasoner as reasoner_module
    class FakeStructured:
        def invoke(self, _):
            from agent.schemas import Plan
            return Plan(intent="sales", language="en", needs_catalog_lookup=True, product_mentions=["Panadol"], wants_to_order=True, rationale="test")
    class FakeModel:
        def with_structured_output(self, _): return FakeStructured()
    monkeypatch.setattr(reasoner_module, "get_chat_model", lambda *args: FakeModel())
    with app.app_context():
        graph = build_graph(); config = {"configurable": {"thread_id": "persistent-confirmation"}}
        first = graph.invoke({"messages": [HumanMessage(content="I want Panadol")], "conversation_id": None, "customer_id": pharmacy_data["customer_id"]}, config=config)
        second = graph.invoke({"messages": [HumanMessage(content="yes")], "conversation_id": None, "customer_id": pharmacy_data["customer_id"]}, config=config)
    # Existing customer context can still use the normal confirm-and-create
    # path; browser chats without customer context use the details collector.
    assert first["pending_action"] is not None
    assert second["tool_results"][-1]["ok"] is True


def test_catalog_offer_collects_real_checkout_details_then_creates_order(app, pharmacy_data):
    from app.extensions import db
    from app.models import Product
    with app.app_context():
        graph = build_graph()
        config = {"configurable": {"thread_id": "offered-product-memory"}}
        first = graph.invoke(
            {"messages": [HumanMessage(content="هل يوجد بانادول؟")], "conversation_id": None, "customer_id": None},
            config=config,
        )
        second = graph.invoke(
            {"messages": [HumanMessage(content="طيب عايزة اعمل اوردر بيه")], "conversation_id": None, "customer_id": None},
            config=config,
        )
        stock_before = db.session.get(Product, pharmacy_data["product_id"]).stock_quantity
        details = graph.invoke(
            {"messages": [HumanMessage(content="الاسم: روان فايز، الموبايل: 01098765432، العنوان: الحديد والصلب")], "conversation_id": None, "customer_id": None},
            config=config,
        )
        stock_after_quote = db.session.get(Product, pharmacy_data["product_id"]).stock_quantity
        confirmed = graph.invoke(
            {"messages": [HumanMessage(content="تمام")], "conversation_id": None, "customer_id": details["customer_id"]},
            config=config,
        )
        stock_after_order = db.session.get(Product, pharmacy_data["product_id"]).stock_quantity
    assert first["last_catalog_product"]["name"] == "Panadol 500 mg Tablets 24"
    assert second["order_stage"] == "collect_details"
    assert "رقم الموبايل" in second["response"]
    assert details["pending_action"]["items"] == [{"product_id": pharmacy_data["product_id"], "quantity": 1}]
    assert "روان فايز" in details["response"]
    assert "93.00" in details["response"]
    assert stock_after_quote == stock_before
    assert confirmed["tool_results"][-1]["ok"] is True
    assert stock_after_order == stock_before - 1

def test_graph_uses_live_catalog_price_for_sales_answer(app, pharmacy_data, monkeypatch):
    from agent.nodes import reasoner as reasoner_module
    class FakeStructured:
        def invoke(self, _):
            from agent.schemas import Plan
            return Plan(intent="sales", language="en", needs_catalog_lookup=True, product_mentions=["Panadol"], rationale="test")
    class FakeModel:
        def with_structured_output(self, _): return FakeStructured()
    monkeypatch.setattr(reasoner_module, "get_chat_model", lambda *args: FakeModel())
    with app.app_context():
        result = build_graph().invoke({"messages": [HumanMessage(content="How much is Panadol?")], "conversation_id": None}, config={"configurable": {"thread_id": "sales-price"}})
    assert "EGP 58.00" in result["response"]

def test_graph_order_status_and_escalation_branches(app, pharmacy_data, monkeypatch):
    from agent.nodes import reasoner as reasoner_module
    from app.extensions import db
    from app.models import Conversation
    class EscalationStructured:
        def invoke(self, _):
            from agent.schemas import Plan
            return Plan(intent="escalation", language="en", rationale="human requested")
    class EscalationModel:
        def with_structured_output(self, _): return EscalationStructured()
    with app.app_context():
        graph = build_graph()
        conversation = Conversation(customer_id=pharmacy_data["customer_id"], channel="web", external_thread_id="escalation-test")
        db.session.add(conversation); db.session.commit()
        status = graph.invoke({"messages": [HumanMessage(content="SHF-TEST-001")], "conversation_id": None, "customer_id": pharmacy_data["customer_id"]}, config={"configurable": {"thread_id": "status-branch"}})
        monkeypatch.setattr(reasoner_module, "get_chat_model", lambda *args: EscalationModel())
        escalated = graph.invoke({"messages": [HumanMessage(content="Please connect me to a pharmacist")], "conversation_id": conversation.id, "customer_id": pharmacy_data["customer_id"]}, config={"configurable": {"thread_id": "escalation-branch"}})
    assert "SHF-TEST-001" in status["response"] and "pending" in status["response"]
    assert escalated["needs_human"] is True


def test_reasoner_cache_reuses_a_validated_llm_plan(monkeypatch, tmp_path):
    from agent.cache import ReasonerCache
    from agent.nodes import reasoner as reasoner_module
    calls = {"count": 0}

    class FakeStructured:
        def invoke(self, _):
            calls["count"] += 1
            from agent.schemas import Plan
            return Plan(intent="customer_service", language="en", needs_rag=True, rationale="test")

    class FakeModel:
        def with_structured_output(self, _): return FakeStructured()

    monkeypatch.setattr(reasoner_module, "get_chat_model", lambda *args: FakeModel())
    monkeypatch.setattr(reasoner_module, "ReasonerCache", lambda: ReasonerCache(str(tmp_path / "reasoner.db")))
    state = {"messages": [HumanMessage(content="Could I speak to customer support?")], "language": "en"}

    first = reasoner_module.reasoner(state)
    second = reasoner_module.reasoner(state)

    assert first["plan"] == second["plan"]
    assert calls["count"] == 1


def test_bare_order_intent_is_deterministic_without_llm():
    from agent.nodes.reasoner import reasoner
    result = reasoner({"messages": [HumanMessage(content="I want to place an order")], "language": "en"})
    assert result["plan"]["wants_to_order"] is True
    assert result["plan"]["rationale"] == "order intent without product"


def test_anemia_is_escalated_without_catalog_suggestion(app):
    with app.app_context():
        result = build_graph().invoke(
            {"messages": [HumanMessage(content="I have anemia")], "conversation_id": None},
            config={"configurable": {"thread_id": "anemia-safety"}},
        )
    assert result["needs_human"] is True
    assert not result["catalog_results"]
    assert "anemia" in result["response"].casefold()


def test_first_messenger_turn_gets_welcome():
    from agent.nodes.synthesizer import synthesizer
    result = synthesizer({
        "channel": "messenger", "is_first_turn": True, "language": "en",
        "plan": {"rationale": "thanks"},
    })
    assert result["response"].startswith("Welcome to Shifa Pharmacy")
