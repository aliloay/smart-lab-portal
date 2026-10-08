"""Robot monitoring: robot_events, robot_home_calibrations.

Only new tables - nothing existing is changed or dropped.

Revision ID: a3c5e7f9b124
Revises: d7b3f1e9a246
"""
import sqlalchemy as sa
from alembic import op

revision = 'a3c5e7f9b124'
down_revision = 'd7b3f1e9a246'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "robot_events",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("device_id", sa.Integer, sa.ForeignKey("devices.id"), nullable=False, index=True),
        sa.Column("lab_id", sa.Integer, sa.ForeignKey("labs.id"), nullable=False, index=True),
        sa.Column("kind", sa.String(32), nullable=False, index=True),
        sa.Column("joint", sa.Integer, nullable=True),
        sa.Column("detail", sa.JSON, nullable=True),
        sa.Column("source", sa.String(16), nullable=False, server_default="RTDE"),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False, index=True),
        sa.Column("received_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("booking_id", sa.Integer, sa.ForeignKey("bookings.id"), nullable=True),
        sa.Column("context", sa.JSON, nullable=True),
        sa.Column("severity", sa.String(12), nullable=False, server_default="INFO"),
        sa.Column("provenance", sa.String(24), nullable=False, server_default="UNKNOWN_PROVENANCE", index=True),
        sa.Column("experiment_id", sa.Integer, sa.ForeignKey("experiments.id"), nullable=True, index=True),
    )
    op.create_table(
        "robot_home_calibrations",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("device_id", sa.Integer, sa.ForeignKey("devices.id"), nullable=False, index=True),
        sa.Column("version", sa.Integer, nullable=False),
        sa.Column("home_q", sa.JSON, nullable=False),
        sa.Column("home_tcp", sa.JSON, nullable=True),
        sa.Column("tolerance_deg", sa.Float, nullable=False, server_default="1.0"),
        sa.Column("note", sa.String(255), nullable=False, server_default=""),
        sa.Column("created_by_id", sa.Integer, sa.ForeignKey("users.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )


def downgrade():
    # Never drops recorded data automatically (NEVER delete data): refuse.
    raise RuntimeError("robot_events / robot_home_calibrations hold recorded data - not dropped automatically")
