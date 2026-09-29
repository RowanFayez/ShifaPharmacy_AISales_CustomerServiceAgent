from langchain_core.messages import HumanMessage

from agent.graph import build_graph
from agent.tools import search_products


def test_misspelled_product_returns_nearest_catalog_alternative(app, pharmacy_data):
    with app.app_context():
        result = search_products({"query": "panadoll"})

    assert result["ok"] is False
    assert result["error_code"] == "NO_EXACT_MATCH"
    assert result["data"]
    assert result["data"][0]["name"] == "Panadol 500 mg Tablets 24"


def test_nearest_alternative_is_not_ordered_without_exact_match(app, pharmacy_data):
    with app.app_context():
        result = build_graph().invoke(
            {"messages": [HumanMessage(content="do you have panadoll")], "conversation_id": None},
            config={"configurable": {"thread_id": "catalog-fallback-order-guard"}},
        )

    assert result["catalog_exact_match"] is False
    assert result["catalog_results"]
    assert result["pending_action"] is None
    assert "could not find" in result["response"].casefold()
