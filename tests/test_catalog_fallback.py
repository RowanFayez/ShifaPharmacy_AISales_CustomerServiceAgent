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


def test_specific_vitamin_query_does_not_expand_to_the_whole_category(app):
    from decimal import Decimal
    from app.extensions import db
    from app.models import Category, Product

    with app.app_context():
        category = Category(name="Vitamins & Supplements", slug="vitamins-supplements")
        db.session.add(category)
        db.session.add(Product(
            sku="VIT-C-1000-20", name="Vitamin C 1000 mg Effervescent 20",
            name_ar="فيتامين سي 1000 مجم فوار 20 قرص", generic_name="ascorbic acid",
            aliases="vitamin c, فيتامين سي", category=category, price=Decimal("110.00"),
            stock_quantity=70,
        ))
        db.session.add(Product(
            sku="VIT-D3-5000-30", name="Vitamin D3 5000 IU Capsules 30",
            name_ar="فيتامين د3 5000 وحدة 30 كبسولة", generic_name="cholecalciferol",
            aliases="vitamin d, فيتامين د", category=category, price=Decimal("210.00"),
            stock_quantity=42,
        ))
        db.session.commit()
        result = search_products({"query": "فيتامين سي"})

    assert result["ok"] is True
    assert [item["name"] for item in result["data"]] == ["Vitamin C 1000 mg Effervescent 20"]


def test_exact_product_first_rule_applies_to_medicines_and_arabic_aliases(app, pharmacy_data):
    from decimal import Decimal
    from app.extensions import db
    from app.models import Product

    with app.app_context():
        category = db.session.get(Product, pharmacy_data["product_id"]).category
        db.session.add(Product(
            sku="OTC-BRUF-400-20", name="Brufen 400 mg Tablets 20",
            name_ar="بروفين 400 مجم 20 قرص", generic_name="ibuprofen",
            aliases="brufen, بروفين, ibuprofen", category=category,
            price=Decimal("65.00"), stock_quantity=20,
        ))
        db.session.commit()
        english = search_products({"query": "Panadol"})
        arabic = search_products({"query": "بروفين"})

    assert [item["name"] for item in english["data"]] == ["Panadol 500 mg Tablets 24"]
    assert [item["name"] for item in arabic["data"]] == ["Brufen 400 mg Tablets 20"]
