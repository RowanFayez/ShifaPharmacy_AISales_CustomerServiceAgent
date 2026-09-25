from decimal import Decimal
from agent import tools
from app.extensions import db
from app.models import Product

def test_create_order_is_real_and_decrements_stock(app, pharmacy_data):
    with app.app_context():
        product = db.session.get(Product, pharmacy_data["product_id"]); before = product.stock_quantity
        result = tools.create_order({"customer_ref": "01012345678", "items": [{"product_id": product.id, "quantity": 2}], "address": "Cairo"})
        assert result["ok"] and result["data"]["order_number"].startswith("SHF-")
        assert db.session.get(Product, product.id).stock_quantity == before - 2

def test_rx_product_is_rejected_without_stock_change(app, pharmacy_data):
    with app.app_context():
        product = db.session.get(Product, pharmacy_data["product_id"]); product.requires_prescription = True; db.session.commit(); before = product.stock_quantity
        result = tools.create_order({"customer_ref": "01012345678", "items": [{"product_id": product.id, "quantity": 1}], "address": "Cairo"})
        assert result["ok"] is False and result["error_code"] == "PRESCRIPTION_REQUIRED"
        assert db.session.get(Product, product.id).stock_quantity == before

def test_tool_arguments_are_validated():
    result = tools.create_order({"customer_ref": "x", "items": [], "address": ""})
    assert result["ok"] is False and result["error_code"] == "INVALID_ARGUMENTS"
