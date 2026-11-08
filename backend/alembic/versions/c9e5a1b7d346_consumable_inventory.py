"""consumable inventory

Revision ID: c9e5a1b7d346
Revises: b7c3e9f5a124
Create Date: 2026-10-03 02:00:00.000000

Robotics Lab System 3: inventory_bins (weighing bins with their MEASURED
calibration), inventory_measurements (stable readings) and
inventory_transactions (withdrawals, refills, physical counts).

Additive only.
"""
from alembic import op
import sqlalchemy as sa


revision = 'c9e5a1b7d346'
down_revision = 'b7c3e9f5a124'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table('inventory_bins',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('code', sa.String(length=32), nullable=False),
    sa.Column('lab_id', sa.Integer(), nullable=False),
    sa.Column('device_id', sa.Integer(), nullable=True),
    sa.Column('item_name', sa.String(length=64), nullable=False),
    sa.Column('category', sa.String(length=32), nullable=False),
    sa.Column('tare_g', sa.Float(), nullable=True),
    sa.Column('unit_mass_g', sa.Float(), nullable=True),
    sa.Column('noise_g', sa.Float(), nullable=True),
    sa.Column('calibrated_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('min_change_g', sa.Float(), nullable=True),
    sa.Column('reorder_qty', sa.Integer(), nullable=True),
    sa.Column('last_mass_g', sa.Float(), nullable=True),
    sa.Column('last_measured_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('notes', sa.Text(), nullable=False),
    sa.Column('is_active', sa.Boolean(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['device_id'], ['devices.id'], ),
    sa.ForeignKeyConstraint(['lab_id'], ['labs.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_inventory_bins_code'), 'inventory_bins', ['code'], unique=True)
    op.create_index(op.f('ix_inventory_bins_lab_id'), 'inventory_bins', ['lab_id'], unique=False)
    op.create_table('inventory_measurements',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('bin_id', sa.Integer(), nullable=False),
    sa.Column('mass_g', sa.Float(), nullable=False),
    sa.Column('recorded_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['bin_id'], ['inventory_bins.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_inventory_measurements_bin_id'), 'inventory_measurements', ['bin_id'], unique=False)
    op.create_index(op.f('ix_inventory_measurements_recorded_at'), 'inventory_measurements', ['recorded_at'], unique=False)
    op.create_table('inventory_transactions',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('bin_id', sa.Integer(), nullable=False),
    sa.Column('kind', sa.String(length=16), nullable=False),
    sa.Column('delta_mass_g', sa.Float(), nullable=True),
    sa.Column('delta_qty_est', sa.Integer(), nullable=True),
    sa.Column('qty_est_after', sa.Integer(), nullable=True),
    sa.Column('actual_count', sa.Integer(), nullable=True),
    sa.Column('user_id', sa.Integer(), nullable=True),
    sa.Column('booking_id', sa.Integer(), nullable=True),
    sa.Column('attribution', sa.String(length=24), nullable=False),
    sa.Column('recorded_by_id', sa.Integer(), nullable=True),
    sa.Column('note', sa.String(length=255), nullable=False),
    sa.Column('recorded_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['bin_id'], ['inventory_bins.id'], ),
    sa.ForeignKeyConstraint(['booking_id'], ['bookings.id'], ),
    sa.ForeignKeyConstraint(['recorded_by_id'], ['users.id'], ),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_inventory_transactions_bin_id'), 'inventory_transactions', ['bin_id'], unique=False)
    op.create_index(op.f('ix_inventory_transactions_recorded_at'), 'inventory_transactions', ['recorded_at'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_inventory_transactions_recorded_at'), table_name='inventory_transactions')
    op.drop_index(op.f('ix_inventory_transactions_bin_id'), table_name='inventory_transactions')
    op.drop_table('inventory_transactions')
    op.drop_index(op.f('ix_inventory_measurements_recorded_at'), table_name='inventory_measurements')
    op.drop_index(op.f('ix_inventory_measurements_bin_id'), table_name='inventory_measurements')
    op.drop_table('inventory_measurements')
    op.drop_index(op.f('ix_inventory_bins_lab_id'), table_name='inventory_bins')
    op.drop_index(op.f('ix_inventory_bins_code'), table_name='inventory_bins')
    op.drop_table('inventory_bins')
