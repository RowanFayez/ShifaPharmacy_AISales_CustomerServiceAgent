"""Live catalogue reads used by the agent's constrained tools."""
from __future__ import annotations
from decimal import Decimal
from difflib import SequenceMatcher
from sqlalchemy import or_, select
from app.extensions import db
from app.models import Category, Product
from agent.lang import normalize_for_retrieval


_SEARCH_STOP_WORDS = {
    "do", "you", "have", "is", "are", "the", "a", "an", "price", "how", "much",
    "في", "عندكم", "عندكو", "ممكن", "عايز", "عايزه", "بكام", "سعر", "دوا", "دواء", "ادوية", "ادويه",
}
_CATEGORY_ALIASES = {
    "برد": "pain-relief-cold", "انفلونزا": "pain-relief-cold", "cold": "pain-relief-cold", "flu": "pain-relief-cold",
    "vitamin": "vitamins-supplements", "vitamins": "vitamins-supplements", "supplement": "vitamins-supplements",
    "supplements": "vitamins-supplements", "فيتامين": "vitamins-supplements", "فيتامينات": "vitamins-supplements", "مكمل": "vitamins-supplements", "مكملات": "vitamins-supplements",
    "baby": "baby-care", "طفل": "baby-care", "اطفال": "baby-care", "personal care": "personal-care", "عناية شخصية": "personal-care",
    "diabetes": "diabetes-care", "سكري": "diabetes-care", "device": "medical-devices", "اجهزة": "medical-devices",
}

def product_data(product: Product) -> dict:
    return {"id": product.id, "sku": product.sku, "name": product.name, "name_ar": product.name_ar,
            "price": str(product.price), "stock_quantity": product.stock_quantity,
            "requires_prescription": product.requires_prescription, "category": product.category.name,
            "generic_name": product.generic_name, "short_description": product.short_description}


def list_categories() -> list[dict]:
    """Return the active storefront categories from the live database."""
    categories = db.session.scalars(
        select(Category).where(Category.active.is_(True)).order_by(Category.name)
    ).all()
    return [{"name": category.name, "slug": category.slug, "description": category.description} for category in categories]


def _catalog_terms(product: Product) -> list[str]:
    values = [product.name, product.name_ar, product.generic_name, product.sku]
    values.extend((product.aliases or "").split(","))
    return [normalize_for_retrieval(value) for value in values if value]


def _fuzzy_products(products: list[Product], query: str) -> list[Product]:
    """Find close catalog names for transliteration and small spelling mistakes."""
    normalized = normalize_for_retrieval(query)
    terms = [term for term in normalized.split() if len(term) > 2 and term not in _SEARCH_STOP_WORDS]
    ranked: list[tuple[float, Product]] = []
    for product in products:
        candidates = _catalog_terms(product)
        score = max(
            (1.0 if term in candidate else SequenceMatcher(None, term, candidate).ratio()
             for term in terms for candidate in candidates),
            default=0.0,
        )
        # Do not turn a weakly similar name into a different medicine.  This
        # threshold still accepts common misspellings (for example بانادوال),
        # while a vague name such as ميرفين is reported as not found.
        if score >= 0.75:
            ranked.append((score, product))
    return [product for _, product in sorted(ranked, key=lambda item: item[0], reverse=True)[:3]]

def search_products(query: str, *, category: str | None = None, max_price: Decimal | None = None,
                    otc_only: bool = False, lang: str = "en") -> list[dict]:
    pattern = f"%{query.strip()}%"
    normalized_query = normalize_for_retrieval(query)
    inferred_category = next(
        (slug for phrase, slug in _CATEGORY_ALIASES.items() if normalize_for_retrieval(phrase) in normalized_query),
        None,
    )
    stmt = select(Product).join(Category).where(Product.active.is_(True), Category.active.is_(True))
    if query.strip() and not inferred_category:
        stmt = stmt.where(or_(Product.name.ilike(pattern), Product.name_ar.ilike(pattern), Product.generic_name.ilike(pattern), Product.aliases.ilike(pattern), Product.sku.ilike(pattern)))
    if category:
        stmt = stmt.where(or_(Category.slug == category, Category.name.ilike(f"%{category}%")))
    elif inferred_category:
        stmt = stmt.where(Category.slug == inferred_category)
    if max_price is not None: stmt = stmt.where(Product.price <= max_price)
    if otc_only: stmt = stmt.where(Product.requires_prescription.is_(False))
    products = db.session.scalars(stmt.order_by(Product.name).limit(12)).all()
    if not products and query.strip():
        fallback = select(Product).join(Category).where(Product.active.is_(True), Category.active.is_(True))
        if otc_only:
            fallback = fallback.where(Product.requires_prescription.is_(False))
        products = _fuzzy_products(db.session.scalars(fallback.order_by(Product.name)).all(), query)
    return [product_data(product) for product in products]

def check_availability(sku_or_name: str) -> dict | None:
    product = db.session.scalar(select(Product).join(Category).where(Product.active.is_(True), or_(Product.sku == sku_or_name.upper(), Product.name.ilike(f"%{sku_or_name}%"), Product.name_ar.ilike(f"%{sku_or_name}%"))))
    return product_data(product) if product else None
