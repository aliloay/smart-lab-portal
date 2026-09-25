"""asset lifecycle fields and query indexes

Revision ID: c3e5a91d4b27
Revises: b8d41f7a2c90
Create Date: 2026-09-25 12:00:00.000000

Asset lifecycle: serial number, current holder (set on checkout, cleared on
return), last inspection and next scheduled maintenance. All nullable - an
item that has never been inspected says so rather than inventing a date.

Indexes, each backing a query the portal runs constantly:
  ix_booking_user_start    a person's bookings, newest first
  ix_event_user_time       a person's own access timeline
  ix_session_lab_open      open sessions (who is inside) per laboratory
  ix_asset_tx_asset_time   an item's usage and maintenance history

Additive only: no data is rewritten. The existing holder of a checked-out
item is backfilled from the latest CHECKOUT transaction, so current state
is right from the first request.
"""
from alembic import op
import sqlalchemy as sa


revision = 'c3e5a91d4b27'
down_revision = 'b8d41f7a2c90'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('assets', sa.Column('serial_number', sa.String(length=64), nullable=True))
    op.add_column('assets', sa.Column('holder_id', sa.Integer(), nullable=True))
    op.add_column('assets', sa.Column('checked_out_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('assets', sa.Column('last_inspected_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('assets', sa.Column('next_maintenance_at', sa.DateTime(timezone=True), nullable=True))
    op.create_foreign_key('fk_assets_holder_id_users', 'assets', 'users',
                          ['holder_id'], ['id'], ondelete='SET NULL')
    op.create_index('ix_assets_holder_id', 'assets', ['holder_id'])
    op.create_index('ix_assets_next_maintenance_at', 'assets', ['next_maintenance_at'])

    # Who has each currently checked-out item: the latest CHECKOUT.
    op.execute("""
        UPDATE assets a
           SET holder_id = t.user_id, checked_out_at = t.created_at
          FROM (SELECT DISTINCT ON (asset_id) asset_id, user_id, created_at
                  FROM asset_transactions
                 WHERE action = 'CHECKOUT'
                 ORDER BY asset_id, created_at DESC) t
         WHERE a.id = t.asset_id AND a.status = 'CHECKED_OUT'
    """)

    op.create_index('ix_booking_user_start', 'bookings', ['user_id', 'start_time'])
    op.create_index('ix_event_user_time', 'access_events', ['user_id', 'created_at'])
    op.create_index('ix_session_lab_open', 'access_sessions', ['lab_id', 'ended_at'])
    op.create_index('ix_asset_tx_asset_time', 'asset_transactions', ['asset_id', 'created_at'])


def downgrade() -> None:
    op.drop_index('ix_asset_tx_asset_time', table_name='asset_transactions')
    op.drop_index('ix_session_lab_open', table_name='access_sessions')
    op.drop_index('ix_event_user_time', table_name='access_events')
    op.drop_index('ix_booking_user_start', table_name='bookings')
    op.drop_index('ix_assets_next_maintenance_at', table_name='assets')
    op.drop_index('ix_assets_holder_id', table_name='assets')
    op.drop_constraint('fk_assets_holder_id_users', 'assets', type_='foreignkey')
    op.drop_column('assets', 'next_maintenance_at')
    op.drop_column('assets', 'last_inspected_at')
    op.drop_column('assets', 'checked_out_at')
    op.drop_column('assets', 'holder_id')
    op.drop_column('assets', 'serial_number')
