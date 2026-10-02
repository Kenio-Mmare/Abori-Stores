"""Add special order sourcing to sale items

Revision ID: be7215ca5676
Revises: c887bb2080a6
Create Date: 2026-10-01 20:44:33.230903

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "be7215ca5676"
down_revision: Union[str, Sequence[str], None] = "c887bb2080a6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""

    # Add source_type as nullable first so existing rows can be migrated safely.
    op.add_column(
        "sale_items",
        sa.Column(
            "source_type",
            sa.String(length=20),
            nullable=True,
        ),
    )

    # Existing sale items were all sold from normal Abori stock.
    op.execute(
        "UPDATE sale_items SET source_type = 'stock' "
        "WHERE source_type IS NULL"
    )

    # Add the remaining special-order fields.
    op.add_column(
        "sale_items",
        sa.Column(
            "source_supplier_id",
            sa.Integer(),
            nullable=True,
        ),
    )

    op.add_column(
        "sale_items",
        sa.Column(
            "source_unit_cost",
            sa.Numeric(precision=12, scale=2),
            nullable=True,
        ),
    )

    # Make source_type required after existing records have been populated.
    with op.batch_alter_table("sale_items") as batch_op:
        batch_op.alter_column(
            "source_type",
            existing_type=sa.String(length=20),
            nullable=False,
        )

        batch_op.create_index(
            "ix_sale_items_source_supplier_id",
            ["source_supplier_id"],
            unique=False,
        )

        batch_op.create_foreign_key(
            "fk_sale_items_source_supplier_id",
            "suppliers",
            ["source_supplier_id"],
            ["id"],
        )


def downgrade() -> None:
    """Downgrade schema."""

    with op.batch_alter_table("sale_items") as batch_op:
        batch_op.drop_constraint(
            "fk_sale_items_source_supplier_id",
            type_="foreignkey",
        )

        batch_op.drop_index(
            "ix_sale_items_source_supplier_id",
        )

        batch_op.drop_column("source_unit_cost")
        batch_op.drop_column("source_supplier_id")
        batch_op.drop_column("source_type")
        