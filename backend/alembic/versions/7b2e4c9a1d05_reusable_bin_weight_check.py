"""reusable bin weight check

Revision ID: 7b2e4c9a1d05
Revises: 56076a8ed8a3
Create Date: 2026-10-03 16:10:00.000000

The reusable smart bin's load cell, the third proof of a checkout or a
return besides the portal and the NFC tag: assets.unit_mass_g (learnt from
the first return or set by staff) and, per bin transaction, the mass change
over the lid cycle and its verdict (MATCH / MISMATCH / LEARNED / NO_SCALE).

Additive only.
"""
from alembic import op
import sqlalchemy as sa


revision = '7b2e4c9a1d05'
down_revision = '56076a8ed8a3'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('assets', sa.Column('unit_mass_g', sa.Float(), nullable=True))
    op.add_column('asset_transactions', sa.Column('mass_delta_g', sa.Float(), nullable=True))
    op.add_column('asset_transactions', sa.Column('weight_check', sa.String(length=16), nullable=True))


def downgrade() -> None:
    op.drop_column('asset_transactions', 'weight_check')
    op.drop_column('asset_transactions', 'mass_delta_g')
    op.drop_column('assets', 'unit_mass_g')
