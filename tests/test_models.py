from decimal import Decimal

from sqlalchemy import select

from app.extensions import db
from app.models import KnowledgeDocument, Product
from scripts import seed_db


def test_product_persists_multilingual_catalog_fields(pharmacy_data):
    product = db.session.get(Product, pharmacy_data["product_id"])

    assert product.name_ar == "بانادول 500 مجم 24 قرص"
    assert "بنادول" in product.aliases
    assert product.requires_prescription is False
    assert product.price == Decimal("58.00")


def test_seed_data_has_required_scale_rx_products_and_bilingual_knowledge(app):
    with app.app_context():
        categories = seed_db.seed_categories()
        seed_db.seed_products(categories)
        seed_db.seed_customers()
        db.session.flush()
        seed_db.seed_knowledge()
        seed_db.seed_sample_orders()
        db.session.commit()

        products = db.session.scalars(select(Product)).all()
        knowledge = db.session.scalars(select(KnowledgeDocument)).all()

        assert len(products) == 40
        assert sum(product.requires_prescription for product in products) == 8
        assert len(knowledge) == 15
        assert all(document.lang == "bilingual" for document in knowledge)
        assert all("**English:**" in document.content and "**العربية:**" in document.content for document in knowledge)
