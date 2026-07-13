"""add connected_accounts and transfers

Revision ID: a1b2c3d4e5f6
Revises: 498020b41597
Create Date: 2026-07-13 14:45:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, Sequence[str], None] = '498020b41597'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create connected_accounts and transfers tables."""
    # -----------------------------------------------------------------------
    # connected_accounts
    # -----------------------------------------------------------------------
    op.create_table(
        'connected_accounts',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('stripe_account_id', sa.String(), nullable=False),
        sa.Column('email', sa.String(), nullable=True),
        sa.Column('display_name', sa.String(), nullable=True),
        sa.Column('account_type', sa.String(), nullable=True),
        sa.Column('charges_enabled', sa.Boolean(), nullable=True),
        sa.Column('payouts_enabled', sa.Boolean(), nullable=True),
        sa.Column('details_submitted', sa.Boolean(), nullable=True),
        sa.Column('status', sa.String(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_connected_accounts_id'), 'connected_accounts', ['id'], unique=False)
    op.create_index(op.f('ix_connected_accounts_stripe_account_id'), 'connected_accounts', ['stripe_account_id'], unique=True)

    # -----------------------------------------------------------------------
    # transfers
    # -----------------------------------------------------------------------
    op.create_table(
        'transfers',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('stripe_transfer_id', sa.String(), nullable=True),
        sa.Column('connected_account_id', sa.Integer(), nullable=False),
        sa.Column('stripe_charge_id', sa.String(), nullable=True),
        sa.Column('transfer_group', sa.String(), nullable=True),
        sa.Column('amount_cents', sa.Integer(), nullable=False),
        sa.Column('currency', sa.String(), nullable=False),
        sa.Column('status', sa.String(), nullable=False),
        sa.Column('description', sa.String(), nullable=True),
        sa.Column('failure_message', sa.Text(), nullable=True),
        sa.Column('reversed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('amount_reversed_cents', sa.Integer(), nullable=True),
        sa.Column('idempotency_key', sa.String(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.ForeignKeyConstraint(['connected_account_id'], ['connected_accounts.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_transfers_id'), 'transfers', ['id'], unique=False)
    op.create_index(op.f('ix_transfers_stripe_transfer_id'), 'transfers', ['stripe_transfer_id'], unique=True)
    op.create_index(op.f('ix_transfers_stripe_charge_id'), 'transfers', ['stripe_charge_id'], unique=False)
    op.create_index(op.f('ix_transfers_transfer_group'), 'transfers', ['transfer_group'], unique=False)
    op.create_index(op.f('ix_transfers_idempotency_key'), 'transfers', ['idempotency_key'], unique=True)


def downgrade() -> None:
    """Drop transfers and connected_accounts tables."""
    op.drop_index(op.f('ix_transfers_idempotency_key'), table_name='transfers')
    op.drop_index(op.f('ix_transfers_transfer_group'), table_name='transfers')
    op.drop_index(op.f('ix_transfers_stripe_charge_id'), table_name='transfers')
    op.drop_index(op.f('ix_transfers_stripe_transfer_id'), table_name='transfers')
    op.drop_index(op.f('ix_transfers_id'), table_name='transfers')
    op.drop_table('transfers')

    op.drop_index(op.f('ix_connected_accounts_stripe_account_id'), table_name='connected_accounts')
    op.drop_index(op.f('ix_connected_accounts_id'), table_name='connected_accounts')
    op.drop_table('connected_accounts')
