from decimal import Decimal

from sqlalchemy.orm import Session

from app.models.product import Product
from app.models.sale import Sale
from app.models.sale_item import SaleItem
from app.models.stock_movement import StockMovement
from app.models.supplier import Supplier


def create_sale(
    session: Session,
    user_id: int,
    items: list[dict],
    customer_id: int | None = None,
) -> Sale:
    """
    Create a completed sale from the supplied cart items.

    Each item should contain:
        product_id
        quantity
        unit_price

    Optional special-order fields:
        source_type
        source_supplier_id
        source_unit_cost

    source_type may be:
        "stock"          - item comes from Abori stock
        "special_order"  - item is sourced from another supplier/shop
    """

    if not items:
        raise ValueError("Cannot create a sale with no items.")

    # Validate every cart item before changing the database.
    for item in items:
        if "product_id" not in item:
            raise ValueError("Each sale item must have a product_id.")

        if "quantity" not in item:
            raise ValueError("Each sale item must have a quantity.")

        if "unit_price" not in item:
            raise ValueError("Each sale item must have a unit_price.")

        product = session.get(Product, item["product_id"])

        if product is None:
            raise ValueError(
                f"Product with ID {item['product_id']} was not found."
            )

        if not product.is_active:
            raise ValueError(
                f"Product '{product.name}' is inactive."
            )

        quantity = Decimal(str(item["quantity"]))

        if quantity <= 0:
            raise ValueError(
                f"Quantity for '{product.name}' must be greater than zero."
            )

        source_type = item.get("source_type", "stock")

        if source_type not in {"stock", "special_order"}:
            raise ValueError(
                f"Invalid source_type '{source_type}' for '{product.name}'."
            )

        # Normal stock sales must have enough Abori stock.
        if source_type == "stock":
            if product.stock_quantity < quantity:
                raise ValueError(
                    f"Insufficient stock for '{product.name}'. "
                    f"Available: {product.stock_quantity}, "
                    f"requested: {quantity}."
                )

        # Special-order sales require a source supplier and source cost.
        if source_type == "special_order":
            source_supplier_id = item.get("source_supplier_id")

            if source_supplier_id is None:
                raise ValueError(
                    f"Special-order item '{product.name}' "
                    "must have a source_supplier_id."
                )

            supplier = session.get(Supplier, source_supplier_id)

            if supplier is None:
                raise ValueError(
                    f"Source supplier with ID {source_supplier_id} "
                    "was not found."
                )

            if "source_unit_cost" not in item:
                raise ValueError(
                    f"Special-order item '{product.name}' "
                    "must have a source_unit_cost."
                )

            source_unit_cost = Decimal(str(item["source_unit_cost"]))

            if source_unit_cost < 0:
                raise ValueError(
                    f"Source unit cost for '{product.name}' "
                    "cannot be negative."
                )

    # Calculate the sale totals.
    subtotal = Decimal("0.00")
    sale_items = []

    for item in items:
        product = session.get(Product, item["product_id"])

        quantity = Decimal(str(item["quantity"]))
        unit_price = Decimal(str(item["unit_price"]))

        if unit_price < 0:
            raise ValueError(
                f"Unit price for '{product.name}' cannot be negative."
            )

        source_type = item.get("source_type", "stock")

        source_supplier_id = None
        source_unit_cost = None

        if source_type == "special_order":
            source_supplier_id = item["source_supplier_id"]
            source_unit_cost = Decimal(str(item["source_unit_cost"]))

        line_total = quantity * unit_price
        subtotal += line_total

        sale_items.append(
            {
                "product": product,
                "quantity": quantity,
                "unit_price": unit_price,
                "line_total": line_total,
                "source_type": source_type,
                "source_supplier_id": source_supplier_id,
                "source_unit_cost": source_unit_cost,
            }
        )

    # Generate a temporary sequential sale number.
    sale_number = f"SALE-{session.query(Sale).count() + 1:06d}"

    # Create the sale header.
    sale = Sale(
        sale_number=sale_number,
        user_id=user_id,
        customer_id=customer_id,
        subtotal=subtotal,
        tax_amount=Decimal("0.00"),
        discount_amount=Decimal("0.00"),
        total_amount=subtotal,
        payment_status="unpaid",
        status="completed",
    )

    session.add(sale)
    session.flush()

    # Create sale items and handle stock according to the source type.
    for item in sale_items:
        product = item["product"]
        quantity = item["quantity"]

        sale_item = SaleItem(
            sale_id=sale.id,
            product_id=product.id,
            quantity=quantity,
            unit_price=item["unit_price"],
            tax_amount=Decimal("0.00"),
            discount_amount=Decimal("0.00"),
            line_total=item["line_total"],
            source_type=item["source_type"],
            source_supplier_id=item["source_supplier_id"],
            source_unit_cost=item["source_unit_cost"],
        )

        session.add(sale_item)

        # Only normal stock sales reduce Abori's inventory.
        if item["source_type"] == "stock":
            product.stock_quantity -= quantity

            movement = StockMovement(
                product_id=product.id,
                movement_type="sale",
                quantity=-quantity,
                reference=f"Sale #{sale.id}",
                notes=f"Sold through sale #{sale.id}",
            )

            session.add(movement)

    session.commit()
    session.refresh(sale)

    return sale