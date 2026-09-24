"""issue reporting, notifications, honest occupancy sessions

Revision ID: b8d41f7a2c90
Revises: 392460921eaf
Create Date: 2026-09-25 03:10:00.000000

Adds the maintenance workflow (issues, photos, comments, history), in-portal
notifications, per-device component state, and the door-cycle columns on
access_sessions.

Data fix: until now a session was ended by DOOR_CLOSED, which fires seconds
after entry when the door swings shut behind the person. Those ended_at
values are door-close times, not exits. They are moved to door_closed_at and
the sessions re-opened, so the application can close them properly (booking
end, or the no-exit cut-off) and never present a door closing as an exit.
"""
from alembic import op
import sqlalchemy as sa


revision = 'b8d41f7a2c90'
down_revision = '392460921eaf'
branch_labels = None
depends_on = None


def _enum(*values, name):
    return sa.Enum(*values, name=name, native_enum=False, length=48)


ISSUE_STATUS = ('OPEN', 'ACKNOWLEDGED', 'IN_PROGRESS', 'WAITING_FOR_PARTS',
                'RESOLVED', 'CLOSED', 'REJECTED')
AUTH_METHOD = ('RFID', 'QR', 'FINGERPRINT', 'FACE', 'PORTAL')
END_REASON = ('EXIT_RECORDED', 'BOOKING_ENDED', 'DOOR_NOT_OPENED',
              'SUPERSEDED', 'NO_EXIT_TIMEOUT')


def upgrade() -> None:
    # --- devices ---------------------------------------------------------------
    op.add_column('devices', sa.Column('component_state', sa.JSON(), nullable=True))

    # --- access_sessions -------------------------------------------------------
    op.add_column('access_sessions', sa.Column(
        'second_factor', _enum(*AUTH_METHOD, name='auth_method_enum4'),
        nullable=True))
    op.add_column('access_sessions', sa.Column(
        'door_opened_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('access_sessions', sa.Column(
        'door_closed_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('access_sessions', sa.Column(
        'end_reason', _enum(*END_REASON, name='session_end_reason_enum'),
        nullable=True))
    op.execute("""
        UPDATE access_sessions
           SET door_closed_at = ended_at,
               ended_at = NULL
         WHERE ended_at IS NOT NULL AND end_reason IS NULL
    """)

    # --- issues ----------------------------------------------------------------
    op.create_table(
        'issues',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('ticket_number', sa.String(length=32), nullable=True),
        sa.Column('reporter_id', sa.Integer(), nullable=False),
        sa.Column('lab_id', sa.Integer(), nullable=False),
        sa.Column('asset_id', sa.Integer(), nullable=True),
        sa.Column('device_id', sa.Integer(), nullable=True),
        sa.Column('access_event_id', sa.Integer(), nullable=True),
        sa.Column('category', _enum('DAMAGED', 'MISSING', 'MALFUNCTION',
                                    'MAINTENANCE', 'SAFETY', 'SOFTWARE',
                                    'NETWORK', 'ACCESS_CONTROL', 'OTHER',
                                    name='issue_category_enum'), nullable=False),
        sa.Column('severity', _enum('LOW', 'MEDIUM', 'HIGH', 'CRITICAL',
                                    name='issue_severity_enum'), nullable=False),
        sa.Column('status', _enum(*ISSUE_STATUS, name='issue_status_enum'),
                  nullable=False),
        sa.Column('title', sa.String(length=140), nullable=False),
        sa.Column('description', sa.Text(), nullable=False),
        sa.Column('additional_comments', sa.Text(), nullable=False),
        sa.Column('assigned_to_id', sa.Integer(), nullable=True),
        sa.Column('resolution_notes', sa.Text(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('acknowledged_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('resolved_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('closed_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['access_event_id'], ['access_events.id'],
                                ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['asset_id'], ['assets.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['assigned_to_id'], ['users.id']),
        sa.ForeignKeyConstraint(['device_id'], ['devices.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['lab_id'], ['labs.id']),
        sa.ForeignKeyConstraint(['reporter_id'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_issues_ticket_number', 'issues', ['ticket_number'],
                    unique=True)
    for col in ('reporter_id', 'lab_id', 'asset_id', 'device_id', 'category',
                'severity', 'status', 'assigned_to_id', 'created_at'):
        op.create_index(f'ix_issues_{col}', 'issues', [col], unique=False)
    op.create_index('ix_issue_status_severity', 'issues', ['status', 'severity'])
    op.create_index('ix_issue_lab_status', 'issues', ['lab_id', 'status'])

    op.create_table(
        'issue_photos',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('issue_id', sa.Integer(), nullable=False),
        sa.Column('uploaded_by_id', sa.Integer(), nullable=False),
        sa.Column('stage', _enum('REPORT', 'BEFORE', 'AFTER',
                                 name='issue_photo_stage_enum'), nullable=False),
        sa.Column('storage_key', sa.String(length=255), nullable=False),
        sa.Column('thumb_key', sa.String(length=255), nullable=False),
        sa.Column('original_filename', sa.String(length=255), nullable=False),
        sa.Column('content_type', sa.String(length=32), nullable=False),
        sa.Column('size_bytes', sa.Integer(), nullable=False),
        sa.Column('width', sa.Integer(), nullable=False),
        sa.Column('height', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['issue_id'], ['issues.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['uploaded_by_id'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('storage_key'),
        sa.UniqueConstraint('thumb_key'),
    )
    op.create_index('ix_issue_photos_issue_id', 'issue_photos', ['issue_id'])

    op.create_table(
        'issue_comments',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('issue_id', sa.Integer(), nullable=False),
        sa.Column('author_id', sa.Integer(), nullable=False),
        sa.Column('body', sa.Text(), nullable=False),
        sa.Column('is_internal', sa.Boolean(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['author_id'], ['users.id']),
        sa.ForeignKeyConstraint(['issue_id'], ['issues.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_issue_comments_issue_id', 'issue_comments', ['issue_id'])

    op.create_table(
        'issue_history',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('issue_id', sa.Integer(), nullable=False),
        sa.Column('actor_id', sa.Integer(), nullable=True),
        sa.Column('event_type', _enum(
            'ISSUE_CREATED', 'ISSUE_ACKNOWLEDGED', 'ISSUE_ASSIGNED',
            'ISSUE_STATUS_CHANGED', 'ISSUE_SEVERITY_CHANGED', 'ISSUE_UPDATED',
            'ISSUE_COMMENT_ADDED', 'ISSUE_PHOTO_ADDED', 'ISSUE_RESOLVED',
            'ISSUE_CLOSED', 'ISSUE_REOPENED', name='issue_event_type_enum'),
            nullable=False),
        sa.Column('old_status', _enum(*ISSUE_STATUS, name='issue_status_enum2'),
                  nullable=True),
        sa.Column('new_status', _enum(*ISSUE_STATUS, name='issue_status_enum3'),
                  nullable=True),
        sa.Column('message', sa.String(length=500), nullable=False),
        sa.Column('detail', sa.JSON(), nullable=True),
        sa.Column('is_internal', sa.Boolean(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['actor_id'], ['users.id']),
        sa.ForeignKeyConstraint(['issue_id'], ['issues.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_issue_history_issue_id', 'issue_history', ['issue_id'])
    op.create_index('ix_issue_history_event_type', 'issue_history', ['event_type'])
    op.create_index('ix_issue_history_created_at', 'issue_history', ['created_at'])

    # --- notifications -----------------------------------------------------------
    op.create_table(
        'notifications',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('kind', sa.String(length=48), nullable=False),
        sa.Column('severity', sa.String(length=16), nullable=False),
        sa.Column('title', sa.String(length=160), nullable=False),
        sa.Column('body', sa.String(length=500), nullable=False),
        sa.Column('link', sa.String(length=160), nullable=True),
        sa.Column('issue_id', sa.Integer(), nullable=True),
        sa.Column('booking_id', sa.Integer(), nullable=True),
        sa.Column('is_read', sa.Boolean(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('read_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['booking_id'], ['bookings.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['issue_id'], ['issues.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    for col in ('user_id', 'kind', 'issue_id', 'booking_id', 'created_at'):
        op.create_index(f'ix_notifications_{col}', 'notifications', [col])
    op.create_index('ix_notification_user_unread', 'notifications',
                    ['user_id', 'is_read', 'created_at'])


def downgrade() -> None:
    op.drop_table('notifications')
    op.drop_table('issue_history')
    op.drop_table('issue_comments')
    op.drop_table('issue_photos')
    op.drop_table('issues')
    # Door-close times go back to where the old model kept them.
    op.execute("""
        UPDATE access_sessions
           SET ended_at = COALESCE(ended_at, door_closed_at)
    """)
    op.drop_column('access_sessions', 'end_reason')
    op.drop_column('access_sessions', 'door_closed_at')
    op.drop_column('access_sessions', 'door_opened_at')
    op.drop_column('access_sessions', 'second_factor')
    op.drop_column('devices', 'component_state')
