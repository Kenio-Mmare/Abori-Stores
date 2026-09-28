from sqlalchemy.orm import Session

from app.models.product import Product
from app.models.purchase import Purchase
from app.models.purchase_item import PurchaseItem
from app.models.stock_movement import StockMovement


def receive_purchase(session: Session, purchase_id: int) -> Purchase:
    purchase = session.get(Purchase, purchase_id)

    if purchase is None:
        raise ValueError("Purchase not found.")

    if purchase.status != "draft":
        raise ValueError(
            f"Purchase cannot be received because its status is "
            f"'{purchase.status}'."
        )

    items = (
        session.query(PurchaseItem)
        .filter(PurchaseItem.purchase_id == purchase_id)
        .all()
    )

    if not items:
        raise ValueError("Cannot receive a purchase with no items.")

    for item in items:
        product = session.get(Product, item.product_id)

        if product is None:
            raise ValueError(
                f"Product with ID {item.product_id} was not found."
            )

        if item.quantity <= 0:
            raise ValueError(
                f"Purchase item {item.id} has an invalid quantity."
            )

        if item.unit_cost < 0:
            raise ValueError(
                f"Purchase item {item.id} has an invalid unit cost."
            )

        product.stock_quantity += item.quantity
        product.purchase_cost = item.unit_cost

        movement = StockMovement(
            product_id=product.id,
            movement_type="purchase",
            quantity=item.quantity,
            reference=f"Purchase #{purchase.id}",
            notes=f"Received from purchase #{purchase.id}",
        )

        session.add(movement)

    purchase.status = "completed"

    session.commit()
    session.refresh(purchase)

    return purchase
