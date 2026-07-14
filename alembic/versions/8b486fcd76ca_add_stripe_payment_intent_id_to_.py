"""add_stripe_payment_intent_id_to_subscriptions

Revision ID: 8b486fcd76ca
Revises: a9b8c7d6e5f4
Create Date: 2026-07-14 16:21:20.918199

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '8b486fcd76ca'
down_revision: Union[str, Sequence[str], None] = 'a9b8c7d6e5f4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Add stripe_payment_intent_id column to subscriptions table
    op.add_column('subscriptions', sa.Column('stripe_payment_intent_id', sa.String(), nullable=True))
    op.create_index(op.f('ix_subscriptions_stripe_payment_intent_id'), 'subscriptions', ['stripe_payment_intent_id'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    # Remove stripe_payment_intent_id column and its index
    op.drop_index(op.f('ix_subscriptions_stripe_payment_intent_id'), table_name='subscriptions')
    op.drop_column('subscriptions', 'stripe_payment_intent_id')
