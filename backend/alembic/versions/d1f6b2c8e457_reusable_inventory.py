"""reusable inventory

Revision ID: d1f6b2c8e457
Revises: c9e5a1b7d346
Create Date: 2026-10-03 03:00:00.000000

Robotics Lab System 4: assets.nfc_uid (the item's NTAG213 sticker - an
identifier, not authentication) and smart-bin context on asset
transactions (booking, bin node, source). Existing transactions get
source = STAFF, which is what they were.

Additive only.
"""
from alembic import op
import sqlalchemy as sa


revision = 'd1f6b2c8e457'
down_revision = 'c9e5a1b7d346'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('asset_transactions', sa.Column('booking_id', sa.Integer(), nullable=True))
    op.add_column('asset_transactions', sa.Column('device_id', sa.Integer(), nullable=True))
    op.add_column('asset_transactions', sa.Column('source', sa.String(length=16),
                                                  nullable=False, server_default='STAFF'))
    op.create_foreign_key('fk_asset_tx_booking', 'asset_transactions', 'bookings',
                          ['booking_id'], ['id'])
    op.create_foreign_key('fk_asset_tx_device', 'asset_transactions', 'devices',
                          ['device_id'], ['id'])
    op.add_column('assets', sa.Column('nfc_uid', sa.String(length=32), nullable=True))
    op.create_unique_constraint('uq_assets_nfc_uid', 'assets', ['nfc_uid'])


def downgrade() -> None:
    op.drop_constraint('uq_assets_nfc_uid', 'assets', type_='unique')
    op.drop_column('assets', 'nfc_uid')
    op.drop_constraint('fk_asset_tx_device', 'asset_transactions', type_='foreignkey')
    op.drop_constraint('fk_asset_tx_booking', 'asset_transactions', type_='foreignkey')
    op.drop_column('asset_transactions', 'source')
    op.drop_column('asset_transactions', 'device_id')
    op.drop_column('asset_transactions', 'booking_id')
