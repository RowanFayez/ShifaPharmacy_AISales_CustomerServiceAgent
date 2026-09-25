import pytest
from langchain_core.messages import HumanMessage
from uuid import uuid4

from agent.graph import build_graph
from agent.nodes.reasoner import reasoner
from agent.nodes.symptom_router import classify_symptom


@pytest.mark.parametrize("message", [
    "I have a mild headache", "I have a common cold", "I have a mild cough", "My throat is sore",
    "عندي صداع بسيط", "عندي برد خفيف", "عندي كحة بسيطة", "حلقي بيوجعني",
    "عندي صداع خفيف يا اسطى", "عندي برد بسيط", "عندي كحة خفيفة", "زوري بيوجعني",
])
def test_tier_one_symptoms_route_to_an_otc_category(message):
    decision = classify_symptom(message)
    assert decision.tier == "tier1"
    assert decision.category is not None


@pytest.mark.parametrize("message", [
    "I have chest pain", "I have difficulty breathing", "I have a persistent high fever", "My child has a cough",
    "عندي ألم في الصدر", "عندي صعوبة تنفس", "عندي حرارة عالية مستمرة", "طفلي عنده كحة",
    "صدري بيوجعني جامد", "مش عارف اتنفس", "حرارتي عالية بقالها يومين", "ابني عنده كحة",
])
def test_tier_two_red_flags_always_escalate(message):
    assert classify_symptom(message).tier == "tier2"


@pytest.mark.parametrize("message", ["I have anemia", "عندي أنيميا", "عندي فقر دم"])
def test_anemia_is_medical_escalation_not_product_matching(message):
    assert classify_symptom(message).tier == "tier2"


@pytest.mark.parametrize("message", ["How much should I take?", "ما هي جرعة بروفين؟", "هاخد كام قرص يا اسطى؟"])
def test_dosage_questions_are_always_tier_two(message):
    assert classify_symptom(message).tier == "tier2"


def test_unclear_health_message_gets_one_clarifying_question(app):
    with app.app_context():
        result = build_graph().invoke(
            {"messages": [HumanMessage(content="I am not feeling well")], "conversation_id": None},
            config={"configurable": {"thread_id": f"symptom-clarify:{uuid4()}"}},
        )
    assert result["symptom_tier"] == "clarify"
    assert result["needs_human"] is False
    assert result["response"] == "Are the symptoms mild, or is there a warning sign such as trouble breathing?"


def test_tier_one_graph_response_uses_otc_catalog_and_disclaimer(app, pharmacy_data):
    with app.app_context():
        result = build_graph().invoke(
            {"messages": [HumanMessage(content="I have a mild headache")], "conversation_id": None},
            config={"configurable": {"thread_id": f"symptom-tier-one:{uuid4()}"}},
        )
    assert result["symptom_tier"] == "tier1"
    assert result["catalog_results"] and all(not product["requires_prescription"] for product in result["catalog_results"])
    assert "not a diagnosis" in result["response"]


def test_arabic_otc_catalog_response_is_not_replaced_by_guardrail(app, pharmacy_data):
    with app.app_context():
        result = build_graph().invoke(
            {"messages": [HumanMessage(content="قول منتجات البرد")], "conversation_id": None},
            config={"configurable": {"thread_id": f"arabic-catalog:{uuid4()}"}},
        )
    assert result["catalog_results"]
    assert "المتاح حاليًا" in result["response"]
    assert "لا أستطيع تشخيص" not in result["response"]


def test_tier_two_graph_response_hard_escalates_without_catalog_lookup(app):
    with app.app_context():
        result = build_graph().invoke(
            {"messages": [HumanMessage(content="I have chest pain")], "conversation_id": None},
            config={"configurable": {"thread_id": f"symptom-tier-two:{uuid4()}"}},
        )
    assert result["symptom_tier"] == "tier2"
    assert result["needs_human"] is True and result["catalog_results"] == []
    assert "pharmacist" in result["response"].casefold()


def test_egyptian_order_intent_is_not_lost_in_catalog_routing():
    plan = reasoner({"messages": [HumanMessage(content="عايز فيتامين")], "language": "masri"})["plan"]
    assert plan["intent"] == "sales"
    assert plan["wants_to_order"] is True
