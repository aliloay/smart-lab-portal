"""Incident handling on alerts (state, acknowledgement, owner, resolution) + incident_notes.

Additive only: new nullable columns / a defaulted column and a new table. Existing alerts are
backfilled to RESOLVED when already resolved, OPEN otherwise. Downgrade removes only what this adds.
"""
import sqlalchemy as sa
from alembic import op

revision = "a9d4e7c1b305"
down_revision = "c3f8a1e5d720"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("alerts", sa.Column("state", sa.String(16), nullable=False, server_default="OPEN"))
    op.add_column("alerts", sa.Column("acknowledged_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("alerts", sa.Column("acknowledged_by_id", sa.Integer, sa.ForeignKey("users.id"), nullable=True))
    op.add_column("alerts", sa.Column("owner_id", sa.Integer, sa.ForeignKey("users.id"), nullable=True))
    op.add_column("alerts", sa.Column("resolved_by_id", sa.Integer, sa.ForeignKey("users.id"), nullable=True))
    op.add_column("alerts", sa.Column("resolution", sa.String(500), nullable=True))
    op.create_index("ix_alerts_state", "alerts", ["state"])
    op.execute("update alerts set state = 'RESOLVED' where is_resolved")
    op.create_table(
        "incident_notes",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("alert_id", sa.Integer, sa.ForeignKey("alerts.id"), nullable=False, index=True),
        sa.Column("user_id", sa.Integer, sa.ForeignKey("users.id"), nullable=True),
        sa.Column("kind", sa.String(16), nullable=False),
        sa.Column("text", sa.String(2000), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, index=True),
    )


def downgrade():
    op.drop_table("incident_notes")
    op.drop_index("ix_alerts_state", "alerts")
    for c in ("resolution", "resolved_by_id", "owner_id", "acknowledged_by_id", "acknowledged_at", "state"):
        op.drop_column("alerts", c)
