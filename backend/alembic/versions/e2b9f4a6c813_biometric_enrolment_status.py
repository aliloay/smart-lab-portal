"""biometric enrolment status

Revision ID: e2b9f4a6c813
Revises: d7a4c2e9f1b3
Create Date: 2026-09-26 21:00:00.000000

users.fingerprint_enrolled_at / users.face_enrolled_at: when the person's
fingerprint (reported by the door controller or confirmed by staff) and face
(seen on the face server or confirmed by staff) were enrolled under their
auth subject. NULL = not enrolled yet, which is what the "finish your lab
access setup" reminder is built on. The biometric itself is never stored
here - only the fact and time of enrolment.

Additive only.
"""
from alembic import op
import sqlalchemy as sa


revision = 'e2b9f4a6c813'
down_revision = 'd7a4c2e9f1b3'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('users', sa.Column('fingerprint_enrolled_at',
                                     sa.DateTime(timezone=True), nullable=True))
    op.add_column('users', sa.Column('face_enrolled_at',
                                     sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column('users', 'face_enrolled_at')
    op.drop_column('users', 'fingerprint_enrolled_at')
