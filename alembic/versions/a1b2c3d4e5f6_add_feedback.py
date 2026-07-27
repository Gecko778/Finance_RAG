"""add feedback table

Revision ID: a1b2c3d4e5f6
Revises: 11fb1533c938
Create Date: 2026-07-27

"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "a1b2c3d4e5f6"
down_revision: str | Sequence[str] | None = "11fb1533c938"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "feedback",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("tenant_id", sa.Uuid(), sa.ForeignKey("tenants.id"), nullable=False, index=True),
        sa.Column("created_by", sa.Uuid(), nullable=True),
        sa.Column("query", sa.Text(), nullable=False),
        sa.Column("answer", sa.Text(), nullable=False, server_default=""),
        sa.Column("rating", sa.String(length=8), nullable=False),
        sa.Column("comment", sa.Text(), nullable=False, server_default=""),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("rating IN ('up', 'down')", name="ck_feedback_rating"),
    )
    op.create_index("ix_feedback_tenant_created", "feedback", ["tenant_id", "created_at"])

    # 新表需单独授权（初始迁移的 GRANT ALL 只覆盖当时已存在的表）+ RLS 租户隔离
    op.execute("GRANT SELECT, INSERT, UPDATE, DELETE ON feedback TO finance_rag_app")
    op.execute("ALTER TABLE feedback ENABLE ROW LEVEL SECURITY")
    op.execute("""
        CREATE POLICY feedback_tenant_all ON feedback
        FOR ALL
        USING (tenant_id::text = current_setting('app.tenant_id', true))
        WITH CHECK (tenant_id::text = current_setting('app.tenant_id', true))
    """)


def downgrade() -> None:
    op.execute("REVOKE ALL ON feedback FROM finance_rag_app")
    op.drop_index("ix_feedback_tenant_created", table_name="feedback")
    op.drop_table("feedback")
