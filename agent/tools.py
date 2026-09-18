"""The agent's complete constrained tool surface."""
from __future__ import annotations
from decimal import Decimal
from pydantic import ValidationError
from app.services import catalog_service, order_service
from agent.schemas import AvailabilityInput, CreateOrderInput, EscalationInput, OrderStatusInput, PrescriptionInput, SearchProductsInput
def envelope(call, schema, payload):
    try: return {"ok": True, "data": call(schema.model_validate(payload)), "error_code": None, "message": "ok"}
    except ValidationError as exc: return {"ok": False, "data": None, "error_code": "INVALID_ARGUMENTS", "message": str(exc)}
    except order_service.ServiceError as exc: return {"ok": False, "data": None, "error_code": exc.code, "message": exc.message}
def search_products(payload): return envelope(lambda x: catalog_service.search_products(x.query, category=x.category, max_price=Decimal(str(x.max_price)) if x.max_price is not None else None, otc_only=x.otc_only, lang=x.lang), SearchProductsInput, payload)
def check_availability(payload): return envelope(lambda x: catalog_service.check_availability(x.sku_or_name), AvailabilityInput, payload)
def create_order(payload): return envelope(lambda x: order_service.create_order(x.customer_ref, [item.model_dump() for item in x.items], x.address), CreateOrderInput, payload)
def get_order_status(payload): return envelope(lambda x: order_service.order_status(x.order_number, x.phone), OrderStatusInput, payload)
def request_prescription_upload(payload): return envelope(lambda x: order_service.request_prescription(x.customer_ref, x.product_id, x.note), PrescriptionInput, payload)
def escalate_to_pharmacist(payload): return envelope(lambda x: order_service.escalate(x.conversation_id, x.question), EscalationInput, payload)
TOOL_REGISTRY = {"search_products": search_products, "check_availability": check_availability, "create_order": create_order, "get_order_status": get_order_status, "request_prescription_upload": request_prescription_upload, "escalate_to_pharmacist": escalate_to_pharmacist}
