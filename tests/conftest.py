from decimal import Decimal

import pytest

from app import create_app
from app.extensions import db
from app.models import Category, Customer, Order, OrderItem, Product


class TestConfig:
    TESTING = True
    SECRET_KEY = "test-secret"
    SQLALCHEMY_DATABASE_URI = "sqlite://"
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    WTF_CSRF_ENABLED = False


@pytest.fixture()
def app():
    application = create_app(TestConfig)
    with application.app_context():
        db.create_all()
        yield application
        db.session.remove()
        db.drop_all()


@pytest.fixture()
def client(app):
    return app.test_client()


@pytest.fixture()
def pharmacy_data(app):
    with app.app_context():
        category = Category(name="Pain Relief & Cold", slug="pain-relief-cold")
        product = Product(
            sku="OTC-PAN-500-24",
            name="Panadol 500 mg Tablets 24",
            name_ar="بانادول 500 مجم 24 قرص",
            generic_name="paracetamol",
            aliases="panadol, بانادول, بنادول",
            category=category,
            brand="Panadol",
            price=Decimal("58.00"),
            stock_quantity=10,
            short_description="Paracetamol tablets.",
        )
        customer = Customer(
            full_name="Mariam Hassan",
            phone="01012345678",
            email="mariam@example.test",
            default_address="Nasr City, Cairo",
        )
        order = Order(
            order_number="SHF-TEST-001",
            customer=customer,
            delivery_address="Nasr City, Cairo",
            subtotal=Decimal("58.00"),
            delivery_fee=Decimal("35.00"),
            total=Decimal("93.00"),
        )
        order.items = [OrderItem(product=product, quantity=1, unit_price=Decimal("58.00"))]
        db.session.add_all([category, product, customer, order])
        db.session.flush()
        ids = {"category_id": category.id, "product_id": product.id, "customer_id": customer.id, "order_id": order.id}
        db.session.commit()
        return ids
