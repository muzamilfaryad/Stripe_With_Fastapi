"""add_balance_cents_to_connected_accounts

Revision ID: 87cf9f3319ea
Revises: g3c4d5e6f7a8
Create Date: 2026-07-14 14:52:50.411525

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '87cf9f3319ea'
down_revision: Union[str, Sequence[str], None] = 'g3c4d5e6f7a8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Add balance_cents column to connected_accounts table
    op.add_column('connected_accounts', sa.Column('balance_cents', sa.Integer(), nullable=False, server_default='0'))


def downgrade() -> None:
    """Downgrade schema."""
    # Remove balance_cents column from connected_accounts table
    op.drop_column('connected_accounts', 'balance_cents')
