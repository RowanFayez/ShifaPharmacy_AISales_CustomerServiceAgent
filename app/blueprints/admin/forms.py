"""Validated server-rendered forms for the core admin workflow."""

from __future__ import annotations

from flask_wtf import FlaskForm
from wtforms import BooleanField, DecimalField, IntegerField, SelectField, StringField, SubmitField, TextAreaField
from wtforms.validators import DataRequired, Length, NumberRange, Optional, Regexp

from app.models import Category


class CategoryForm(FlaskForm):
    name = StringField("Name", validators=[DataRequired(), Length(max=100)])
    slug = StringField(
        "Slug",
        validators=[Optional(), Length(max=100), Regexp(r"^[a-z0-9-]*$", message="Use lowercase letters, numbers, and hyphens.")],
    )
    description = TextAreaField("Description", validators=[Optional(), Length(max=1000)])
    active = BooleanField("Active", default=True)
    submit = SubmitField("Save category")


class ProductForm(FlaskForm):
    sku = StringField("SKU", validators=[DataRequired(), Length(max=64)])
    name = StringField("English name", validators=[DataRequired(), Length(max=180)])
    name_ar = StringField("Arabic name", validators=[Optional(), Length(max=180)])
    generic_name = StringField("Generic name", validators=[Optional(), Length(max=180)])
    aliases = TextAreaField("Aliases", validators=[Optional(), Length(max=2000)])
    category_id = SelectField("Category", coerce=int, validators=[DataRequired()])
    brand = StringField("Brand", validators=[Optional(), Length(max=120)])
    price = DecimalField("Price (EGP)", places=2, rounding=None, validators=[DataRequired(), NumberRange(min=0)])
    stock_quantity = IntegerField("Stock quantity", validators=[DataRequired(), NumberRange(min=0)])
    requires_prescription = BooleanField("Requires prescription")
    short_description = TextAreaField("Short description", validators=[Optional(), Length(max=2000)])
    active = BooleanField("Active", default=True)
    submit = SubmitField("Save product")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.category_id.choices = [
            (category.id, category.name)
            for category in Category.query.filter_by(active=True).order_by(Category.name).all()
        ]


class OrderStatusForm(FlaskForm):
    status = SelectField(
        "Status",
        choices=[
            ("pending", "Pending"),
            ("confirmed", "Confirmed"),
            ("preparing", "Preparing"),
            ("out_for_delivery", "Out for delivery"),
            ("delivered", "Delivered"),
            ("cancelled", "Cancelled"),
        ],
        validators=[DataRequired()],
    )
    submit = SubmitField("Update status")
