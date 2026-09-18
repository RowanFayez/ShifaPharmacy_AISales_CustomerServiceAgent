"""Live catalogue reads used by the agent's constrained tools."""
from __future__ import annotations
from decimal import Decimal
from sqlalchemy import or_, select
from app.extensions import db
from app.models import Category, Product

def product_data(product: Product) -> dict:
    return {"id": product.id, "sku": product.sku, "name": product.name, "name_ar": product.name_ar,
            "price": str(product.price), "stock_quantity": product.stock_quantity,
            "requires_prescription": product.requires_prescription, "category": product.category.name}

def search_products(query: str, *, category: str | None = None, max_price: Decimal | None = None,
                    otc_only: bool = False, lang: str = "en") -> list[dict]:
    pattern = f"%{query.strip()}%"
    stmt = select(Product).join(Category).where(Product.active.is_(True), Category.active.is_(True))
    if query.strip():
        stmt = stmt.where(or_(Product.name.ilike(pattern), Product.name_ar.ilike(pattern), Product.generic_name.ilike(pattern), Product.aliases.ilike(pattern), Product.sku.ilike(pattern)))
    if category:
        stmt = stmt.where(or_(Category.slug == category, Category.name.ilike(f"%{category}%")))
    if max_price is not None: stmt = stmt.where(Product.price <= max_price)
    if otc_only: stmt = stmt.where(Product.requires_prescription.is_(False))
    return [product_data(product) for product in db.session.scalars(stmt.order_by(Product.name).limit(12)).all()]

def check_availability(sku_or_name: str) -> dict | None:
    product = db.session.scalar(select(Product).join(Category).where(Product.active.is_(True), or_(Product.sku == sku_or_name.upper(), Product.name.ilike(f"%{sku_or_name}%"), Product.name_ar.ilike(f"%{sku_or_name}%"))))
    return product_data(product) if product else None
