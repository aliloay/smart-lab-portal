"""face submissions

Revision ID: a6b2d8e4f013
Revises: f5a1c7d3e902
Create Date: 2026-10-03 00:30:00.000000

face_submissions: face photos a person sends from the portal for door
enrollment. Used only after staff approve; the images are deleted from the
portal on approval or rejection - only this record stays.

Additive only.
"""
from alembic import op
import sqlalchemy as sa


revision = 'a6b2d8e4f013'
down_revision = 'f5a1c7d3e902'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'face_submissions',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('status', sa.String(length=16), nullable=False),
        sa.Column('photo_keys', sa.JSON(), nullable=True),
        sa.Column('thumb_keys', sa.JSON(), nullable=True),
        sa.Column('photo_count', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('reviewed_by_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=True),
        sa.Column('reviewed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('reason', sa.String(length=255), nullable=True),
        sa.Column('samples_saved', sa.Integer(), nullable=True),
    )
    op.create_index('ix_face_submissions_user_id', 'face_submissions', ['user_id'])
    op.create_index('ix_face_submissions_status', 'face_submissions', ['status'])
    op.create_index('ix_face_submissions_created_at', 'face_submissions', ['created_at'])


def downgrade() -> None:
    op.drop_index('ix_face_submissions_created_at', table_name='face_submissions')
    op.drop_index('ix_face_submissions_status', table_name='face_submissions')
    op.drop_index('ix_face_submissions_user_id', table_name='face_submissions')
    op.drop_table('face_submissions')
