from datetime import date
from decimal import Decimal

from app.models.category import Category
from app.models.product import Product
from app.models.purchase import Purchase
from app.models.purchase_item import PurchaseItem
from app.models.stock_movement import StockMovement
from app.models.supplier import Supplier
from app.services.purchase_service import receive_purchase


def test_receive_purchase(session):
    category = Category(
        name="Test Category",
        description="Temporary test category",
    )

    supplier = Supplier(
        name="Test Supplier",
    )

    session.add_all([category, supplier])
    session.commit()

    product = Product(
        name="Test Cement",
        category_id=category.id,
        unit="bag",
        purchase_cost=Decimal("600.00"),
        selling_price=Decimal("750.00"),
        stock_quantity=Decimal("0"),
        reorder_level=Decimal("5"),
    )

    session.add(product)
    session.commit()

    purchase = Purchase(
        supplier_id=supplier.id,
        purchase_date=date(2026, 9, 28),
        status="draft",
    )

    session.add(purchase)
    session.commit()

    item = PurchaseItem(
        purchase_id=purchase.id,
        product_id=product.id,
        quantity=Decimal("20"),
        unit_cost=Decimal("700.00"),
        line_total=Decimal("14000.00"),
    )

    session.add(item)
    session.commit()

    receive_purchase(session, purchase.id)

    session.refresh(product)
    session.refresh(purchase)

    movement = (
        session.query(StockMovement)
        .filter(
            StockMovement.product_id == product.id,
            StockMovement.reference == f"Purchase #{purchase.id}",
        )
        .first()
    )

    assert purchase.status == "completed"
    assert product.stock_quantity == Decimal("20.000")
    assert product.purchase_cost == Decimal("700.00")
    assert movement is not None
    assert movement.quantity == Decimal("20.000")


def test_cannot_receive_completed_purchase(session):
    category = Category(
        name="Test Category 2",
    )

    supplier = Supplier(
        name="Test Supplier 2",
    )

    session.add_all([category, supplier])
    session.commit()

    product = Product(
        name="Test Pipe",
        category_id=category.id,
        unit="piece",
        purchase_cost=Decimal("100.00"),
        selling_price=Decimal("150.00"),
        stock_quantity=Decimal("0"),
        reorder_level=Decimal("5"),
    )

    session.add(product)
    session.commit()

    purchase = Purchase(
        supplier_id=supplier.id,
        purchase_date=date(2026, 9, 28),
        status="draft",
    )

    session.add(purchase)
    session.commit()

    item = PurchaseItem(
        purchase_id=purchase.id,
        product_id=product.id,
        quantity=Decimal("10"),
        unit_cost=Decimal("100.00"),
         line_total=Decimal("1000.00"),
)
    

    session.add(item)
    session.commit()

    receive_purchase(session, purchase.id)

    try:
        receive_purchase(session, purchase.id)
        assert False, "Expected second receiving attempt to fail."
    except ValueError as error:
        assert "cannot be received" in str(error).lower()

    session.refresh(product)

    assert product.stock_quantity == Decimal("10.000")
    line_total=Decimal("14000.00"),
