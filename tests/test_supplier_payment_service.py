from datetime import date
from decimal import Decimal

import pytest

from app.models.purchase import Purchase
from app.models.supplier import Supplier
from app.services.supplier_payment_service import (
    get_purchase_outstanding_amount,
    get_purchase_paid_amount,
    record_supplier_payment,
)


def create_supplier(session):
    supplier = Supplier(
        name="Test Supplier",
        phone="0712345678",
    )

    session.add(supplier)
    session.commit()
    session.refresh(supplier)

    return supplier


def create_completed_purchase(
    session,
    supplier_id,
    total_amount=Decimal("50000.00"),
):
    purchase = Purchase(
        supplier_id=supplier_id,
        purchase_date=date(2026, 10, 2),
        subtotal=total_amount,
        tax_amount=Decimal("0.00"),
        total_amount=total_amount,
        payment_status="unpaid",
        status="completed",
    )

    session.add(purchase)
    session.commit()
    session.refresh(purchase)

    return purchase


def test_new_purchase_has_full_outstanding_balance(session):
    supplier = create_supplier(session)

    purchase = create_completed_purchase(
        session,
        supplier.id,
    )

    assert get_purchase_paid_amount(
        session,
        purchase.id,
    ) == Decimal("0.00")

    assert get_purchase_outstanding_amount(
        session,
        purchase.id,
    ) == Decimal("50000.00")


def test_full_supplier_payment_marks_purchase_paid(session):
    supplier = create_supplier(session)

    purchase = create_completed_purchase(
        session,
        supplier.id,
    )

    payment = record_supplier_payment(
        session=session,
        purchase_id=purchase.id,
        amount=Decimal("50000.00"),
        payment_method="cash",
    )

    assert payment.purchase_id == purchase.id
    assert payment.supplier_id == supplier.id
    assert payment.amount == Decimal("50000.00")

    session.refresh(purchase)

    assert purchase.payment_status == "paid"

    assert get_purchase_paid_amount(
        session,
        purchase.id,
    ) == Decimal("50000.00")

    assert get_purchase_outstanding_amount(
        session,
        purchase.id,
    ) == Decimal("0.00")


def test_partial_supplier_payment_marks_purchase_partial(session):
    supplier = create_supplier(session)

    purchase = create_completed_purchase(
        session,
        supplier.id,
    )

    record_supplier_payment(
        session=session,
        purchase_id=purchase.id,
        amount=Decimal("20000.00"),
        payment_method="mpesa",
        reference="MPESA123",
    )

    session.refresh(purchase)

    assert purchase.payment_status == "partial"

    assert get_purchase_paid_amount(
        session,
        purchase.id,
    ) == Decimal("20000.00")

    assert get_purchase_outstanding_amount(
        session,
        purchase.id,
    ) == Decimal("30000.00")


def test_multiple_supplier_payments_complete_purchase(session):
    supplier = create_supplier(session)

    purchase = create_completed_purchase(
        session,
        supplier.id,
    )

    record_supplier_payment(
        session=session,
        purchase_id=purchase.id,
        amount=Decimal("20000.00"),
        payment_method="cash",
    )

    record_supplier_payment(
        session=session,
        purchase_id=purchase.id,
        amount=Decimal("15000.00"),
        payment_method="mpesa",
    )

    record_supplier_payment(
        session=session,
        purchase_id=purchase.id,
        amount=Decimal("15000.00"),
        payment_method="bank",
    )

    session.refresh(purchase)

    assert purchase.payment_status == "paid"

    assert get_purchase_paid_amount(
        session,
        purchase.id,
    ) == Decimal("50000.00")

    assert get_purchase_outstanding_amount(
        session,
        purchase.id,
    ) == Decimal("0.00")


def test_supplier_payment_gets_supplier_id_from_purchase(session):
    supplier = create_supplier(session)

    purchase = create_completed_purchase(
        session,
        supplier.id,
    )

    payment = record_supplier_payment(
        session=session,
        purchase_id=purchase.id,
        amount=Decimal("10000.00"),
        payment_method="cash",
    )

    assert payment.supplier_id == supplier.id


def test_supplier_payment_rejects_zero_amount(session):
    supplier = create_supplier(session)

    purchase = create_completed_purchase(
        session,
        supplier.id,
    )

    with pytest.raises(
        ValueError,
        match="Payment amount must be greater than zero.",
    ):
        record_supplier_payment(
            session=session,
            purchase_id=purchase.id,
            amount=Decimal("0.00"),
            payment_method="cash",
        )


def test_supplier_payment_rejects_negative_amount(session):
    supplier = create_supplier(session)

    purchase = create_completed_purchase(
        session,
        supplier.id,
    )

    with pytest.raises(
        ValueError,
        match="Payment amount must be greater than zero.",
    ):
        record_supplier_payment(
            session=session,
            purchase_id=purchase.id,
            amount=Decimal("-100.00"),
            payment_method="cash",
        )


def test_supplier_payment_rejects_overpayment(session):
    supplier = create_supplier(session)

    purchase = create_completed_purchase(
        session,
        supplier.id,
    )

    with pytest.raises(
        ValueError,
        match="Payment exceeds the outstanding balance",
    ):
        record_supplier_payment(
            session=session,
            purchase_id=purchase.id,
            amount=Decimal("50001.00"),
            payment_method="cash",
        )


def test_supplier_payment_rejects_payment_after_full_payment(session):
    supplier = create_supplier(session)

    purchase = create_completed_purchase(
        session,
        supplier.id,
    )

    record_supplier_payment(
        session=session,
        purchase_id=purchase.id,
        amount=Decimal("50000.00"),
        payment_method="cash",
    )

    with pytest.raises(
        ValueError,
        match="Purchase has already been fully paid.",
    ):
        record_supplier_payment(
            session=session,
            purchase_id=purchase.id,
            amount=Decimal("100.00"),
            payment_method="cash",
        )


def test_supplier_payment_rejects_missing_payment_method(session):
    supplier = create_supplier(session)

    purchase = create_completed_purchase(
        session,
        supplier.id,
    )

    with pytest.raises(
        ValueError,
        match="Payment method is required.",
    ):
        record_supplier_payment(
            session=session,
            purchase_id=purchase.id,
            amount=Decimal("1000.00"),
            payment_method="   ",
        )


def test_supplier_payment_rejects_missing_purchase(session):
    with pytest.raises(
        ValueError,
        match="Purchase not found.",
    ):
        record_supplier_payment(
            session=session,
            purchase_id=9999,
            amount=Decimal("1000.00"),
            payment_method="cash",
        )


def test_supplier_payment_rejects_incomplete_purchase(session):
    supplier = create_supplier(session)

    purchase = Purchase(
        supplier_id=supplier.id,
        purchase_date=date(2026, 10, 2),
        subtotal=Decimal("50000.00"),
        tax_amount=Decimal("0.00"),
        total_amount=Decimal("50000.00"),
        payment_status="unpaid",
        status="draft",
    )

    session.add(purchase)
    session.commit()
    session.refresh(purchase)

    with pytest.raises(
        ValueError,
        match="Payment can only be recorded for a completed purchase.",
    ):
        record_supplier_payment(
            session=session,
            purchase_id=purchase.id,
            amount=Decimal("10000.00"),
            payment_method="cash",
        )
        