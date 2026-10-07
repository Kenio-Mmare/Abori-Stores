from decimal import Decimal

import pytest

from app.models.customer import Customer
from app.models.product import Product
from app.models.user import User
from app.services.checkout_service import checkout_sale


def create_user(session):
    user = User(
        username="cashier",
        password_hash="test-hash",
        full_name="Test Cashier",
        role="cashier",
    )

    session.add(user)
    session.commit()
    session.refresh(user)

    return user


def create_customer(session):
    customer = Customer(
        name="Test Customer",
        phone="0712345678",
    )

    session.add(customer)
    session.commit()
    session.refresh(customer)

    return customer


def create_product(session):
    product = Product(
        name="Test Product",
        category_id=1,
        unit="piece",
        purchase_cost=Decimal("500.00"),
        selling_price=Decimal("1000.00"),
        stock_quantity=Decimal("100"),
        reorder_level=Decimal("10"),
        is_active=True,
    )

    session.add(product)
    session.commit()
    session.refresh(product)

    return product


def create_sale_items(product):
    return [
        {
            "product_id": product.id,
            "quantity": Decimal("1"),
            "unit_price": Decimal("1000.00"),
        }
    ]


def test_fully_paid_cash_sale_does_not_require_customer(session):
    user = create_user(session)
    product = create_product(session)

    sale = checkout_sale(
        session=session,
        user_id=user.id,
        items=create_sale_items(product),
        payments=[
            {
                "amount": Decimal("1000.00"),
                "payment_method": "cash",
            }
        ],
    )

    assert sale.total_amount == Decimal("1000.00")
    assert sale.payment_status == "paid"
    assert sale.customer_id is None


def test_multiple_payments_can_fully_pay_sale(session):
    user = create_user(session)
    product = create_product(session)

    sale = checkout_sale(
        session=session,
        user_id=user.id,
        items=create_sale_items(product),
        payments=[
            {
                "amount": Decimal("300.00"),
                "payment_method": "cash",
            },
            {
                "amount": Decimal("700.00"),
                "payment_method": "mpesa",
                "reference": "MPESA123",
            },
        ],
    )

    assert sale.total_amount == Decimal("1000.00")
    assert sale.payment_status == "paid"

    assert product.stock_quantity == Decimal("99.000")


def test_partial_payment_requires_customer(session):
    user = create_user(session)
    product = create_product(session)

    with pytest.raises(
        ValueError,
        match="A customer is required when the sale has an outstanding balance.",
    ):
        checkout_sale(
            session=session,
            user_id=user.id,
            items=create_sale_items(product),
            payments=[
                {
                    "amount": Decimal("700.00"),
                    "payment_method": "cash",
                }
            ],
        )


def test_partial_payment_with_customer_is_allowed(session):
    user = create_user(session)
    customer = create_customer(session)
    product = create_product(session)

    sale = checkout_sale(
        session=session,
        user_id=user.id,
        customer_id=customer.id,
        items=create_sale_items(product),
        payments=[
            {
                "amount": Decimal("700.00"),
                "payment_method": "cash",
            }
        ],
    )

    assert sale.total_amount == Decimal("1000.00")
    assert sale.payment_status == "partial"
    assert sale.customer_id == customer.id


def test_multiple_payments_can_leave_customer_credit(session):
    user = create_user(session)
    customer = create_customer(session)
    product = create_product(session)

    sale = checkout_sale(
        session=session,
        user_id=user.id,
        customer_id=customer.id,
        items=create_sale_items(product),
        payments=[
            {
                "amount": Decimal("200.00"),
                "payment_method": "cash",
            },
            {
                "amount": Decimal("500.00"),
                "payment_method": "mpesa",
                "reference": "MPESA456",
            },
        ],
    )

    assert sale.total_amount == Decimal("1000.00")
    assert sale.payment_status == "partial"
    assert sale.customer_id == customer.id


def test_overpayment_is_rejected(session):
    user = create_user(session)
    product = create_product(session)

    with pytest.raises(
        ValueError,
        match="Payment exceeds the sale total",
    ):
        checkout_sale(
            session=session,
            user_id=user.id,
            items=create_sale_items(product),
            payments=[
                {
                    "amount": Decimal("1001.00"),
                    "payment_method": "cash",
                }
            ],
        )


def test_zero_payment_is_rejected(session):
    user = create_user(session)
    product = create_product(session)

    with pytest.raises(
        ValueError,
        match="Payment amount must be greater than zero.",
    ):
        checkout_sale(
            session=session,
            user_id=user.id,
            items=create_sale_items(product),
            payments=[
                {
                    "amount": Decimal("0.00"),
                    "payment_method": "cash",
                }
            ],
        )


def test_negative_payment_is_rejected(session):
    user = create_user(session)
    product = create_product(session)

    with pytest.raises(
        ValueError,
        match="Payment amount must be greater than zero.",
    ):
        checkout_sale(
            session=session,
            user_id=user.id,
            items=create_sale_items(product),
            payments=[
                {
                    "amount": Decimal("-100.00"),
                    "payment_method": "cash",
                }
            ],
        )


def test_missing_payment_method_is_rejected(session):
    user = create_user(session)
    product = create_product(session)

    with pytest.raises(
        ValueError,
        match="Payment method is required.",
    ):
        checkout_sale(
            session=session,
            user_id=user.id,
            items=create_sale_items(product),
            payments=[
                {
                    "amount": Decimal("1000.00"),
                    "payment_method": "   ",
                }
            ],
        )


def test_empty_payment_list_is_rejected(session):
    user = create_user(session)
    product = create_product(session)

    with pytest.raises(
        ValueError,
        match="At least one payment is required.",
    ):
        checkout_sale(
            session=session,
            user_id=user.id,
            items=create_sale_items(product),
            payments=[],
        )


def test_failed_credit_checkout_rolls_back_sale(session):
    user = create_user(session)
    product = create_product(session)

    original_stock = product.stock_quantity

    with pytest.raises(
        ValueError,
        match="A customer is required when the sale has an outstanding balance.",
    ):
        checkout_sale(
            session=session,
            user_id=user.id,
            items=create_sale_items(product),
            payments=[
                {
                    "amount": Decimal("500.00"),
                    "payment_method": "cash",
                }
            ],
        )

    session.expire_all()

    assert session.query(Product).count() == 1

    refreshed_product = session.get(Product, product.id)

    assert refreshed_product.stock_quantity == original_stock

    from app.models.sale import Sale

    assert session.query(Sale).count() == 0
    