"""Live catalogue reads used by the agent's constrained tools."""
from __future__ import annotations
from decimal import Decimal
from difflib import SequenceMatcher
import re
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
    "skin care": "personal-care", "skincare": "personal-care", "skin": "personal-care", "cream": "personal-care",
    "بشرة": "personal-care", "بشره": "personal-care", "جلد": "personal-care", "كريم": "personal-care", "كريم للبشرة": "personal-care",
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


def _rank_products(products: list[Product], query: str) -> list[Product]:
    """Put products matching the customer's meaningful words first."""
    normalized = re.sub(r"[^\w\s-]", " ", normalize_for_retrieval(query), flags=re.UNICODE)
    terms = [term for term in normalized.split() if len(term) > 2 and term not in _SEARCH_STOP_WORDS]
    if not terms:
        return products
    ranked: list[tuple[int, Product]] = []
    for product in products:
        haystack = " ".join(_catalog_terms(product))
        score = sum(1 for term in terms if term in haystack)
        ranked.append((score, product))
    return [product for _, product in sorted(ranked, key=lambda item: (-item[0], item[1].name))]


def _fuzzy_products(products: list[Product], query: str, *, minimum_score: float = 0.75) -> list[Product]:
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
        if score >= minimum_score:
            ranked.append((score, product))
    return [product for _, product in sorted(ranked, key=lambda item: item[0], reverse=True)[:3]]


def suggest_products(query: str, *, category: str | None = None, otc_only: bool = False,
                     limit: int = 3) -> list[dict]:
    """Return safe alternatives without pretending they exactly match a query."""
    normalized_query = normalize_for_retrieval(query)
    inferred_category = next(
        (slug for phrase, slug in _CATEGORY_ALIASES.items() if normalize_for_retrieval(phrase) in normalized_query),
        None,
    )
    category_slug = category or inferred_category
    stmt = select(Product).join(Category).where(Product.active.is_(True), Category.active.is_(True))
    if category_slug:
        stmt = stmt.where(Category.slug == category_slug)
    if otc_only:
        stmt = stmt.where(Product.requires_prescription.is_(False))
    candidates = db.session.scalars(stmt.order_by(Product.name)).all()
    if category_slug:
        return [product_data(product) for product in candidates[:limit]]
    return [product_data(product) for product in _rank_products(_fuzzy_products(candidates, query, minimum_score=0.45), query)[:limit]]

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
    # This function intentionally returns exact SQL matches only. Fuzzy results
    # are produced by ``suggest_products`` and are labelled as alternatives by
    # the tool layer, so an approximate name can never be ordered silently.
    products = db.session.scalars(stmt.order_by(Product.name).limit(12)).all()
    if not products and query.strip() and not inferred_category:
        # Customer messages often include storefront wording and punctuation
        # around the product name (for example "هل يوجد بانادول؟"). Retry
        # meaningful tokens as exact SQL terms before falling back to fuzzy
        # alternatives. This preserves exact-match ordering for known products.
        tokens = [
            token for token in re.sub(r"[^\w\s-]", " ", normalized_query, flags=re.UNICODE).split()
            if len(token) > 2 and token not in _SEARCH_STOP_WORDS
        ]
        for token in tokens:
            token_stmt = select(Product).join(Category).where(
                Product.active.is_(True), Category.active.is_(True),
                or_(Product.name.ilike(f"%{token}%"), Product.name_ar.ilike(f"%{token}%"),
                    Product.generic_name.ilike(f"%{token}%"), Product.aliases.ilike(f"%{token}%"),
                    Product.sku.ilike(f"%{token}%")),
            )
            if category:
                token_stmt = token_stmt.where(or_(Category.slug == category, Category.name.ilike(f"%{category}%")))
            if max_price is not None:
                token_stmt = token_stmt.where(Product.price <= max_price)
            if otc_only:
                token_stmt = token_stmt.where(Product.requires_prescription.is_(False))
            products = db.session.scalars(token_stmt.order_by(Product.name).limit(12)).all()
            if products:
                break
    return [product_data(product) for product in _rank_products(products, query)]

def check_availability(sku_or_name: str) -> dict | None:
    product = db.session.scalar(select(Product).join(Category).where(Product.active.is_(True), or_(Product.sku == sku_or_name.upper(), Product.name.ilike(f"%{sku_or_name}%"), Product.name_ar.ilike(f"%{sku_or_name}%"))))
    return product_data(product) if product else None
