"""Robotics Lab room correction: Room 202 -> Room 214 (owner, 2026-10-14).

Data-only. Changes LAB_01 only, and only while it still holds the old value; downgrade restores it.
"""
from alembic import op

revision = "b7e4c2d9a614"
down_revision = "a9d3f1c7b520"
branch_labels = None
depends_on = None

OLD, NEW = "Building S, Floor 2, Room 202", "Building S, Floor 2, Room 214"


def upgrade():
    op.execute(f"UPDATE labs SET location = '{NEW}' WHERE code = 'LAB_01' AND location = '{OLD}'")


def downgrade():
    op.execute(f"UPDATE labs SET location = '{OLD}' WHERE code = 'LAB_01' AND location = '{NEW}'")
