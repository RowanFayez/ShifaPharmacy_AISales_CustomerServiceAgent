"""The agent's complete constrained tool surface."""
from __future__ import annotations
from decimal import Decimal
from pydantic import ValidationError
import logging
from app.services import catalog_service, order_service
from agent.schemas import AvailabilityInput, CreateOrderInput, EscalationInput, ListCategoriesInput, OrderStatusInput, PrescriptionInput, SearchProductsInput
logger = logging.getLogger(__name__)
def envelope(call, schema, payload):
    try: return {"ok": True, "data": call(schema.model_validate(payload)), "error_code": None, "message": "ok"}
    except ValidationError as exc: return {"ok": False, "data": None, "error_code": "INVALID_ARGUMENTS", "message": str(exc)}
    except order_service.ServiceError as exc: return {"ok": False, "data": None, "error_code": exc.code, "message": exc.message}
    except Exception:
        logger.exception("Tool call failed")
        return {"ok": False, "data": None, "error_code": "BACKEND_FAILURE", "message": "The service is temporarily unavailable."}
def search_products(payload):
    result = envelope(lambda x: catalog_service.search_products(x.query, category=x.category, max_price=Decimal(str(x.max_price)) if x.max_price is not None else None, otc_only=x.otc_only, lang=x.lang), SearchProductsInput, payload)
    return {"ok": False, "data": [], "error_code": "NO_RESULTS", "message": "No matching products were found."} if result["ok"] and not result["data"] else result
def list_categories(payload=None): return envelope(lambda _: catalog_service.list_categories(), ListCategoriesInput, payload or {})
def check_availability(payload):
    result = envelope(lambda x: catalog_service.check_availability(x.sku_or_name), AvailabilityInput, payload)
    return {"ok": False, "data": None, "error_code": "NOT_FOUND", "message": "Product not found."} if result["ok"] and result["data"] is None else result
def create_order(payload): return envelope(lambda x: order_service.create_order(x.customer_ref, [item.model_dump() for item in x.items], x.address), CreateOrderInput, payload)
def get_order_status(payload): return envelope(lambda x: order_service.order_status(x.order_number, x.phone), OrderStatusInput, payload)
def request_prescription_upload(payload): return envelope(lambda x: order_service.request_prescription(x.customer_ref, x.product_id, x.note), PrescriptionInput, payload)
def escalate_to_pharmacist(payload): return envelope(lambda x: order_service.escalate(x.conversation_id, x.question), EscalationInput, payload)
TOOL_REGISTRY = {"search_products": search_products, "list_categories": list_categories, "check_availability": check_availability, "create_order": create_order, "get_order_status": get_order_status, "request_prescription_upload": request_prescription_upload, "escalate_to_pharmacist": escalate_to_pharmacist}
