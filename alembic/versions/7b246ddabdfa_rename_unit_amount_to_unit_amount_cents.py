"""rename_unit_amount_to_unit_amount_cents

Revision ID: 7b246ddabdfa
Revises: abdb6d419804
Create Date: 2026-07-10 16:13:13.559818

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '7b246ddabdfa'
down_revision: Union[str, Sequence[str], None] = 'abdb6d419804'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Rename unit_amount to unit_amount_cents for clarity
    op.alter_column('prices', 'unit_amount', new_column_name='unit_amount_cents')


def downgrade() -> None:
    """Downgrade schema."""
    # Revert the column name back to unit_amount
    op.alter_column('prices', 'unit_amount_cents', new_column_name='unit_amount')
