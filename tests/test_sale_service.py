from decimal import Decimal

import pytest

from app.models.category import Category
from app.models.product import Product
from app.models.sale_item import SaleItem
from app.models.stock_movement import StockMovement
from app.models.supplier import Supplier
from app.services.sale_service import create_sale


def create_test_product(session, stock_quantity=10):
    category = Category(name="Test Category")
    session.add(category)
    session.flush()

    product = Product(
        name="Test Product",
        category_id=category.id,
        unit="piece",
        purchase_cost=Decimal("100.00"),
        selling_price=Decimal("150.00"),
        stock_quantity=Decimal(str(stock_quantity)),
        reorder_level=Decimal("2.000"),
        is_active=True,
    )

    session.add(product)
    session.commit()
    session.refresh(product)

    return product


def test_sale_rejects_empty_cart(session):
    with pytest.raises(ValueError, match="no items"):
        create_sale(
            session=session,
            user_id=1,
            items=[],
        )


def test_sale_rejects_missing_product(session):
    with pytest.raises(ValueError, match="not found"):
        create_sale(
            session=session,
            user_id=1,
            items=[
                {
                    "product_id": 999,
                    "quantity": 1,
                    "unit_price": Decimal("150.00"),
                }
            ],
        )


def test_sale_rejects_insufficient_stock(session):
    product = create_test_product(session, stock_quantity=5)

    with pytest.raises(ValueError, match="Insufficient stock"):
        create_sale(
            session=session,
            user_id=1,
            items=[
                {
                    "product_id": product.id,
                    "quantity": 10,
                    "unit_price": Decimal("150.00"),
                }
            ],
        )


def test_create_sale_creates_sale_and_reduces_stock(session):
    product = create_test_product(session, stock_quantity=10)

    sale = create_sale(
        session=session,
        user_id=1,
        items=[
            {
                "product_id": product.id,
                "quantity": 2,
                "unit_price": Decimal("150.00"),
            }
        ],
    )

    assert sale.id is not None
    assert sale.sale_number == "SALE-000001"
    assert sale.subtotal == Decimal("300.00")
    assert sale.total_amount == Decimal("300.00")
    assert sale.status == "completed"
    assert sale.payment_status == "unpaid"

    session.refresh(product)

    assert product.stock_quantity == Decimal("8.000")


def test_create_sale_with_multiple_products(session):
    product1 = create_test_product(session, stock_quantity=10)

    category = session.get(Category, product1.category_id)

    product2 = Product(
        name="Second Test Product",
        category_id=category.id,
        unit="piece",
        purchase_cost=Decimal("50.00"),
        selling_price=Decimal("80.00"),
        stock_quantity=Decimal("20.000"),
        reorder_level=Decimal("2.000"),
        is_active=True,
    )

    session.add(product2)
    session.commit()
    session.refresh(product2)

    sale = create_sale(
        session=session,
        user_id=1,
        items=[
            {
                "product_id": product1.id,
                "quantity": 2,
                "unit_price": Decimal("150.00"),
            },
            {
                "product_id": product2.id,
                "quantity": 3,
                "unit_price": Decimal("80.00"),
            },
        ],
    )

    assert sale.subtotal == Decimal("540.00")
    assert sale.total_amount == Decimal("540.00")

    session.refresh(product1)
    session.refresh(product2)

    assert product1.stock_quantity == Decimal("8.000")
    assert product2.stock_quantity == Decimal("17.000")


def test_create_sale_records_stock_movement(session):
    product = create_test_product(session, stock_quantity=10)

    sale = create_sale(
        session=session,
        user_id=1,
        items=[
            {
                "product_id": product.id,
                "quantity": 3,
                "unit_price": Decimal("150.00"),
            }
        ],
    )

    movement = (
        session.query(StockMovement)
        .filter(StockMovement.product_id == product.id)
        .one()
    )

    assert movement.movement_type == "sale"
    assert movement.quantity == Decimal("-3.000")
    assert movement.reference == f"Sale #{sale.id}"


def test_special_order_sale_does_not_reduce_stock(session):
    product = create_test_product(session, stock_quantity=0)

    supplier = Supplier(
        name="Source Hardware Shop",
        phone="0712345678",
    )

    session.add(supplier)
    session.commit()
    session.refresh(supplier)

    sale = create_sale(
        session=session,
        user_id=1,
        items=[
            {
                "product_id": product.id,
                "quantity": 2,
                "unit_price": Decimal("180.00"),
                "source_type": "special_order",
                "source_supplier_id": supplier.id,
                "source_unit_cost": Decimal("150.00"),
            }
        ],
    )

    assert sale.total_amount == Decimal("360.00")

    session.refresh(product)

    assert product.stock_quantity == Decimal("0.000")


def test_special_order_records_source_details(session):
    product = create_test_product(session, stock_quantity=0)

    supplier = Supplier(
        name="Source Hardware Shop",
    )

    session.add(supplier)
    session.commit()
    session.refresh(supplier)

    sale = create_sale(
        session=session,
        user_id=1,
        items=[
            {
                "product_id": product.id,
                "quantity": 2,
                "unit_price": Decimal("180.00"),
                "source_type": "special_order",
                "source_supplier_id": supplier.id,
                "source_unit_cost": Decimal("150.00"),
            }
        ],
    )

    sale_item = (
        session.query(SaleItem)
        .filter(SaleItem.sale_id == sale.id)
        .one()
    )

    assert sale_item.source_type == "special_order"
    assert sale_item.source_supplier_id == supplier.id
    assert sale_item.source_unit_cost == Decimal("150.00")


def test_special_order_rejects_missing_supplier(session):
    product = create_test_product(session, stock_quantity=0)

    with pytest.raises(
        ValueError,
        match="must have a source_supplier_id",
    ):
        create_sale(
            session=session,
            user_id=1,
            items=[
                {
                    "product_id": product.id,
                    "quantity": 1,
                    "unit_price": Decimal("180.00"),
                    "source_type": "special_order",
                    "source_unit_cost": Decimal("150.00"),
                }
            ],
        )


def test_special_order_rejects_missing_source_cost(session):
    product = create_test_product(session, stock_quantity=0)

    supplier = Supplier(
        name="Source Hardware Shop",
    )

    session.add(supplier)
    session.commit()
    session.refresh(supplier)

    with pytest.raises(
        ValueError,
        match="must have a source_unit_cost",
    ):
        create_sale(
            session=session,
            user_id=1,
            items=[
                {
                    "product_id": product.id,
                    "quantity": 1,
                    "unit_price": Decimal("180.00"),
                    "source_type": "special_order",
                    "source_supplier_id": supplier.id,
                }
            ],
        )


def test_special_order_rejects_unknown_supplier(session):
    product = create_test_product(session, stock_quantity=0)

    with pytest.raises(
        ValueError,
        match="Source supplier with ID 999 was not found",
    ):
        create_sale(
            session=session,
            user_id=1,
            items=[
                {
                    "product_id": product.id,
                    "quantity": 1,
                    "unit_price": Decimal("180.00"),
                    "source_type": "special_order",
                    "source_supplier_id": 999,
                    "source_unit_cost": Decimal("150.00"),
                }
            ],
        )