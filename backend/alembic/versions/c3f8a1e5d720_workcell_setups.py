"""Virtual workcell setups for the robot digital twins (versioned rows, never overwritten)."""
import sqlalchemy as sa
from alembic import op

revision = "c3f8a1e5d720"
down_revision = "b7e4c2d9a614"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "workcell_setups",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("robot_key", sa.String(16), nullable=False, index=True),
        sa.Column("name", sa.String(64), nullable=False),
        sa.Column("data", sa.JSON, nullable=False),
        sa.Column("created_by_id", sa.Integer, sa.ForeignKey("users.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )


def downgrade():
    op.drop_table("workcell_setups")
