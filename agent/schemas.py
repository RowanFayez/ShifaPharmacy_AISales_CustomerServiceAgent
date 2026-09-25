"""Validated plans and tool arguments; LLM arguments are never trusted."""
from typing import Literal
from pydantic import BaseModel, Field
class Plan(BaseModel):
    intent: Literal["chitchat", "customer_service", "sales", "order_action", "order_status", "safety", "escalation"]
    language: Literal["en", "ar", "masri"] = "en"; needs_rag: bool = False; needs_catalog_lookup: bool = False
    product_mentions: list[str] = Field(default_factory=list); quantities: dict[str, int] = Field(default_factory=dict)
    is_medical_question: bool = False; wants_to_order: bool = False; confirming_previous_action: bool = False; rationale: str = ""
class SearchProductsInput(BaseModel): query: str; category: str | None = None; max_price: float | None = Field(default=None, ge=0); otc_only: bool = False; lang: str = "en"
class ListCategoriesInput(BaseModel): pass
class AvailabilityInput(BaseModel): sku_or_name: str
class OrderItemInput(BaseModel): product_id: int; quantity: int = Field(ge=1)
class CreateOrderInput(BaseModel): customer_ref: str; items: list[OrderItemInput] = Field(min_length=1); address: str
class OrderStatusInput(BaseModel): order_number: str; phone: str
class PrescriptionInput(BaseModel): customer_ref: str; product_id: int; note: str = ""
class EscalationInput(BaseModel): conversation_id: int; question: str
