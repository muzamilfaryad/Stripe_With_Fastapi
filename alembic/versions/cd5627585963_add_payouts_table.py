"""add_payouts_table

Revision ID: cd5627585963
Revises: a1b2c3d4e5f6
Create Date: 2026-07-14 12:11:50.678082

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'cd5627585963'
down_revision: Union[str, Sequence[str], None] = 'a1b2c3d4e5f6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema - Create payouts table."""
    op.create_table(
        'payouts',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('stripe_payout_id', sa.String(), nullable=True),
        sa.Column('amount_cents', sa.Integer(), nullable=False),
        sa.Column('currency', sa.String(), nullable=False),
        sa.Column('method', sa.String(), nullable=False),
        sa.Column('type', sa.String(), nullable=False),
        sa.Column('status', sa.String(), nullable=False),
        sa.Column('destination_id', sa.String(), nullable=True),
        sa.Column('arrival_date', sa.DateTime(timezone=True), nullable=True),
        sa.Column('automatic', sa.Boolean(), nullable=False),
        sa.Column('description', sa.String(), nullable=True),
        sa.Column('statement_descriptor', sa.String(), nullable=True),
        sa.Column('failure_code', sa.String(), nullable=True),
        sa.Column('failure_message', sa.Text(), nullable=True),
        sa.Column('balance_transaction_id', sa.String(), nullable=True),
        sa.Column('idempotency_key', sa.String(), nullable=True),
        sa.Column('source_type', sa.String(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Create indexes for optimal query performance
    op.create_index(op.f('ix_payouts_id'), 'payouts', ['id'], unique=False)
    op.create_index(op.f('ix_payouts_stripe_payout_id'), 'payouts', ['stripe_payout_id'], unique=True)
    op.create_index(op.f('ix_payouts_idempotency_key'), 'payouts', ['idempotency_key'], unique=True)
    op.create_index(op.f('ix_payouts_status'), 'payouts', ['status'], unique=False)
    op.create_index(op.f('ix_payouts_method'), 'payouts', ['method'], unique=False)


def downgrade() -> None:
    """Downgrade schema - Drop payouts table."""
    op.drop_index(op.f('ix_payouts_method'), table_name='payouts')
    op.drop_index(op.f('ix_payouts_status'), table_name='payouts')
    op.drop_index(op.f('ix_payouts_idempotency_key'), table_name='payouts')
    op.drop_index(op.f('ix_payouts_stripe_payout_id'), table_name='payouts')
    op.drop_index(op.f('ix_payouts_id'), table_name='payouts')
    op.drop_table('payouts')
