"""Personal door QR credentials.

Only a new table - nothing existing is changed or dropped.

Revision ID: c4f8a2e6d913
Revises: b7e2d4f6a830
"""
import sqlalchemy as sa
from alembic import op

revision = 'c4f8a2e6d913'
down_revision = 'b7e2d4f6a830'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "personal_qr_credentials",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("user_id", sa.Integer, sa.ForeignKey("users.id"), nullable=False, index=True),
        sa.Column("token_sha256", sa.String(64), nullable=False, unique=True, index=True),
        sa.Column("issued_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("issued_by_id", sa.Integer, sa.ForeignKey("users.id"), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade():
    raise RuntimeError("personal_qr_credentials holds credential history; not dropped by a downgrade")
