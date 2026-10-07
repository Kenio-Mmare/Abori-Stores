from decimal import Decimal

from sqlalchemy.orm import Session

from app.models.payment import Payment
from app.models.purchase import Purchase


def get_purchase_paid_amount(
    session: Session,
    purchase_id: int,
) -> Decimal:
    """
    Return the total amount already paid toward a purchase.
    """

    purchase = session.get(Purchase, purchase_id)

    if purchase is None:
        raise ValueError("Purchase not found.")

    payments = (
        session.query(Payment)
        .filter(Payment.purchase_id == purchase_id)
        .all()
    )

    return sum(
        (payment.amount for payment in payments),
        Decimal("0.00"),
    )


def get_purchase_outstanding_amount(
    session: Session,
    purchase_id: int,
) -> Decimal:
    """
    Return the remaining amount owed to the supplier.
    """

    purchase = session.get(Purchase, purchase_id)

    if purchase is None:
        raise ValueError("Purchase not found.")

    paid_amount = get_purchase_paid_amount(
        session,
        purchase_id,
    )

    outstanding = purchase.total_amount - paid_amount

    if outstanding < Decimal("0.00"):
        return Decimal("0.00")

    return outstanding


def record_supplier_payment(
    session: Session,
    purchase_id: int,
    amount: Decimal,
    payment_method: str,
    reference: str | None = None,
    notes: str | None = None,
) -> Payment:
    """
    Record a payment made toward a supplier purchase.

    The payment amount cannot exceed the purchase's
    outstanding balance.

    The purchase payment status is updated automatically.
    """

    purchase = session.get(Purchase, purchase_id)

    if purchase is None:
        raise ValueError("Purchase not found.")

    if purchase.status != "completed":
        raise ValueError(
            "Payment can only be recorded for a completed purchase."
        )

    amount = Decimal(str(amount))

    if amount <= Decimal("0.00"):
        raise ValueError(
            "Payment amount must be greater than zero."
        )

    payment_method = payment_method.strip()

    if not payment_method:
        raise ValueError("Payment method is required.")

    outstanding = get_purchase_outstanding_amount(
        session,
        purchase_id,
    )

    if outstanding <= Decimal("0.00"):
        raise ValueError(
            "Purchase has already been fully paid."
        )

    if amount > outstanding:
        raise ValueError(
            f"Payment exceeds the outstanding balance of "
            f"{outstanding}."
        )

    payment = Payment(
        purchase_id=purchase.id,
        supplier_id=purchase.supplier_id,
        amount=amount,
        payment_method=payment_method,
        reference=reference,
        notes=notes,
    )

    session.add(payment)
    session.flush()

    paid_amount = get_purchase_paid_amount(
        session,
        purchase_id,
    )

    if paid_amount >= purchase.total_amount:
        purchase.payment_status = "paid"
    elif paid_amount > Decimal("0.00"):
        purchase.payment_status = "partial"
    else:
        purchase.payment_status = "unpaid"

    session.commit()
    session.refresh(payment)

    return payment
