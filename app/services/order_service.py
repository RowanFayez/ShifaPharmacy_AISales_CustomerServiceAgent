"""Transactional pharmacy order and escalation writes."""
from __future__ import annotations
from datetime import datetime
from decimal import Decimal
from sqlalchemy import or_, select
from app.extensions import db
from app.models import Customer, Handoff, Lead, Order, OrderItem, Product

class ServiceError(Exception):
    def __init__(self, code: str, message: str): self.code, self.message = code, message; super().__init__(message)

def _customer(ref: str) -> Customer:
    clauses = [Customer.phone == str(ref), Customer.external_id == str(ref)]
    if str(ref).isdigit(): clauses.append(Customer.id == int(ref))
    customer = db.session.scalar(select(Customer).where(or_(*clauses)))
    if not customer: raise ServiceError("CUSTOMER_NOT_FOUND", "Customer reference was not found.")
    return customer

def create_order(customer_ref: str, items: list[dict], address: str) -> dict:
    if not items or not address.strip(): raise ServiceError("INVALID_ORDER", "Items and delivery address are required.")
    try:
        customer = _customer(customer_ref)
        requested: dict[int, int] = {}
        for item in items:
            product_id, quantity = int(item["product_id"]), int(item["quantity"])
            if quantity < 1: raise ServiceError("INVALID_QUANTITY", "Quantity must be at least one.")
            requested[product_id] = requested.get(product_id, 0) + quantity
        products = {p.id: p for p in db.session.scalars(select(Product).where(Product.id.in_(requested))).all()}
        if len(products) != len(requested): raise ServiceError("PRODUCT_NOT_FOUND", "One or more products were not found.")
        for product_id, quantity in requested.items():
            product = products[product_id]
            if not product.active: raise ServiceError("PRODUCT_INACTIVE", f"{product.name} is unavailable.")
            if product.requires_prescription: raise ServiceError("PRESCRIPTION_REQUIRED", f"{product.name} requires a prescription.")
            if product.stock_quantity < quantity: raise ServiceError("INSUFFICIENT_STOCK", f"{product.name} has insufficient stock.")
        subtotal = sum((products[i].price * q for i, q in requested.items()), Decimal("0.00"))
        delivery_fee = Decimal("0.00") if subtotal >= Decimal("500.00") else Decimal("35.00")
        order = Order(order_number=f"SHF-{datetime.utcnow():%Y%m%d%H%M%S%f}", customer=customer, delivery_address=address.strip(), subtotal=subtotal, delivery_fee=delivery_fee, total=subtotal + delivery_fee)
        db.session.add(order)
        for product_id, quantity in requested.items():
            product = products[product_id]; product.stock_quantity -= quantity
            order.items.append(OrderItem(product=product, quantity=quantity, unit_price=product.price))
        db.session.commit()
        return {"order_number": order.order_number, "total": str(order.total), "status": order.status}
    except ServiceError:
        db.session.rollback(); raise
    except Exception:
        db.session.rollback(); raise ServiceError("ORDER_FAILED", "The order could not be created.")

def order_status(order_number: str, phone: str) -> dict | None:
    order = db.session.scalar(select(Order).join(Customer).where(Order.order_number == order_number, Customer.phone == phone))
    return {"order_number": order.order_number, "status": order.status, "total": str(order.total)} if order else None

def request_prescription(customer_ref: str, product_id: int, note: str) -> dict:
    customer = _customer(customer_ref); lead = Lead(customer=customer, lead_type="prescription_request", details=f"product_id={product_id}; {note.strip()}")
    db.session.add(lead); db.session.commit(); return {"lead_id": lead.id, "status": lead.status}

def escalate(conversation_id: int, question: str) -> dict:
    handoff = Handoff(conversation_id=conversation_id, question=question.strip())
    db.session.add(handoff); db.session.commit(); return {"handoff_id": handoff.id, "status": handoff.status}
