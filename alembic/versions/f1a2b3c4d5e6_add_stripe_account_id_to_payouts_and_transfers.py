"""add_stripe_account_id_to_payouts_and_transfers

Revision ID: f1a2b3c4d5e6
Revises: cd5627585963
Create Date: 2026-07-14 14:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f1a2b3c4d5e6'
down_revision: Union[str, Sequence[str], None] = 'cd5627585963'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """
    Upgrade schema:
    1. Add stripe_account_id column to payouts table
    2. Add stripe_account_id column to transfers table
    3. Make connected_account_id nullable in transfers table
    """
    # Add stripe_account_id to payouts table
    op.add_column('payouts', sa.Column('stripe_account_id', sa.String(), nullable=True))
    op.create_index(op.f('ix_payouts_stripe_account_id'), 'payouts', ['stripe_account_id'], unique=False)
    
    # Add stripe_account_id to transfers table
    op.add_column('transfers', sa.Column('stripe_account_id', sa.String(), nullable=True))
    op.create_index(op.f('ix_transfers_stripe_account_id'), 'transfers', ['stripe_account_id'], unique=False)
    
    # Make connected_account_id nullable in transfers table (backward compatibility)
    op.alter_column('transfers', 'connected_account_id',
                    existing_type=sa.Integer(),
                    nullable=True)


def downgrade() -> None:
    """
    Downgrade schema:
    1. Remove stripe_account_id column from transfers table
    2. Remove stripe_account_id column from payouts table
    3. Make connected_account_id NOT nullable in transfers table
    """
    # Revert connected_account_id to NOT nullable
    op.alter_column('transfers', 'connected_account_id',
                    existing_type=sa.Integer(),
                    nullable=False)
    
    # Remove stripe_account_id from transfers table
    op.drop_index(op.f('ix_transfers_stripe_account_id'), table_name='transfers')
    op.drop_column('transfers', 'stripe_account_id')
    
    # Remove stripe_account_id from payouts table
    op.drop_index(op.f('ix_payouts_stripe_account_id'), table_name='payouts')
    op.drop_column('payouts', 'stripe_account_id')
