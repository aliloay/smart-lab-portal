"""notification source

Revision ID: d7b3f1e9a246
Revises: c4e8a2f7b915
Create Date: 2026-10-06 23:00:00.000000

notifications.source: who raised it - "n8n" (POST /automation/notify) or
"portal". Existing rows stay NULL: which path raised them was never stored,
and it is not guessed. Additive only.
"""
from alembic import op
import sqlalchemy as sa


revision = 'd7b3f1e9a246'
down_revision = 'c4e8a2f7b915'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('notifications', sa.Column('source', sa.String(16), nullable=True))
    op.create_index('ix_notifications_source', 'notifications', ['source'])


def downgrade() -> None:
    op.drop_index('ix_notifications_source', table_name='notifications')
    op.drop_column('notifications', 'source')
