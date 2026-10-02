from decimal import Decimal

import pytest

from app.models.category import Category
from app.models.payment import Payment
from app.models.product import Product
from app.models.sale import Sale
from app.services.payment_service import (
    get_sale_outstanding_amount,
    get_sale_paid_amount,
    record_sale_payment,
)


def create_test_sale(
    session,
    total_amount=Decimal("1000.00"),
    customer_id=None,
):
    category = Category(name="Test Category")
    session.add(category)
    session.flush()

    product = Product(
        name="Test Product",
        category_id=category.id,
        unit="piece",
        purchase_cost=Decimal("100.00"),
        selling_price=Decimal("1000.00"),
        stock_quantity=Decimal("10.000"),
        reorder_level=Decimal("2.000"),
        is_active=True,
    )

    session.add(product)
    session.flush()

    sale = Sale(
        sale_number="SALE-000001",
        user_id=1,
        customer_id=customer_id,
        subtotal=total_amount,
        tax_amount=Decimal("0.00"),
        discount_amount=Decimal("0.00"),
        total_amount=total_amount,
        payment_status="unpaid",
        status="completed",
    )

    session.add(sale)
    session.commit()
    session.refresh(sale)

    return sale


def test_new_sale_has_full_outstanding_balance(session):
    sale = create_test_sale(
        session,
        total_amount=Decimal("1000.00"),
    )

    assert get_sale_paid_amount(
        session,
        sale.id,
    ) == Decimal("0.00")

    assert get_sale_outstanding_amount(
        session,
        sale.id,
    ) == Decimal("1000.00")


def test_full_payment_marks_sale_as_paid(session):
    sale = create_test_sale(
        session,
        total_amount=Decimal("1000.00"),
    )

    payment = record_sale_payment(
        session=session,
        sale_id=sale.id,
        amount=Decimal("1000.00"),
        payment_method="cash",
    )

    assert payment.id is not None
    assert payment.sale_id == sale.id
    assert payment.amount == Decimal("1000.00")
    assert payment.payment_method == "cash"

    session.refresh(sale)

    assert sale.payment_status == "paid"

    assert get_sale_paid_amount(
        session,
        sale.id,
    ) == Decimal("1000.00")

    assert get_sale_outstanding_amount(
        session,
        sale.id,
    ) == Decimal("0.00")


def test_partial_payment_marks_sale_as_partial(session):
    sale = create_test_sale(
        session,
        total_amount=Decimal("1000.00"),
    )

    record_sale_payment(
        session=session,
        sale_id=sale.id,
        amount=Decimal("400.00"),
        payment_method="cash",
    )

    session.refresh(sale)

    assert sale.payment_status == "partial"

    assert get_sale_paid_amount(
        session,
        sale.id,
    ) == Decimal("400.00")

    assert get_sale_outstanding_amount(
        session,
        sale.id,
    ) == Decimal("600.00")


def test_multiple_payments_can_complete_sale(session):
    sale = create_test_sale(
        session,
        total_amount=Decimal("1000.00"),
    )

    first_payment = record_sale_payment(
        session=session,
        sale_id=sale.id,
        amount=Decimal("300.00"),
        payment_method="cash",
    )

    second_payment = record_sale_payment(
        session=session,
        sale_id=sale.id,
        amount=Decimal("500.00"),
        payment_method="mpesa",
        reference="MPESA123456",
    )

    third_payment = record_sale_payment(
        session=session,
        sale_id=sale.id,
        amount=Decimal("200.00"),
        payment_method="cash",
    )

    assert first_payment.amount == Decimal("300.00")
    assert second_payment.amount == Decimal("500.00")
    assert third_payment.amount == Decimal("200.00")

    session.refresh(sale)

    assert sale.payment_status == "paid"

    assert get_sale_paid_amount(
        session,
        sale.id,
    ) == Decimal("1000.00")

    assert get_sale_outstanding_amount(
        session,
        sale.id,
    ) == Decimal("0.00")

    payments = (
        session.query(Payment)
        .filter(Payment.sale_id == sale.id)
        .all()
    )

    assert len(payments) == 3


def test_payment_records_customer_id_from_sale(session):
    sale = create_test_sale(
        session,
        total_amount=Decimal("1000.00"),
        customer_id=25,
    )

    payment = record_sale_payment(
        session=session,
        sale_id=sale.id,
        amount=Decimal("250.00"),
        payment_method="mpesa",
        reference="MPESA987654",
    )

    assert payment.customer_id == 25


def test_payment_rejects_zero_amount(session):
    sale = create_test_sale(session)

    with pytest.raises(
        ValueError,
        match="greater than zero",
    ):
        record_sale_payment(
            session=session,
            sale_id=sale.id,
            amount=Decimal("0.00"),
            payment_method="cash",
        )


def test_payment_rejects_negative_amount(session):
    sale = create_test_sale(session)

    with pytest.raises(
        ValueError,
        match="greater than zero",
    ):
        record_sale_payment(
            session=session,
            sale_id=sale.id,
            amount=Decimal("-50.00"),
            payment_method="cash",
        )


def test_payment_rejects_overpayment(session):
    sale = create_test_sale(
        session,
        total_amount=Decimal("1000.00"),
    )

    with pytest.raises(
        ValueError,
        match="exceeds the outstanding balance",
    ):
        record_sale_payment(
            session=session,
            sale_id=sale.id,
            amount=Decimal("1000.01"),
            payment_method="cash",
        )


def test_payment_rejects_payment_after_sale_is_fully_paid(session):
    sale = create_test_sale(
        session,
        total_amount=Decimal("1000.00"),
    )

    record_sale_payment(
        session=session,
        sale_id=sale.id,
        amount=Decimal("1000.00"),
        payment_method="cash",
    )

    with pytest.raises(
        ValueError,
        match="already been fully paid",
    ):
        record_sale_payment(
            session=session,
            sale_id=sale.id,
            amount=Decimal("100.00"),
            payment_method="cash",
        )


def test_payment_rejects_missing_payment_method(session):
    sale = create_test_sale(session)

    with pytest.raises(
        ValueError,
        match="Payment method is required",
    ):
        record_sale_payment(
            session=session,
            sale_id=sale.id,
            amount=Decimal("100.00"),
            payment_method="   ",
        )


def test_payment_rejects_missing_sale(session):
    with pytest.raises(
        ValueError,
        match="Sale not found",
    ):
        record_sale_payment(
            session=session,
            sale_id=999,
            amount=Decimal("100.00"),
            payment_method="cash",
        )