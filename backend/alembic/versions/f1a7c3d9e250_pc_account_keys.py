"""One key per Windows account on a lab PC (2026-11-07).

Additive only: one new table. Without it, a second account enrolling on a PC replaced the key of the first, so the two
accounts' agents locked each other out. No existing row changes. Downgrade removes the table.
"""
import sqlalchemy as sa
from alembic import op

revision = "f1a7c3d9e250"
down_revision = "e6c2a8f4b170"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "pc_account_keys",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("device_id", sa.Integer(), sa.ForeignKey("devices.id", ondelete="CASCADE"), nullable=False),
        sa.Column("account", sa.String(64), nullable=False),
        sa.Column("key_hash", sa.String(64), nullable=False, unique=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("device_id", "account", name="uq_pc_account_keys_device_account"),
    )


def downgrade():
    op.drop_table("pc_account_keys")
