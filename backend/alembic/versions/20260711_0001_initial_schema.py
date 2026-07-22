"""创建电商分析初始表结构。

Revision ID: 20260711_0001
Revises:
Create Date: 2026-07-11
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "20260711_0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """按外键依赖顺序创建 PostgreSQL 业务表。"""
    op.create_table(
        "regions",
        sa.Column("region_id", sa.Integer(), primary_key=True, autoincrement=False),
        sa.Column("region_name", sa.String(50)),
        sa.Column("province", sa.String(50)),
        sa.Column("city", sa.String(50)),
    )
    op.create_table(
        "customers",
        sa.Column("customer_id", sa.Integer(), primary_key=True, autoincrement=False),
        sa.Column("customer_name", sa.String(100)),
        sa.Column("gender", sa.String(10)),
        sa.Column("age", sa.Integer()),
        sa.Column("region_id", sa.Integer(), sa.ForeignKey("regions.region_id")),
        sa.Column("register_date", sa.Date()),
    )
    op.create_table(
        "categories",
        sa.Column("category_id", sa.Integer(), primary_key=True, autoincrement=False),
        sa.Column("category_name", sa.String(50)),
    )
    op.create_table(
        "products",
        sa.Column("product_id", sa.Integer(), primary_key=True, autoincrement=False),
        sa.Column("product_name", sa.String(100)),
        sa.Column("category_id", sa.Integer(), sa.ForeignKey("categories.category_id")),
        sa.Column("price", sa.Numeric(10, 2)),
        sa.Column("cost", sa.Numeric(10, 2)),
        sa.Column("created_at", sa.Date()),
    )
    op.create_table(
        "orders",
        sa.Column("order_id", sa.Integer(), primary_key=True, autoincrement=False),
        sa.Column("customer_id", sa.Integer(), sa.ForeignKey("customers.customer_id")),
        sa.Column("order_date", sa.Date()),
        sa.Column("status", sa.String(20)),
        sa.Column("total_amount", sa.Numeric(10, 2)),
    )
    op.create_table(
        "order_items",
        sa.Column("item_id", sa.Integer(), primary_key=True, autoincrement=False),
        sa.Column("order_id", sa.Integer(), sa.ForeignKey("orders.order_id")),
        sa.Column("product_id", sa.Integer(), sa.ForeignKey("products.product_id")),
        sa.Column("quantity", sa.Integer()),
        sa.Column("unit_price", sa.Numeric(10, 2)),
    )
    op.create_table(
        "payments",
        sa.Column("payment_id", sa.Integer(), primary_key=True, autoincrement=False),
        sa.Column("order_id", sa.Integer(), sa.ForeignKey("orders.order_id")),
        sa.Column("payment_method", sa.String(30)),
        sa.Column("payment_status", sa.String(20)),
        sa.Column("paid_amount", sa.Numeric(10, 2)),
        sa.Column("paid_at", sa.DateTime()),
    )
    op.create_table(
        "refunds",
        sa.Column("refund_id", sa.Integer(), primary_key=True, autoincrement=False),
        sa.Column("order_id", sa.Integer(), sa.ForeignKey("orders.order_id")),
        sa.Column("refund_amount", sa.Numeric(10, 2)),
        sa.Column("refund_reason", sa.String(100)),
        sa.Column("refund_date", sa.Date()),
    )


def downgrade() -> None:
    """按外键依赖逆序删除业务表。"""
    for table_name in (
        "refunds",
        "payments",
        "order_items",
        "orders",
        "products",
        "categories",
        "customers",
        "regions",
    ):
        op.drop_table(table_name)
