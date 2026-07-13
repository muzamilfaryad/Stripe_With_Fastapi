"""rename_unit_amount_to_unit_amount_cents

Revision ID: 498020b41597
Revises: 7b246ddabdfa
Create Date: 2026-07-13 12:18:29.793486

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '498020b41597'
down_revision: Union[str, Sequence[str], None] = '7b246ddabdfa'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
