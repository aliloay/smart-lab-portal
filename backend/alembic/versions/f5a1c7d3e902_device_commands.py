"""device commands

Revision ID: f5a1c7d3e902
Revises: e2b9f4a6c813
Create Date: 2026-10-02 23:30:00.000000

device_commands: requests from the portal that a door controller fetches
and carries out itself (first use: fingerprint enrollment from Users &
roles). The controller polls for them and stays the final authority.

Additive only.
"""
from alembic import op
import sqlalchemy as sa


revision = 'f5a1c7d3e902'
down_revision = 'e2b9f4a6c813'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'device_commands',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('device_id', sa.Integer(), sa.ForeignKey('devices.id'), nullable=False),
        sa.Column('command', sa.String(length=32), nullable=False),
        sa.Column('args', sa.JSON(), nullable=True),
        sa.Column('status', sa.String(length=16), nullable=False),
        sa.Column('step', sa.String(length=32), nullable=True),
        sa.Column('message', sa.String(length=255), nullable=True),
        sa.Column('target_user_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=True),
        sa.Column('requested_by_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('sent_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index('ix_device_commands_device_id', 'device_commands', ['device_id'])
    op.create_index('ix_device_commands_status', 'device_commands', ['status'])
    op.create_index('ix_device_commands_created_at', 'device_commands', ['created_at'])


def downgrade() -> None:
    op.drop_index('ix_device_commands_created_at', table_name='device_commands')
    op.drop_index('ix_device_commands_status', table_name='device_commands')
    op.drop_index('ix_device_commands_device_id', table_name='device_commands')
    op.drop_table('device_commands')
