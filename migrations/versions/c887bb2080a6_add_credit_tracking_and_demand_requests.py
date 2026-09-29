"""Add credit tracking and demand requests

Revision ID: c887bb2080a6
Revises: 45f72b631997
Create Date: 2026-09-29

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "c887bb2080a6"
down_revision: Union[str, Sequence[str], None] = "45f72b631997"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""

    # ---------------------------------------------------------
    # 1. Customers
    # ---------------------------------------------------------
    op.create_table(
        "customers",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("name", sa.String(length=150), nullable=False),
        sa.Column("phone", sa.String(length=30), nullable=True),
        sa.Column("email", sa.String(length=150), nullable=True),
        sa.Column("address", sa.String(length=255), nullable=True),
        sa.Column("notes", sa.String(length=255), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_index(
        "ix_customers_name",
        "customers",
        ["name"],
        unique=False,
    )

    # ---------------------------------------------------------
    # 2. Demand requests
    # ---------------------------------------------------------
    op.create_table(
        "demand_requests",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("product_id", sa.Integer(), nullable=True),
        sa.Column(
            "requested_item_name",
            sa.String(length=150),
            nullable=False,
        ),
        sa.Column("category", sa.String(length=100), nullable=True),
        sa.Column(
            "quantity_requested",
            sa.Numeric(precision=12, scale=3),
            nullable=True,
        ),
        sa.Column("customer_id", sa.Integer(), nullable=True),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("request_date", sa.DateTime(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(
            ["customer_id"],
            ["customers.id"],
        ),
        sa.ForeignKeyConstraint(
            ["product_id"],
            ["products.id"],
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_index(
        "ix_demand_requests_customer_id",
        "demand_requests",
        ["customer_id"],
        unique=False,
    )

    op.create_index(
        "ix_demand_requests_product_id",
        "demand_requests",
        ["product_id"],
        unique=False,
    )

    op.create_index(
        "ix_demand_requests_requested_item_name",
        "demand_requests",
        ["requested_item_name"],
        unique=False,
    )

    op.create_index(
        "ix_demand_requests_user_id",
        "demand_requests",
        ["user_id"],
        unique=False,
    )

    # ---------------------------------------------------------
    # 3. Payments
    # ---------------------------------------------------------
    op.create_table(
        "payments",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("sale_id", sa.Integer(), nullable=True),
        sa.Column("purchase_id", sa.Integer(), nullable=True),
        sa.Column("customer_id", sa.Integer(), nullable=True),
        sa.Column("supplier_id", sa.Integer(), nullable=True),
        sa.Column(
            "amount",
            sa.Numeric(precision=14, scale=2),
            nullable=False,
        ),
        sa.Column(
            "payment_method",
            sa.String(length=30),
            nullable=False,
        ),
        sa.Column(
            "payment_date",
            sa.DateTime(),
            nullable=False,
        ),
        sa.Column("reference", sa.String(length=100), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.CheckConstraint(
            """
            (
                sale_id IS NOT NULL
                AND purchase_id IS NULL
            )
            OR
            (
                sale_id IS NULL
                AND purchase_id IS NOT NULL
            )
            """,
            name="ck_payment_one_transaction",
        ),
        sa.ForeignKeyConstraint(
            ["customer_id"],
            ["customers.id"],
        ),
        sa.ForeignKeyConstraint(
            ["purchase_id"],
            ["purchases.id"],
        ),
        sa.ForeignKeyConstraint(
            ["sale_id"],
            ["sales.id"],
        ),
        sa.ForeignKeyConstraint(
            ["supplier_id"],
            ["suppliers.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_index(
        "ix_payments_customer_id",
        "payments",
        ["customer_id"],
        unique=False,
    )

    op.create_index(
        "ix_payments_purchase_id",
        "payments",
        ["purchase_id"],
        unique=False,
    )

    op.create_index(
        "ix_payments_sale_id",
        "payments",
        ["sale_id"],
        unique=False,
    )

    op.create_index(
        "ix_payments_supplier_id",
        "payments",
        ["supplier_id"],
        unique=False,
    )

    # ---------------------------------------------------------
    # 4. purchase_items
    #
    # Add line_total temporarily as nullable so existing rows
    # can be populated safely.
    # ---------------------------------------------------------
    op.add_column(
        "purchase_items",
        sa.Column(
            "line_total",
            sa.Numeric(precision=14, scale=2),
            nullable=True,
        ),
    )

    op.execute(
        """
        UPDATE purchase_items
        SET line_total = quantity * unit_cost
        WHERE line_total IS NULL
        """
    )

    with op.batch_alter_table("purchase_items") as batch_op:
        batch_op.alter_column(
            "line_total",
            existing_type=sa.Numeric(
                precision=14,
                scale=2,
            ),
            nullable=False,
        )

    # ---------------------------------------------------------
    # 5. purchases
    #
    # Add new columns as nullable first, populate existing
    # records, then enforce NOT NULL.
    # ---------------------------------------------------------
    op.add_column(
        "purchases",
        sa.Column(
            "subtotal",
            sa.Numeric(precision=14, scale=2),
            nullable=True,
        ),
    )

    op.add_column(
        "purchases",
        sa.Column(
            "tax_amount",
            sa.Numeric(precision=14, scale=2),
            nullable=True,
        ),
    )

    op.add_column(
        "purchases",
        sa.Column(
            "total_amount",
            sa.Numeric(precision=14, scale=2),
            nullable=True,
        ),
    )

    op.add_column(
        "purchases",
        sa.Column(
            "payment_status",
            sa.String(length=20),
            nullable=True,
        ),
    )

    # Existing purchases did not previously store these totals.
    # We therefore reconstruct subtotal from their purchase items.
    op.execute(
        """
        UPDATE purchases
        SET subtotal = COALESCE(
            (
                SELECT SUM(purchase_items.line_total)
                FROM purchase_items
                WHERE purchase_items.purchase_id = purchases.id
            ),
            0
        )
        WHERE subtotal IS NULL
        """
    )

    # Historical purchase tax was not stored in the old schema.
    # Start those records at zero.
    op.execute(
        """
        UPDATE purchases
        SET tax_amount = 0
        WHERE tax_amount IS NULL
        """
    )

    op.execute(
        """
        UPDATE purchases
        SET total_amount = subtotal + tax_amount
        WHERE total_amount IS NULL
        """
    )

    # Existing purchases have no payment history yet.
    op.execute(
        """
        UPDATE purchases
        SET payment_status = 'unpaid'
        WHERE payment_status IS NULL
        """
    )

    with op.batch_alter_table("purchases") as batch_op:
        batch_op.alter_column(
            "subtotal",
            existing_type=sa.Numeric(
                precision=14,
                scale=2,
            ),
            nullable=False,
        )

        batch_op.alter_column(
            "tax_amount",
            existing_type=sa.Numeric(
                precision=14,
                scale=2,
            ),
            nullable=False,
        )

        batch_op.alter_column(
            "total_amount",
            existing_type=sa.Numeric(
                precision=14,
                scale=2,
            ),
            nullable=False,
        )

        batch_op.alter_column(
            "payment_status",
            existing_type=sa.String(length=20),
            nullable=False,
        )

    # ---------------------------------------------------------
    # 6. sales
    # ---------------------------------------------------------
    op.add_column(
        "sales",
        sa.Column(
            "customer_id",
            sa.Integer(),
            nullable=True,
        ),
    )

    op.add_column(
        "sales",
        sa.Column(
            "payment_status",
            sa.String(length=20),
            nullable=True,
        ),
    )

    # Existing sales have no payment ledger yet.
    op.execute(
        """
        UPDATE sales
        SET payment_status = 'unpaid'
        WHERE payment_status IS NULL
        """
    )

    with op.batch_alter_table("sales") as batch_op:
        batch_op.alter_column(
            "payment_status",
            existing_type=sa.String(length=20),
            nullable=False,
        )

        batch_op.create_index(
            "ix_sales_customer_id",
            ["customer_id"],
            unique=False,
        )

        batch_op.create_foreign_key(
            "fk_sales_customer_id",
            "customers",
            ["customer_id"],
            ["id"],
        )


def downgrade() -> None:
    """Downgrade schema."""

    # ---------------------------------------------------------
    # sales
    # ---------------------------------------------------------
    with op.batch_alter_table("sales") as batch_op:
        batch_op.drop_constraint(
            "fk_sales_customer_id",
            type_="foreignkey",
        )

        batch_op.drop_index(
            "ix_sales_customer_id",
        )

        batch_op.drop_column(
            "payment_status",
        )

        batch_op.drop_column(
            "customer_id",
        )

    # ---------------------------------------------------------
    # purchases
    # ---------------------------------------------------------
    with op.batch_alter_table("purchases") as batch_op:
        batch_op.drop_column("payment_status")
        batch_op.drop_column("total_amount")
        batch_op.drop_column("tax_amount")
        batch_op.drop_column("subtotal")

    # ---------------------------------------------------------
    # purchase_items
    # ---------------------------------------------------------
    with op.batch_alter_table("purchase_items") as batch_op:
        batch_op.drop_column("line_total")

    # ---------------------------------------------------------
    # payments
    # ---------------------------------------------------------
    op.drop_index(
        "ix_payments_supplier_id",
        table_name="payments",
    )

    op.drop_index(
        "ix_payments_sale_id",
        table_name="payments",
    )

    op.drop_index(
        "ix_payments_purchase_id",
        table_name="payments",
    )

    op.drop_index(
        "ix_payments_customer_id",
        table_name="payments",
    )

    op.drop_table("payments")

    # ---------------------------------------------------------
    # demand_requests
    # ---------------------------------------------------------
    op.drop_index(
        "ix_demand_requests_user_id",
        table_name="demand_requests",
    )

    op.drop_index(
        "ix_demand_requests_requested_item_name",
        table_name="demand_requests",
    )

    op.drop_index(
        "ix_demand_requests_product_id",
        table_name="demand_requests",
    )

    op.drop_index(
        "ix_demand_requests_customer_id",
        table_name="demand_requests",
    )

    op.drop_table("demand_requests")

    # ---------------------------------------------------------
    # customers
    # ---------------------------------------------------------
    op.drop_index(
        "ix_customers_name",
        table_name="customers",
    )

    op.drop_table("customers")
