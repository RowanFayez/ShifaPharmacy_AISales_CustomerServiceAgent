"""Core M2 administration routes; no agent or RAG behavior lives here."""

from __future__ import annotations

import re

from flask import abort, flash, redirect, render_template, request, url_for
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import selectinload

from app.blueprints.admin import admin_bp
from app.blueprints.admin.forms import CategoryForm, OrderStatusForm, ProductForm
from app.extensions import db
from app.models import Category, Customer, Order, OrderItem, Product


def slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return slug


def save_or_flash(message: str, redirect_endpoint: str, **values):
    try:
        db.session.commit()
        flash(message, "success")
    except IntegrityError:
        db.session.rollback()
        flash("The record could not be saved because a unique value already exists.", "danger")
    return redirect(url_for(redirect_endpoint, **values))


@admin_bp.get("/")
def dashboard():
    return render_template(
        "admin/dashboard.html",
        category_count=db.session.scalar(select(func.count()).select_from(Category)),
        product_count=db.session.scalar(select(func.count()).select_from(Product)),
        order_count=db.session.scalar(select(func.count()).select_from(Order)),
        customer_count=db.session.scalar(select(func.count()).select_from(Customer)),
    )


@admin_bp.route("/categories/new", methods=["GET", "POST"])
def category_create():
    form = CategoryForm()
    if form.validate_on_submit():
        slug = form.slug.data or slugify(form.name.data)
        if not slug:
            form.slug.errors.append("Provide a name that can produce a slug.")
        elif db.session.scalar(select(Category).where(Category.slug == slug)):
            form.slug.errors.append("This slug is already in use.")
        else:
            db.session.add(
                Category(
                    name=form.name.data.strip(),
                    slug=slug,
                    description=form.description.data.strip() or None,
                    active=form.active.data,
                )
            )
            return save_or_flash("Category created.", "admin.category_list")
    return render_template("admin/category_form.html", form=form, category=None)


@admin_bp.get("/categories")
def category_list():
    categories = db.session.scalars(select(Category).order_by(Category.name)).all()
    return render_template("admin/categories.html", categories=categories)


@admin_bp.route("/categories/<int:category_id>/edit", methods=["GET", "POST"])
def category_edit(category_id: int):
    category = db.get_or_404(Category, category_id)
    form = CategoryForm(obj=category)
    if form.validate_on_submit():
        slug = form.slug.data or slugify(form.name.data)
        duplicate = db.session.scalar(
            select(Category).where(Category.slug == slug, Category.id != category.id)
        )
        if not slug:
            form.slug.errors.append("Provide a name that can produce a slug.")
        elif duplicate:
            form.slug.errors.append("This slug is already in use.")
        else:
            category.name = form.name.data.strip()
            category.slug = slug
            category.description = form.description.data.strip() or None
            category.active = form.active.data
            return save_or_flash("Category updated.", "admin.category_list")
    return render_template("admin/category_form.html", form=form, category=category)


@admin_bp.post("/categories/<int:category_id>/delete")
def category_delete(category_id: int):
    category = db.get_or_404(Category, category_id)
    if category.products:
        flash("A category with products cannot be deleted. Move or delete its products first.", "warning")
    else:
        db.session.delete(category)
        return save_or_flash("Category deleted.", "admin.category_list")
    return redirect(url_for("admin.category_list"))


@admin_bp.route("/products/new", methods=["GET", "POST"])
def product_create():
    form = ProductForm()
    if form.validate_on_submit():
        if db.session.scalar(select(Product).where(Product.sku == form.sku.data.strip().upper())):
            form.sku.errors.append("This SKU is already in use.")
        else:
            db.session.add(
                Product(
                    sku=form.sku.data.strip().upper(),
                    name=form.name.data.strip(),
                    name_ar=form.name_ar.data.strip() or None,
                    generic_name=form.generic_name.data.strip() or None,
                    aliases=form.aliases.data.strip() or None,
                    category_id=form.category_id.data,
                    brand=form.brand.data.strip() or None,
                    price=form.price.data,
                    stock_quantity=form.stock_quantity.data,
                    requires_prescription=form.requires_prescription.data,
                    short_description=form.short_description.data.strip() or None,
                    active=form.active.data,
                )
            )
            return save_or_flash("Product created.", "admin.product_list")
    return render_template("admin/product_form.html", form=form, product=None)


@admin_bp.get("/products")
def product_list():
    query = request.args.get("q", "").strip()
    stmt = select(Product).options(selectinload(Product.category)).order_by(Product.name)
    if query:
        pattern = f"%{query}%"
        stmt = stmt.where(
            Product.name.ilike(pattern)
            | Product.name_ar.ilike(pattern)
            | Product.sku.ilike(pattern)
            | Product.aliases.ilike(pattern)
        )
    return render_template("admin/products.html", products=db.session.scalars(stmt).all(), query=query)


@admin_bp.route("/products/<int:product_id>/edit", methods=["GET", "POST"])
def product_edit(product_id: int):
    product = db.get_or_404(Product, product_id)
    form = ProductForm(obj=product)
    if form.validate_on_submit():
        sku = form.sku.data.strip().upper()
        duplicate = db.session.scalar(select(Product).where(Product.sku == sku, Product.id != product.id))
        if duplicate:
            form.sku.errors.append("This SKU is already in use.")
        else:
            product.sku = sku
            product.name = form.name.data.strip()
            product.name_ar = form.name_ar.data.strip() or None
            product.generic_name = form.generic_name.data.strip() or None
            product.aliases = form.aliases.data.strip() or None
            product.category_id = form.category_id.data
            product.brand = form.brand.data.strip() or None
            product.price = form.price.data
            product.stock_quantity = form.stock_quantity.data
            product.requires_prescription = form.requires_prescription.data
            product.short_description = form.short_description.data.strip() or None
            product.active = form.active.data
            return save_or_flash("Product updated.", "admin.product_list")
    return render_template("admin/product_form.html", form=form, product=product)


@admin_bp.post("/products/<int:product_id>/delete")
def product_delete(product_id: int):
    product = db.get_or_404(Product, product_id)
    if product.order_items:
        flash("A product in an order cannot be deleted; deactivate it instead.", "warning")
    else:
        db.session.delete(product)
        return save_or_flash("Product deleted.", "admin.product_list")
    return redirect(url_for("admin.product_list"))


@admin_bp.get("/orders")
def order_list():
    status = request.args.get("status", "").strip()
    stmt = select(Order).options(selectinload(Order.customer)).order_by(Order.created_at.desc())
    if status:
        stmt = stmt.where(Order.status == status)
    return render_template("admin/orders.html", orders=db.session.scalars(stmt).all(), selected_status=status)


@admin_bp.get("/orders/<int:order_id>")
def order_detail(order_id: int):
    order = db.session.scalar(
        select(Order)
        .options(selectinload(Order.customer), selectinload(Order.items).selectinload(OrderItem.product))
        .where(Order.id == order_id)
    )
    if order is None:
        abort(404)
    form = OrderStatusForm(obj=order)
    return render_template("admin/order_detail.html", order=order, form=form)


@admin_bp.post("/orders/<int:order_id>/status")
def order_status_update(order_id: int):
    order = db.get_or_404(Order, order_id)
    form = OrderStatusForm()
    if form.validate_on_submit():
        order.status = form.status.data
        return save_or_flash("Order status updated.", "admin.order_detail", order_id=order.id)
    flash("Order status could not be updated.", "danger")
    return redirect(url_for("admin.order_detail", order_id=order.id))


@admin_bp.get("/customers")
def customer_list():
    customers = db.session.scalars(select(Customer).order_by(Customer.created_at.desc())).all()
    return render_template("admin/customers.html", customers=customers)


@admin_bp.get("/customers/<int:customer_id>")
def customer_detail(customer_id: int):
    customer = db.session.scalar(
        select(Customer).options(selectinload(Customer.orders)).where(Customer.id == customer_id)
    )
    if customer is None:
        abort(404)
    return render_template("admin/customer_detail.html", customer=customer)
