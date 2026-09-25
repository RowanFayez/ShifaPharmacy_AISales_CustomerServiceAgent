from langchain_core.messages import HumanMessage
from agent.graph import build_graph
from agent.lang import detect_language


def test_language_detection_supports_english_arabic_and_masri():
    assert detect_language("Do you have Panadol?") == "en"
    assert detect_language("عندكم بانادول؟") == "ar"
    assert detect_language("هو عندكو بانادول بكام يا اسطا؟") == "masri"


def test_safety_responses_follow_current_language(app):
    with app.app_context():
        arabic = build_graph().invoke({"messages": [HumanMessage(content="ما هي جرعة هذا الدواء؟")], "conversation_id": None}, config={"configurable": {"thread_id": "ar-safety"}})
        masri = build_graph().invoke({"messages": [HumanMessage(content="عايز جرعة الدوا يا اسطا")], "conversation_id": None}, config={"configurable": {"thread_id": "masri-safety"}})
    assert arabic["language"] == "ar" and "الصيدلي" in arabic["response"]
    assert masri["language"] == "masri" and "الصيدلي" in masri["response"]


def test_product_search_reports_no_results_distinctly(app):
    from agent.tools import search_products
    with app.app_context():
        result = search_products({"query": "not-a-real-pharmacy-product"})
    assert result["ok"] is False and result["error_code"] == "NO_RESULTS"


def test_unknown_arabic_product_availability_skips_the_llm(app):
    from agent.nodes.reasoner import reasoner

    plan = reasoner({"messages": [HumanMessage(content="في ميرفين؟")], "language": "ar"})["plan"]
    assert plan["intent"] == "sales"
    assert plan["needs_catalog_lookup"] is True
