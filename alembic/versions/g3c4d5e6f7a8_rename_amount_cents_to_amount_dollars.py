"""rename_amount_cents_to_amount_dollars

Revision ID: g3c4d5e6f7a8
Revises: f2b3c4d5e6f7
Create Date: 2026-07-14 14:40:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'g3c4d5e6f7a8'
down_revision: Union[str, Sequence[str], None] = 'f2b3c4d5e6f7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """
    Upgrade schema:
    1. Add new 'amount' column (Numeric 12,2) — stores dollars
    2. Copy existing cents values converted to dollars
    3. Drop old 'amount_cents' column
    """
    # Step 1: Add new column (nullable first so existing rows don't fail)
    op.add_column('payouts', sa.Column('amount', sa.Numeric(precision=12, scale=2), nullable=True))

    # Step 2: Migrate existing data — divide cents by 100 to get dollars
    op.execute("UPDATE payouts SET amount = amount_cents / 100.0")

    # Step 3: Set NOT NULL now that data is populated
    op.alter_column('payouts', 'amount', nullable=False)

    # Step 4: Drop old column
    op.drop_column('payouts', 'amount_cents')


def downgrade() -> None:
    """
    Downgrade schema:
    1. Add back 'amount_cents' column (Integer)
    2. Copy dollar values converted back to cents
    3. Drop 'amount' column
    """
    # Step 1: Add amount_cents column
    op.add_column('payouts', sa.Column('amount_cents', sa.Integer(), nullable=True))

    # Step 2: Convert dollars back to cents
    op.execute("UPDATE payouts SET amount_cents = ROUND(amount * 100)")

    # Step 3: Set NOT NULL
    op.alter_column('payouts', 'amount_cents', nullable=False)

    # Step 4: Drop amount column
    op.drop_column('payouts', 'amount')
