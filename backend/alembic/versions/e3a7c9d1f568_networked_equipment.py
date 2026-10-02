"""networked equipment

Revision ID: e3a7c9d1f568
Revises: d1f6b2c8e457
Create Date: 2026-10-03 04:00:00.000000

Robotics Lab equipment (robots, PCs) monitored over the LAN: devices get
asset_id (the equipment this device is) and mode (NORMAL / EXAM /
MAINTENANCE); assets get bin_item (kept in the reusable smart bin);
equipment_sessions (RUNNING / IDLE / FAULT periods with the
booking in force) and policy_violations (exam-mode breaches a PC agent
reported). Robots are read-only.

Additive only.
"""
from alembic import op
import sqlalchemy as sa


revision = 'e3a7c9d1f568'
down_revision = 'd1f6b2c8e457'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table('equipment_sessions',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('device_id', sa.Integer(), nullable=False),
    sa.Column('asset_id', sa.Integer(), nullable=True),
    sa.Column('lab_id', sa.Integer(), nullable=False),
    sa.Column('state', sa.String(length=16), nullable=False),
    sa.Column('user_id', sa.Integer(), nullable=True),
    sa.Column('booking_id', sa.Integer(), nullable=True),
    sa.Column('detail', sa.JSON(), nullable=True),
    sa.Column('started_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('ended_at', sa.DateTime(timezone=True), nullable=True),
    sa.ForeignKeyConstraint(['asset_id'], ['assets.id'], ),
    sa.ForeignKeyConstraint(['booking_id'], ['bookings.id'], ),
    sa.ForeignKeyConstraint(['device_id'], ['devices.id'], ),
    sa.ForeignKeyConstraint(['lab_id'], ['labs.id'], ),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_equipment_sessions_device_id'), 'equipment_sessions', ['device_id'], unique=False)
    op.create_index(op.f('ix_equipment_sessions_lab_id'), 'equipment_sessions', ['lab_id'], unique=False)
    op.create_index(op.f('ix_equipment_sessions_started_at'), 'equipment_sessions', ['started_at'], unique=False)
    op.create_table('policy_violations',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('device_id', sa.Integer(), nullable=False),
    sa.Column('lab_id', sa.Integer(), nullable=False),
    sa.Column('kind', sa.String(length=32), nullable=False),
    sa.Column('detail', sa.String(length=255), nullable=False),
    sa.Column('os_user', sa.String(length=64), nullable=True),
    sa.Column('reviewed', sa.Boolean(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['device_id'], ['devices.id'], ),
    sa.ForeignKeyConstraint(['lab_id'], ['labs.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_policy_violations_created_at'), 'policy_violations', ['created_at'], unique=False)
    op.create_index(op.f('ix_policy_violations_device_id'), 'policy_violations', ['device_id'], unique=False)
    op.create_index(op.f('ix_policy_violations_lab_id'), 'policy_violations', ['lab_id'], unique=False)
    op.add_column('assets', sa.Column('bin_item', sa.Boolean(), nullable=False,
                                      server_default=sa.false()))
    op.add_column('devices', sa.Column('asset_id', sa.Integer(), nullable=True))
    op.add_column('devices', sa.Column('mode', sa.String(length=16), nullable=True))
    op.create_foreign_key('fk_devices_asset', 'devices', 'assets', ['asset_id'], ['id'])


def downgrade() -> None:
    op.drop_constraint('fk_devices_asset', 'devices', type_='foreignkey')
    op.drop_column('devices', 'mode')
    op.drop_column('devices', 'asset_id')
    op.drop_column('assets', 'bin_item')
    op.drop_index(op.f('ix_policy_violations_lab_id'), table_name='policy_violations')
    op.drop_index(op.f('ix_policy_violations_device_id'), table_name='policy_violations')
    op.drop_index(op.f('ix_policy_violations_created_at'), table_name='policy_violations')
    op.drop_table('policy_violations')
    op.drop_index(op.f('ix_equipment_sessions_started_at'), table_name='equipment_sessions')
    op.drop_index(op.f('ix_equipment_sessions_lab_id'), table_name='equipment_sessions')
    op.drop_index(op.f('ix_equipment_sessions_device_id'), table_name='equipment_sessions')
    op.drop_table('equipment_sessions')
