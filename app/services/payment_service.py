from decimal import Decimal

from sqlalchemy.orm import Session

from app.models.payment import Payment
from app.models.sale import Sale


def get_sale_paid_amount(
    session: Session,
    sale_id: int,
) -> Decimal:
    """
    Return the total amount already paid toward a sale.
    """

    sale = session.get(Sale, sale_id)

    if sale is None:
        raise ValueError("Sale not found.")

    payments = (
        session.query(Payment)
        .filter(Payment.sale_id == sale_id)
        .all()
    )

    return sum(
        (payment.amount for payment in payments),
        Decimal("0.00"),
    )


def get_sale_outstanding_amount(
    session: Session,
    sale_id: int,
) -> Decimal:
    """
    Return the remaining amount owed on a sale.
    """

    sale = session.get(Sale, sale_id)

    if sale is None:
        raise ValueError("Sale not found.")

    paid_amount = get_sale_paid_amount(session, sale_id)

    outstanding = sale.total_amount - paid_amount

    if outstanding < Decimal("0.00"):
        return Decimal("0.00")

    return outstanding


def record_sale_payment(
    session: Session,
    sale_id: int,
    amount: Decimal,
    payment_method: str,
    reference: str | None = None,
    notes: str | None = None,
) -> Payment:
    """
    Record a payment made toward a sale.

    The payment amount cannot exceed the sale's outstanding balance.
    The sale payment status is updated automatically.
    """

    sale = session.get(Sale, sale_id)

    if sale is None:
        raise ValueError("Sale not found.")

    if sale.status != "completed":
        raise ValueError(
            "Payment can only be recorded for a completed sale."
        )

    amount = Decimal(str(amount))

    if amount <= Decimal("0.00"):
        raise ValueError("Payment amount must be greater than zero.")

    payment_method = payment_method.strip()

    if not payment_method:
        raise ValueError("Payment method is required.")

    outstanding = get_sale_outstanding_amount(
        session,
        sale_id,
    )

    if outstanding <= Decimal("0.00"):
        raise ValueError("Sale has already been fully paid.")

    if amount > outstanding:
        raise ValueError(
            f"Payment exceeds the outstanding balance of "
            f"{outstanding}."
        )

    payment = Payment(
        sale_id=sale.id,
        customer_id=sale.customer_id,
        amount=amount,
        payment_method=payment_method,
        reference=reference,
        notes=notes,
    )

    session.add(payment)
    session.flush()

    paid_amount = get_sale_paid_amount(
        session,
        sale_id,
    )

    if paid_amount >= sale.total_amount:
        sale.payment_status = "paid"
    elif paid_amount > Decimal("0.00"):
        sale.payment_status = "partial"
    else:
        sale.payment_status = "unpaid"

    session.commit()
    session.refresh(payment)

    return payment