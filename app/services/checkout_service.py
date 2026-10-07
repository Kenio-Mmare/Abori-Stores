from decimal import Decimal

from sqlalchemy.orm import Session

from app.models.payment import Payment
from app.models.sale import Sale
from app.services.sale_service import create_sale


def checkout_sale(
    session: Session,
    user_id: int,
    items: list[dict],
    payments: list[dict],
    customer_id: int | None = None,
) -> Sale:
    """
    Create a sale and process its payments as one transaction.

    Each payment should contain:
        amount
        payment_method

    Optional payment fields:
        reference
        notes

    A customer is required when the payment total is less
    than the sale total.

    Example:

        Sale total: KSh 1,000

        Cash:  KSh 300
        M-Pesa: KSh 500
        Outstanding: KSh 200

    In that case customer_id must be supplied.
    """

    if not payments:
        raise ValueError("At least one payment is required.")

    # Validate payment data before creating the sale.
    payment_data = []

    for payment in payments:
        if "amount" not in payment:
            raise ValueError(
                "Each payment must have an amount."
            )

        if "payment_method" not in payment:
            raise ValueError(
                "Each payment must have a payment_method."
            )

        amount = Decimal(str(payment["amount"]))

        if amount <= Decimal("0.00"):
            raise ValueError(
                "Payment amount must be greater than zero."
            )

        payment_method = payment["payment_method"].strip()

        if not payment_method:
            raise ValueError(
                "Payment method is required."
            )

        payment_data.append(
            {
                "amount": amount,
                "payment_method": payment_method,
                "reference": payment.get("reference"),
                "notes": payment.get("notes"),
            }
        )

    try:
        # Create the sale without committing yet.
        sale = create_sale(
            session=session,
            user_id=user_id,
            items=items,
            customer_id=customer_id,
            auto_commit=False,
        )

        total_paid = sum(
            (payment["amount"] for payment in payment_data),
            Decimal("0.00"),
        )

        if total_paid > sale.total_amount:
            raise ValueError(
                f"Payment exceeds the sale total of "
                f"{sale.total_amount}."
            )

        outstanding = sale.total_amount - total_paid

        # Outstanding credit requires a customer.
        if outstanding > Decimal("0.00") and customer_id is None:
            raise ValueError(
                "A customer is required when the sale has "
                "an outstanding balance."
            )

        # Record each actual payment.
        for payment_data_item in payment_data:
            payment = Payment(
                sale_id=sale.id,
                customer_id=customer_id,
                amount=payment_data_item["amount"],
                payment_method=payment_data_item["payment_method"],
                reference=payment_data_item["reference"],
                notes=payment_data_item["notes"],
            )

            session.add(payment)

        # Update the sale payment status.
        if outstanding == Decimal("0.00"):
            sale.payment_status = "paid"
        else:
            sale.payment_status = "partial"

        session.commit()
        session.refresh(sale)

        return sale

    except Exception:
        session.rollback()
        raise
    