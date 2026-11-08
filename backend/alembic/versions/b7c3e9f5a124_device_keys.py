"""per-device keys

Revision ID: b7c3e9f5a124
Revises: a6b2d8e4f013
Create Date: 2026-10-03 01:30:00.000000

devices.key_hash: SHA-256 of a device's own key, issued on the Devices
page. NULL = the device still uses the shared DEVICE_API_KEY. A device
with its own key may only report as itself.

Additive only.
"""
from alembic import op
import sqlalchemy as sa


revision = 'b7c3e9f5a124'
down_revision = 'a6b2d8e4f013'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('devices', sa.Column('key_hash', sa.String(length=64), nullable=True))
    op.create_unique_constraint('uq_devices_key_hash', 'devices', ['key_hash'])


def downgrade() -> None:
    op.drop_constraint('uq_devices_key_hash', 'devices', type_='unique')
    op.drop_column('devices', 'key_hash')
