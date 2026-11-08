"""data provenance and experiments

Revision ID: a9d4e7c2b310
Revises: 7b2e4c9a1d05
Create Date: 2026-10-06 19:30:00.000000

Every event, reading, alert, booking, session, ticket and camera event gets
`provenance` (models.PROVENANCES) and an optional `experiment_id`, plus the
`experiments` / `experiment_trials` tables for thesis measurements.

Existing rows: UNKNOWN_PROVENANCE, except what is PROVEN -
  * access events whose event_metadata says recovered=true (written by
    tools/db/recover_device_logs.py) -> RECOVERED_HISTORY;
  * the two tickets whose text is the n8n maintenance-workflow test
    ("Test report for the n8n maintenance workflow.", "Second test report
    for the maintenance workflow.") -> SOFTWARE_TEST.
The classification is written to the audit log. Additive only: nothing is
deleted, no other value changes.
"""
from alembic import op
import sqlalchemy as sa


revision = 'a9d4e7c2b310'
down_revision = '7b2e4c9a1d05'
branch_labels = None
depends_on = None

TABLES = ("access_events", "sensor_readings", "alerts", "bookings", "access_sessions", "issues",
          "security_events")


def upgrade() -> None:
    op.create_table(
        'experiments',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('code', sa.String(32), nullable=False),
        sa.Column('name', sa.String(160), nullable=False),
        sa.Column('subsystem', sa.String(32), nullable=False),
        sa.Column('operator_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=True),
        sa.Column('device_id', sa.Integer(), sa.ForeignKey('devices.id'), nullable=True),
        sa.Column('firmware_version', sa.String(64), nullable=True),
        sa.Column('hardware_configuration', sa.Text(), nullable=False, server_default=''),
        sa.Column('configuration', sa.JSON(), nullable=True),
        sa.Column('environment', sa.Text(), nullable=False, server_default=''),
        sa.Column('network_state', sa.Text(), nullable=False, server_default=''),
        sa.Column('data_mode', sa.String(24), nullable=False, server_default='PHYSICAL_TEST'),
        sa.Column('test_condition', sa.Text(), nullable=False, server_default=''),
        sa.Column('expected_result', sa.Text(), nullable=False, server_default=''),
        sa.Column('actual_result', sa.Text(), nullable=False, server_default=''),
        sa.Column('result', sa.String(16), nullable=True),
        sa.Column('notes', sa.Text(), nullable=False, server_default=''),
        sa.Column('status', sa.String(16), nullable=False, server_default='PLANNED'),
        sa.Column('started_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('ended_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index('ix_experiments_code', 'experiments', ['code'], unique=True)
    op.create_table(
        'experiment_trials',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('experiment_id', sa.Integer(), sa.ForeignKey('experiments.id'), nullable=False),
        sa.Column('repeat_number', sa.Integer(), nullable=False),
        sa.Column('input', sa.Text(), nullable=False, server_default=''),
        sa.Column('expected', sa.Text(), nullable=False, server_default=''),
        sa.Column('actual', sa.Text(), nullable=False, server_default=''),
        sa.Column('measurement', sa.Float(), nullable=True),
        sa.Column('unit', sa.String(24), nullable=True),
        sa.Column('result', sa.String(16), nullable=True),
        sa.Column('notes', sa.Text(), nullable=False, server_default=''),
        sa.Column('recorded_by_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=True),
        sa.Column('recorded_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index('ix_experiment_trials_experiment_id', 'experiment_trials', ['experiment_id'])

    for t in TABLES:
        op.add_column(t, sa.Column('provenance', sa.String(24), nullable=False,
                                   server_default='UNKNOWN_PROVENANCE'))
        op.add_column(t, sa.Column('experiment_id', sa.Integer(), sa.ForeignKey('experiments.id'),
                                   nullable=True))
        op.create_index(f'ix_{t}_provenance', t, ['provenance'])
        op.create_index(f'ix_{t}_experiment_id', t, ['experiment_id'])

    conn = op.get_bind()
    recovered = conn.execute(sa.text(
        "UPDATE access_events SET provenance = 'RECOVERED_HISTORY' "
        "WHERE event_metadata::jsonb ->> 'recovered' = 'true'")).rowcount
    tests = conn.execute(sa.text(
        "UPDATE issues SET provenance = 'SOFTWARE_TEST' WHERE description IN "
        "('Test report for the n8n maintenance workflow.', "
        "'Second test report for the maintenance workflow.') RETURNING id")).fetchall()
    conn.execute(sa.text(
        "INSERT INTO audit_logs (action, entity_type, entity_id, detail, created_at) "
        "VALUES ('DATA_PROVENANCE_CLASSIFIED', 'migration', 'a9d4e7c2b310', CAST(:d AS json), now())"),
        {"d": '{"rule": "existing rows UNKNOWN_PROVENANCE unless proven", '
              f'"access_events_recovered_history": {recovered}, '
              f'"issues_software_test": {sorted(r[0] for r in tests)}, '
              '"evidence": "event_metadata.recovered=true; ticket text = n8n workflow test report"}'})


def downgrade() -> None:
    for t in TABLES:
        op.drop_index(f'ix_{t}_experiment_id', table_name=t)
        op.drop_index(f'ix_{t}_provenance', table_name=t)
        op.drop_column(t, 'experiment_id')
        op.drop_column(t, 'provenance')
    op.drop_index('ix_experiment_trials_experiment_id', table_name='experiment_trials')
    op.drop_table('experiment_trials')
    op.drop_index('ix_experiments_code', table_name='experiments')
    op.drop_table('experiments')
