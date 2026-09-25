"""Seed the migrated database with realistic Shifa Pharmacy demo data.

Run after ``flask --app app:create_app db upgrade``:

    python scripts/seed_db.py
"""

from __future__ import annotations

import sys
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from sqlalchemy import select

from app import create_app
from app.extensions import db
from app.models import Category, Customer, KnowledgeDocument, Order, OrderItem, Product


CATEGORIES = (
    ("Pain Relief & Cold", "pain-relief-cold", "OTC pain relief and cold-and-flu essentials."),
    ("Vitamins & Supplements", "vitamins-supplements", "Daily wellness and nutritional support."),
    ("Baby Care", "baby-care", "Diapers, feeding, and gentle baby essentials."),
    ("Personal Care", "personal-care", "Daily hygiene and skin-care products."),
    ("Diabetes Care", "diabetes-care", "Monitoring devices and diabetic-care supplies."),
    ("Medical Devices", "medical-devices", "Home health and first-aid devices."),
)

# sku, category slug, name, Arabic name, generic, aliases, brand, price, stock, Rx, description
PRODUCTS = (
    ("OTC-PAN-500-24", "pain-relief-cold", "Panadol 500 mg Tablets 24", "بانادول 500 مجم 24 قرص", "paracetamol", "panadol, بانادول, بنادول, paracetamol", "Panadol", "58.00", 80, False, "Paracetamol tablets for everyday pain and fever relief."),
    ("OTC-PAN-X-24", "pain-relief-cold", "Panadol Extra Tablets 24", "بانادول إكسترا 24 قرص", "paracetamol caffeine", "panadol extra, بانادول اكسترا, بنادول اكسترا", "Panadol", "72.00", 60, False, "Paracetamol and caffeine tablets."),
    ("OTC-ADV-400-20", "pain-relief-cold", "Advil 400 mg Tablets 20", "أدفيل 400 مجم 20 قرص", "ibuprofen", "advil, أدفيل, ibuprofen", "Advil", "95.00", 45, False, "Ibuprofen tablets."),
    ("OTC-COF-SYR-100", "pain-relief-cold", "Toplexil Cough Syrup 100 ml", "توبلكسيل شراب 100 مل", "oxomemazine", "toplexil, توبلكسيل, cough syrup, شراب كحة", "Toplexil", "49.00", 35, False, "Cough syrup; follow package guidance."),
    ("OTC-ORA-NS-15", "pain-relief-cold", "Otrivin Saline Nasal Spray 15 ml", "أوتريفين محلول ملحي 15 مل", "saline", "otrivin, أوتريفين, saline nasal spray", "Otrivin", "62.00", 30, False, "Saline nasal spray."),
    ("OTC-STRE-24", "pain-relief-cold", "Strepsils Honey & Lemon 24 Lozenges", "ستربسلز عسل وليمون 24 قرص استحلاب", "amylmetacresol", "strepsils, ستربسلز, lozenges, أقراص استحلاب", "Strepsils", "88.00", 55, False, "Honey and lemon lozenges."),
    ("OTC-VOL-GEL-50", "pain-relief-cold", "Voltaren Emulgel 50 g", "فولتارين إيمولجيل 50 جم", "diclofenac topical", "voltaren, فولتارين, emulgel", "Voltaren", "125.00", 25, False, "Topical anti-inflammatory gel."),
    ("RX-AUG-1G-14", "pain-relief-cold", "Augmentin 1 g Tablets 14", "أوجمنتين 1 جم 14 قرص", "amoxicillin clavulanate", "augmentin, أوجمنتين, amoxicillin", "Augmentin", "260.00", 18, True, "Prescription antibiotic."),
    ("RX-ZITH-500-3", "pain-relief-cold", "Zithromax 500 mg Tablets 3", "زيثرومكس 500 مجم 3 أقراص", "azithromycin", "zithromax, زيثرومكس, azithromycin", "Zithromax", "185.00", 16, True, "Prescription antibiotic."),
    ("OTC-BRUF-400-20", "pain-relief-cold", "Brufen 400 mg Tablets 20", "بروفين 400 مجم 20 قرص", "ibuprofen", "brufen, بروفين, ibuprofen", "Brufen", "65.00", 20, False, "Ibuprofen tablets."),
    ("VIT-C-1000-20", "vitamins-supplements", "Vitamin C 1000 mg Effervescent 20", "فيتامين سي 1000 مجم فوار 20 قرص", "ascorbic acid", "vitamin c, فيتامين سي, c 1000", "C-Retard", "110.00", 70, False, "Vitamin C effervescent tablets."),
    ("VIT-D3-5000-30", "vitamins-supplements", "Vitamin D3 5000 IU Capsules 30", "فيتامين د3 5000 وحدة 30 كبسولة", "cholecalciferol", "vitamin d, فيتامين د, d3", "Now Foods", "210.00", 42, False, "Vitamin D3 capsules."),
    ("VIT-MAG-30", "vitamins-supplements", "Magnesium Citrate 30 Tablets", "ماغنسيوم سيترات 30 قرص", "magnesium citrate", "magnesium, ماغنسيوم, magnesium citrate", "21st Century", "165.00", 40, False, "Magnesium citrate tablets."),
    ("VIT-OMEGA-30", "vitamins-supplements", "Omega-3 Fish Oil 30 Capsules", "أوميجا 3 زيت السمك 30 كبسولة", "omega 3", "omega 3, أوميجا 3, fish oil", "Seven Seas", "195.00", 38, False, "Fish oil capsules."),
    ("VIT-MULTI-30", "vitamins-supplements", "Centrum Adults 30 Tablets", "سنتروم للبالغين 30 قرص", "multivitamin", "centrum, سنتروم, multivitamin", "Centrum", "240.00", 28, False, "Adult multivitamin tablets."),
    ("RX-MET-500-30", "diabetes-care", "Metformin 500 mg Tablets 30", "ميتفورمين 500 مجم 30 قرص", "metformin", "metformin, ميتفورمين, glucophage", "Generic", "48.00", 30, True, "Prescription diabetes medicine."),
    ("BABY-PAMP-4-58", "baby-care", "Pampers Baby-Dry Size 4 58 Diapers", "بامبرز بيبي دراي مقاس 4 عدد 58", "diapers", "pampers, بامبرز, حفاضات, diapers", "Pampers", "390.00", 35, False, "Size 4 disposable diapers."),
    ("BABY-WIPES-64", "baby-care", "Johnson's Baby Wipes 64", "مناديل جونسون للأطفال 64 منديل", "baby wipes", "johnsons, جونسون, مناديل اطفال, baby wipes", "Johnson's", "72.00", 80, False, "Gentle baby wipes."),
    ("BABY-SHAM-200", "baby-care", "Mustela Gentle Shampoo 200 ml", "موستيلا شامبو لطيف 200 مل", "baby shampoo", "mustela, موستيلا, baby shampoo", "Mustela", "285.00", 22, False, "Gentle baby shampoo."),
    ("BABY-BOTTLE-260", "baby-care", "Philips Avent Feeding Bottle 260 ml", "ببرونة فيليبس أفنت 260 مل", "feeding bottle", "avent, افنت, ببرونة, feeding bottle", "Philips Avent", "235.00", 19, False, "260 ml feeding bottle."),
    ("BABY-SUD-125", "baby-care", "Sudocrem Baby Care Cream 125 g", "سودوكريم للعناية بالأطفال 125 جم", "zinc oxide cream", "sudocrem, سودوكريم, diaper cream", "Sudocrem", "155.00", 27, False, "Barrier cream for baby care."),
    ("CARE-CET-236", "personal-care", "Cetaphil Gentle Skin Cleanser 236 ml", "سيتافيل غسول لطيف 236 مل", "skin cleanser", "cetaphil, سيتافيل, cleanser", "Cetaphil", "310.00", 24, False, "Gentle daily skin cleanser."),
    ("CARE-SENS-75", "personal-care", "Sensodyne Repair Toothpaste 75 ml", "سنسوداين ريبير معجون أسنان 75 مل", "toothpaste", "sensodyne, سنسوداين, toothpaste", "Sensodyne", "115.00", 45, False, "Sensitive-teeth toothpaste."),
    ("CARE-NIVEA-50", "personal-care", "Nivea Soft Cream 50 ml", "نيفيا سوفت كريم 50 مل", "moisturizer", "nivea, نيفيا, moisturizer", "Nivea", "65.00", 65, False, "Everyday moisturizing cream."),
    ("CARE-REX-50", "personal-care", "Rexona Invisible Deodorant 50 ml", "ريكسونا مزيل عرق إنفيزيبل 50 مل", "deodorant", "rexona, ريكسونا, deodorant", "Rexona", "78.00", 48, False, "Roll-on deodorant."),
    ("CARE-LIP-4", "personal-care", "Labello Classic Lip Balm 4.8 g", "لابيلو مرطب شفاه كلاسيك", "lip balm", "labello, لابيلو, lip balm", "Labello", "58.00", 50, False, "Classic lip balm."),
    ("DIA-ACCU-STR-50", "diabetes-care", "Accu-Chek Active Test Strips 50", "شرائط أكيو تشيك أكتيف 50 شريط", "glucose test strips", "accu chek, أكيو تشيك, شرائط سكر", "Accu-Chek", "430.00", 32, False, "Compatible glucose test strips."),
    ("DIA-ACCU-METER", "diabetes-care", "Accu-Chek Active Glucose Meter", "جهاز أكيو تشيك أكتيف لقياس السكر", "glucose meter", "accu chek, أكيو تشيك, جهاز قياس السكر", "Accu-Chek", "520.00", 15, False, "Blood glucose monitoring device."),
    ("DIA-LANCET-100", "diabetes-care", "Accu-Chek Softclix Lancets 100", "وخزات أكيو تشيك سوفت كليكس 100", "lancets", "accu chek, أكيو تشيك, lancets, وخزات", "Accu-Chek", "175.00", 40, False, "Compatible sterile lancets."),
    ("DIA-GLUCO-25", "diabetes-care", "Glucophage XR 500 mg Tablets 30", "جلوكوفاج إكس آر 500 مجم 30 قرص", "metformin", "glucophage, جلوكوفاج, metformin", "Glucophage", "62.00", 25, True, "Prescription extended-release metformin."),
    ("DIA-INSULIN-100", "diabetes-care", "Lantus SoloStar Insulin Pen", "لانتوس سولوستار قلم أنسولين", "insulin glargine", "lantus, لانتوس, insulin, انسولين", "Lantus", "610.00", 10, True, "Prescription cold-chain insulin pen."),
    ("DEV-OMRON-M2", "medical-devices", "Omron M2 Basic Blood Pressure Monitor", "جهاز أومرون إم 2 لقياس الضغط", "blood pressure monitor", "omron, أومرون, جهاز ضغط", "Omron", "1350.00", 12, False, "Automatic upper-arm monitor."),
    ("DEV-THERMO-DIG", "medical-devices", "Digital Thermometer", "ترمومتر ديجيتال", "digital thermometer", "thermometer, ترمومتر, digital thermometer", "Generic", "105.00", 55, False, "Digital temperature monitor."),
    ("DEV-NEB-C28", "medical-devices", "Omron CompAir Nebulizer C28", "جهاز نيبولايزر أومرون سي 28", "nebulizer", "omron, أومرون, nebulizer, جهاز بخار", "Omron", "1650.00", 8, False, "Compressor nebulizer."),
    ("DEV-MASK-50", "medical-devices", "Disposable Surgical Masks 50", "كمامات جراحية 50 كمامة", "surgical masks", "masks, كمامات, surgical masks", "Generic", "85.00", 100, False, "Disposable face masks."),
    ("RX-VENT-100", "pain-relief-cold", "Ventolin Inhaler 100 mcg", "فنتولين بخاخ 100 ميكروجرام", "salbutamol", "ventolin, فنتولين, inhaler", "Ventolin", "98.00", 17, True, "Prescription inhaler."),
    ("RX-CREST-10-28", "pain-relief-cold", "Crestor 10 mg Tablets 28", "كريستور 10 مجم 28 قرص", "rosuvastatin", "crestor, كريستور, rosuvastatin", "Crestor", "340.00", 14, True, "Prescription cholesterol medicine."),
    ("RX-CONCOR-5-30", "pain-relief-cold", "Concor 5 mg Tablets 30", "كونكور 5 مجم 30 قرص", "bisoprolol", "concor, كونكور, bisoprolol", "Concor", "120.00", 22, True, "Prescription cardiovascular medicine."),
    ("OTC-ORAL-10", "pain-relief-cold", "Oral Rehydration Salts 10 Sachets", "أملاح معالجة الجفاف 10 أكياس", "oral rehydration salts", "ors, أملاح الجفاف, oral rehydration", "Rehydran", "46.00", 45, False, "Oral rehydration sachets."),
    ("OTC-BEP-30", "personal-care", "Bepanthen Moisturizing Cream 30 g", "بيبانثين كريم مرطب 30 جم", "dexpanthenol", "bepanthen, بيبانثين, dexpanthenol", "Bepanthen", "98.00", 38, False, "Moisturizing cream."),
)

CUSTOMERS = (
    ("Mariam Hassan", "01012345678", "mariam.hassan@example.test", "Cairo, Nasr City, Abbas El Akkad St."),
    ("Omar Adel", "01098765432", "omar.adel@example.test", "Giza, Dokki, Mohy El Din Abu El Ezz St."),
    ("Nour El Din", "01123456789", "nour.eldin@example.test", "Cairo, Maadi, Street 9."),
)

KNOWLEDGE_DOCUMENTS = (
    ("Delivery areas and fees", "delivery", "delivery_areas_fees.md"),
    ("Delivery times", "delivery", "delivery_times.md"),
    ("Payment methods", "payments", "payment_methods.md"),
    ("Returns and refunds", "policy", "returns_refunds.md"),
    ("Prescription policy", "prescription", "prescription_policy.md"),
    ("Cold-chain handling", "delivery", "cold_chain.md"),
    ("Loyalty and discounts", "policy", "loyalty_discounts.md"),
    ("Branches and hours", "support", "branches_hours.md"),
    ("How to order", "ordering", "how_to_order.md"),
    ("Privacy", "policy", "privacy.md"),
    ("Pain relief category", "category_explainer", "pain_relief.md"),
    ("Cold and flu category", "category_explainer", "cold_flu.md"),
    ("Baby care category", "category_explainer", "baby_care.md"),
    ("Diabetes care category", "category_explainer", "diabetes_care.md"),
    ("Vitamins category", "category_explainer", "vitamins.md"),
)


def scalar(model, field, value):
    return db.session.scalar(select(model).where(field == value))


def seed_categories() -> dict[str, Category]:
    categories: dict[str, Category] = {}
    for name, slug, description in CATEGORIES:
        category = scalar(Category, Category.slug, slug)
        if category is None:
            category = Category(name=name, slug=slug, description=description)
            db.session.add(category)
        categories[slug] = category
    db.session.flush()
    return categories


def seed_products(categories: dict[str, Category]) -> None:
    for sku, slug, name, name_ar, generic, aliases, brand, price, stock, is_rx, description in PRODUCTS:
        product = scalar(Product, Product.sku, sku)
        if product is None:
            db.session.add(
                Product(
                    sku=sku,
                    category=categories[slug],
                    name=name,
                    name_ar=name_ar,
                    generic_name=generic,
                    aliases=aliases,
                    brand=brand,
                    price=Decimal(price),
                    stock_quantity=stock,
                    requires_prescription=is_rx,
                    short_description=description,
                )
            )


def seed_customers() -> None:
    for full_name, phone, email, address in CUSTOMERS:
        if scalar(Customer, Customer.phone, phone) is None:
            db.session.add(Customer(full_name=full_name, phone=phone, email=email, default_address=address))


def seed_knowledge() -> None:
    knowledge_dir = ROOT / "data" / "knowledge"
    for title, category, filename in KNOWLEDGE_DOCUMENTS:
        if scalar(KnowledgeDocument, KnowledgeDocument.title, title) is None:
            db.session.add(
                KnowledgeDocument(
                    title=title,
                    category=category,
                    lang="bilingual",
                    content=(knowledge_dir / filename).read_text(encoding="utf-8"),
                )
            )


def seed_sample_orders() -> None:
    if scalar(Order, Order.order_number, "SHF-20260917-001") is not None:
        return
    mariam = scalar(Customer, Customer.phone, "01012345678")
    panadol = scalar(Product, Product.sku, "OTC-PAN-500-24")
    vitamin_c = scalar(Product, Product.sku, "VIT-C-1000-20")
    assert mariam and panadol and vitamin_c
    subtotal = panadol.price + vitamin_c.price
    order = Order(
        order_number="SHF-20260917-001",
        customer=mariam,
        status="confirmed",
        delivery_address=mariam.default_address,
        subtotal=subtotal,
        delivery_fee=Decimal("35.00"),
        total=subtotal + Decimal("35.00"),
    )
    order.items = [
        OrderItem(product=panadol, quantity=1, unit_price=panadol.price),
        OrderItem(product=vitamin_c, quantity=1, unit_price=vitamin_c.price),
    ]
    db.session.add(order)


def main() -> None:
    app = create_app()
    with app.app_context():
        categories = seed_categories()
        seed_products(categories)
        seed_customers()
        db.session.flush()
        seed_knowledge()
        seed_sample_orders()
        db.session.commit()
        print(
            "Seed complete: "
            f"{len(PRODUCTS)} products, "
            f"{len(CUSTOMERS)} customers, {len(KNOWLEDGE_DOCUMENTS)} knowledge documents."
        )


if __name__ == "__main__":
    main()
