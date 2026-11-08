"""security camera zones and events

Revision ID: c665cd35a15b
Revises: e3a7c9d1f568
Create Date: 2026-10-03 04:14:35.123289

Security camera (tools/security_vision): security_zones (boxes drawn on the
camera view - fixed equipment to watch, or the door area) and
security_events (what the camera saw that staff should check, with a
snapshot). devices.device_type gains SECURITY_CAMERA (a VARCHAR, no change).

Additive only.
"""
from alembic import op
import sqlalchemy as sa


revision = 'c665cd35a15b'
down_revision = 'e3a7c9d1f568'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table('security_zones',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('device_id', sa.Integer(), nullable=False),
    sa.Column('name', sa.String(length=64), nullable=False),
    sa.Column('kind', sa.String(length=16), nullable=False),
    sa.Column('asset_id', sa.Integer(), nullable=True),
    sa.Column('x', sa.Float(), nullable=False),
    sa.Column('y', sa.Float(), nullable=False),
    sa.Column('w', sa.Float(), nullable=False),
    sa.Column('h', sa.Float(), nullable=False),
    sa.Column('alert_on_motion', sa.Boolean(), nullable=False),
    sa.Column('ref_version', sa.Integer(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['asset_id'], ['assets.id'], ),
    sa.ForeignKeyConstraint(['device_id'], ['devices.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_security_zones_device_id'), 'security_zones', ['device_id'], unique=False)
    op.create_table('security_events',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('device_id', sa.Integer(), nullable=False),
    sa.Column('lab_id', sa.Integer(), nullable=False),
    sa.Column('zone_id', sa.Integer(), nullable=True),
    sa.Column('kind', sa.String(length=32), nullable=False),
    sa.Column('detail', sa.String(length=255), nullable=False),
    sa.Column('people_seen', sa.Integer(), nullable=False),
    sa.Column('people_inside', sa.Integer(), nullable=False),
    sa.Column('snapshot_key', sa.String(length=255), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('acknowledged_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('acknowledged_by_id', sa.Integer(), nullable=True),
    sa.ForeignKeyConstraint(['acknowledged_by_id'], ['users.id'], ),
    sa.ForeignKeyConstraint(['device_id'], ['devices.id'], ),
    sa.ForeignKeyConstraint(['lab_id'], ['labs.id'], ),
    sa.ForeignKeyConstraint(['zone_id'], ['security_zones.id'], ondelete='SET NULL'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_security_events_created_at'), 'security_events', ['created_at'], unique=False)
    op.create_index(op.f('ix_security_events_device_id'), 'security_events', ['device_id'], unique=False)
    op.create_index(op.f('ix_security_events_lab_id'), 'security_events', ['lab_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_security_events_lab_id'), table_name='security_events')
    op.drop_index(op.f('ix_security_events_device_id'), table_name='security_events')
    op.drop_index(op.f('ix_security_events_created_at'), table_name='security_events')
    op.drop_table('security_events')
    op.drop_index(op.f('ix_security_zones_device_id'), table_name='security_zones')
    op.drop_table('security_zones')
