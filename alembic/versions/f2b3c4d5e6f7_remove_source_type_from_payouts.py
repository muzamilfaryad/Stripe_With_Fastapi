"""remove_source_type_from_payouts

Revision ID: f2b3c4d5e6f7
Revises: f1a2b3c4d5e6
Create Date: 2026-07-14 14:10:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f2b3c4d5e6f7'
down_revision: Union[str, Sequence[str], None] = 'f1a2b3c4d5e6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """
    Upgrade schema:
    1. Remove source_type column from payouts table
    """
    op.drop_column('payouts', 'source_type')


def downgrade() -> None:
    """
    Downgrade schema:
    1. Add source_type column to payouts table
    """
    op.add_column('payouts', sa.Column('source_type', sa.String(), nullable=True))
