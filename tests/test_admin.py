from app.extensions import db
from app.models import Category, Order, Product


def test_category_and_product_crud(client, app, pharmacy_data):
    response = client.post(
        "/admin/categories/new",
        data={"name": "Medical Devices", "slug": "medical-devices", "description": "Home health devices", "active": "y"},
        follow_redirects=True,
    )
    assert response.status_code == 200
    assert b"Category created." in response.data

    with app.app_context():
        devices = db.session.query(Category).filter_by(slug="medical-devices").one()

    response = client.post(
        "/admin/products/new",
        data={
            "sku": "DEV-THERMO-DIG",
            "name": "Digital Thermometer",
            "name_ar": "ترمومتر ديجيتال",
            "generic_name": "digital thermometer",
            "aliases": "thermometer, ترمومتر",
            "category_id": devices.id,
            "brand": "Generic",
            "price": "105.00",
            "stock_quantity": "12",
            "short_description": "Digital temperature monitor.",
            "active": "y",
        },
        follow_redirects=True,
    )
    assert response.status_code == 200
    assert b"Product created." in response.data

    with app.app_context():
        product = db.session.query(Product).filter_by(sku="DEV-THERMO-DIG").one()
        assert product.name_ar == "ترمومتر ديجيتال"
        assert product.category.slug == "medical-devices"

    response = client.post(f"/admin/products/{product.id}/delete", follow_redirects=True)
    assert response.status_code == 200
    with app.app_context():
        assert db.session.get(Product, product.id) is None


def test_order_status_and_customer_history_views(client, app, pharmacy_data):
    order_id = pharmacy_data["order_id"]
    customer_id = pharmacy_data["customer_id"]

    response = client.get(f"/admin/orders/{order_id}")
    assert response.status_code == 200
    assert b"SHF-TEST-001" in response.data

    response = client.post(
        f"/admin/orders/{order_id}/status",
        data={"status": "out_for_delivery"},
        follow_redirects=True,
    )
    assert response.status_code == 200
    assert b"Order status updated." in response.data

    with app.app_context():
        assert db.session.get(Order, order_id).status == "out_for_delivery"

    response = client.get(f"/admin/customers/{customer_id}")
    assert response.status_code == 200
    assert b"Order history" in response.data
    assert b"SHF-TEST-001" in response.data
