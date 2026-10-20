"""Usernames (2026-10-20): sign in with e-mail or username (firstname.lastname).

Additive only: one nullable column and a unique index. Existing accounts keep NULL until an
administrator gives them a username; no row is changed. Downgrade removes both.
"""
import sqlalchemy as sa
from alembic import op

revision = "e6c2a8f4b170"
down_revision = "b7c3e1f9a204"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("users", sa.Column("username", sa.String(64), nullable=True))
    op.create_index("ix_users_username", "users", ["username"], unique=True)


def downgrade():
    op.drop_index("ix_users_username", "users")
    op.drop_column("users", "username")
