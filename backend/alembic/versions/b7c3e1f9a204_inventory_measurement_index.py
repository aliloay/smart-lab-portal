"""Index for "the newest reading of this bin" (2026-10-18).

A bin sends about one stable reading per second (~86 000 rows a day). Every reading looked up the
bin's previous one and the bin list now shows when the last reading arrived; both are
WHERE bin_id = ? ORDER BY recorded_at DESC LIMIT 1, which only had a bin_id index (all of the bin's
rows sorted). Additive only: one index; downgrade removes it. No row is changed.
"""
from alembic import op

revision = "b7c3e1f9a204"
down_revision = "d5e8b2c4f917"
branch_labels = None
depends_on = None


def upgrade():
    op.create_index("ix_inventory_measurements_bin_time", "inventory_measurements", ["bin_id", "recorded_at"])


def downgrade():
    op.drop_index("ix_inventory_measurements_bin_time", "inventory_measurements")
