"""emergency states, settings, master pc

Revision ID: 56076a8ed8a3
Revises: c665cd35a15b
Create Date: 2026-10-03 04:44:16.684116

Emergency tab (administrators, behind the emergency password):
lab_emergencies - each lab's emergency state, read every second by its door
controller (door held open / lockdown, message on LCD and tablet, alarm);
system_settings - small key/value settings (the emergency password's bcrypt
hash once changed from the portal). devices.is_master_pc marks the lab
engineer's master PC (administrators only).

Additive only.
"""
from alembic import op
import sqlalchemy as sa


revision = '56076a8ed8a3'
down_revision = 'c665cd35a15b'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table('system_settings',
    sa.Column('key', sa.String(length=64), nullable=False),
    sa.Column('value', sa.Text(), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    sa.PrimaryKeyConstraint('key')
    )
    op.create_table('lab_emergencies',
    sa.Column('lab_id', sa.Integer(), nullable=False),
    sa.Column('door_mode', sa.String(length=16), nullable=False),
    sa.Column('door_until', sa.DateTime(timezone=True), nullable=True),
    sa.Column('message', sa.String(length=96), nullable=False),
    sa.Column('message_until', sa.DateTime(timezone=True), nullable=True),
    sa.Column('alarm', sa.Boolean(), nullable=False),
    sa.Column('version', sa.Integer(), nullable=False),
    sa.Column('updated_by_id', sa.Integer(), nullable=True),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['lab_id'], ['labs.id'], ),
    sa.ForeignKeyConstraint(['updated_by_id'], ['users.id'], ),
    sa.PrimaryKeyConstraint('lab_id')
    )
    op.add_column('devices', sa.Column('is_master_pc', sa.Boolean(), server_default='false', nullable=False))


def downgrade() -> None:
    op.drop_column('devices', 'is_master_pc')
    op.drop_table('lab_emergencies')
    op.drop_table('system_settings')
