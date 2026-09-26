"""automation outbox and dedupe keys

Revision ID: d7a4c2e9f1b3
Revises: c3e5a91d4b27
Create Date: 2026-09-26 12:00:00.000000

integration_events: the transactional outbox n8n consumes (pushed by the
dispatcher, or pulled from /api/automation/events). An integration record,
not the audit trail - access_events is unchanged and stays authoritative.

notifications.dedupe_key / alerts.dedupe_key: so a retried automation run
creates a notification or alert exactly once. Nullable - every existing row
and every row the portal raises itself has none.

Additive only.
"""
from alembic import op
import sqlalchemy as sa


revision = 'd7a4c2e9f1b3'
down_revision = 'c3e5a91d4b27'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'integration_events',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('event_id', sa.String(length=36), nullable=False),
        sa.Column('event_type', sa.String(length=48), nullable=False),
        sa.Column('occurred_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('lab_id', sa.Integer(), nullable=True),
        sa.Column('user_id', sa.Integer(), nullable=True),
        sa.Column('device_id', sa.Integer(), nullable=True),
        sa.Column('object_type', sa.String(length=32), nullable=True),
        sa.Column('object_id', sa.String(length=48), nullable=True),
        sa.Column('correlation_id', sa.String(length=64), nullable=True),
        sa.Column('payload', sa.JSON(), nullable=True),
        sa.Column('delivery_status', sa.String(length=16), nullable=False),
        sa.Column('attempts', sa.Integer(), nullable=False),
        sa.Column('next_attempt_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('delivered_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('last_error', sa.String(length=255), nullable=True),
    )
    op.create_index('ix_integration_events_event_id', 'integration_events',
                    ['event_id'], unique=True)
    op.create_index('ix_integration_events_event_type', 'integration_events',
                    ['event_type'])
    op.create_index('ix_integration_events_occurred_at', 'integration_events',
                    ['occurred_at'])
    op.create_index('ix_integration_events_correlation_id',
                    'integration_events', ['correlation_id'])
    op.create_index('ix_integration_due', 'integration_events',
                    ['delivery_status', 'next_attempt_at'])

    op.add_column('notifications', sa.Column('dedupe_key', sa.String(length=160),
                                             nullable=True))
    op.create_unique_constraint('uq_notification_dedupe', 'notifications',
                                ['user_id', 'dedupe_key'])
    op.add_column('alerts', sa.Column('dedupe_key', sa.String(length=160),
                                      nullable=True))
    op.create_unique_constraint('uq_alerts_dedupe_key', 'alerts', ['dedupe_key'])


def downgrade() -> None:
    op.drop_constraint('uq_alerts_dedupe_key', 'alerts', type_='unique')
    op.drop_column('alerts', 'dedupe_key')
    op.drop_constraint('uq_notification_dedupe', 'notifications', type_='unique')
    op.drop_column('notifications', 'dedupe_key')
    op.drop_index('ix_integration_due', table_name='integration_events')
    op.drop_index('ix_integration_events_correlation_id',
                  table_name='integration_events')
    op.drop_index('ix_integration_events_occurred_at',
                  table_name='integration_events')
    op.drop_index('ix_integration_events_event_type',
                  table_name='integration_events')
    op.drop_index('ix_integration_events_event_id',
                  table_name='integration_events')
    op.drop_table('integration_events')
