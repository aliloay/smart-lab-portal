"""Alert grouping: fingerprint, occurrence count, last seen, reopen count (2026-10-18).

Additive only: three defaulted / nullable columns and one index. Existing alerts get the same
fingerprint formula the service uses (device | lab | lower-cased title), last_seen_at = created_at,
occurrences = 1 - no existing row is merged, deleted or changed in meaning. Downgrade removes only
what this adds.
"""
import sqlalchemy as sa
from alembic import op

revision = "d5e8b2c4f917"
down_revision = "a9d4e7c1b305"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("alerts", sa.Column("fingerprint", sa.String(160), nullable=True))
    op.add_column("alerts", sa.Column("occurrences", sa.Integer, nullable=False, server_default="1"))
    op.add_column("alerts", sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("alerts", sa.Column("reopened_count", sa.Integer, nullable=False, server_default="0"))
    op.create_index("ix_alerts_fingerprint", "alerts", ["fingerprint"])
    op.execute("update alerts set fingerprint = coalesce(device_id::text, '0') || '|' || coalesce(lab_id::text, '0')"
               " || '|' || lower(left(trim(title), 120)) where fingerprint is null")
    op.execute("update alerts set last_seen_at = created_at where last_seen_at is null")


def downgrade():
    op.drop_index("ix_alerts_fingerprint", "alerts")
    for c in ("reopened_count", "last_seen_at", "occurrences", "fingerprint"):
        op.drop_column("alerts", c)
