"""emergency message voice

Revision ID: c4e8a2f7b915
Revises: a9d4e7c2b310
Create Date: 2026-10-06 22:30:00.000000

lab_emergencies.speak: the admin's emergency message is read aloud (door
tablet, every portal screen) until it is cleared or the sound is switched
off. Additive only.
"""
from alembic import op
import sqlalchemy as sa


revision = 'c4e8a2f7b915'
down_revision = 'a9d4e7c2b310'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('lab_emergencies', sa.Column('speak', sa.Boolean(), nullable=False,
                                               server_default=sa.true()))


def downgrade() -> None:
    op.drop_column('lab_emergencies', 'speak')
