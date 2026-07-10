"""add_stripe_checkout_session_id_to_payments

Revision ID: abdb6d419804
Revises: 2df84e084542
Create Date: 2026-07-10 15:54:01.441817

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'abdb6d419804'
down_revision: Union[str, Sequence[str], None] = '2df84e084542'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Add stripe_checkout_session_id column to payments table
    op.add_column('payments', sa.Column('stripe_checkout_session_id', sa.String(), nullable=True))
    op.create_index(op.f('ix_payments_stripe_checkout_session_id'), 'payments', ['stripe_checkout_session_id'], unique=True)


def downgrade() -> None:
    """Downgrade schema."""
    # Remove stripe_checkout_session_id column from payments table
    op.drop_index(op.f('ix_payments_stripe_checkout_session_id'), table_name='payments')
    op.drop_column('payments', 'stripe_checkout_session_id')
