"""convert_cents_to_dollars

Revision ID: a9b8c7d6e5f4
Revises: 
Create Date: 2026-07-14 10:37:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'a9b8c7d6e5f4'
down_revision = '87cf9f3319ea'
branch_labels = None
depends_on = None

def upgrade() -> None:
    # 1. Add new Numeric columns
    op.add_column('payments', sa.Column('amount', sa.Numeric(precision=10, scale=2), nullable=True))
    op.add_column('transfers', sa.Column('amount', sa.Numeric(precision=10, scale=2), nullable=True))
    op.add_column('transfers', sa.Column('amount_reversed', sa.Numeric(precision=10, scale=2), nullable=True))
    op.add_column('prices', sa.Column('unit_amount', sa.Numeric(precision=10, scale=2), nullable=True))
    op.add_column('connected_accounts', sa.Column('balance', sa.Numeric(precision=10, scale=2), nullable=True))

    # 2. Migrate data
    op.execute("UPDATE payments SET amount = amount_cents / 100.0")
    op.execute("UPDATE transfers SET amount = amount_cents / 100.0")
    op.execute("UPDATE transfers SET amount_reversed = amount_reversed_cents / 100.0")
    op.execute("UPDATE prices SET unit_amount = unit_amount_cents / 100.0")
    op.execute("UPDATE connected_accounts SET balance = balance_cents / 100.0")

    # 3. Alter columns to be non-nullable where applicable
    op.alter_column('payments', 'amount', nullable=False)
    op.alter_column('transfers', 'amount', nullable=False)
    op.alter_column('prices', 'unit_amount', nullable=False)
    op.alter_column('connected_accounts', 'balance', nullable=False, server_default=sa.text('0.0'))

    # 4. Drop old cents columns
    op.drop_column('payments', 'amount_cents')
    op.drop_column('transfers', 'amount_cents')
    op.drop_column('transfers', 'amount_reversed_cents')
    op.drop_column('prices', 'unit_amount_cents')
    op.drop_column('connected_accounts', 'balance_cents')

def downgrade() -> None:
    # 1. Add back old Integer cents columns
    op.add_column('payments', sa.Column('amount_cents', sa.Integer(), nullable=True))
    op.add_column('transfers', sa.Column('amount_cents', sa.Integer(), nullable=True))
    op.add_column('transfers', sa.Column('amount_reversed_cents', sa.Integer(), nullable=True))
    op.add_column('prices', sa.Column('unit_amount_cents', sa.Integer(), nullable=True))
    op.add_column('connected_accounts', sa.Column('balance_cents', sa.Integer(), nullable=True))

    # 2. Migrate data back
    op.execute("UPDATE payments SET amount_cents = ROUND(amount * 100)")
    op.execute("UPDATE transfers SET amount_cents = ROUND(amount * 100)")
    op.execute("UPDATE transfers SET amount_reversed_cents = ROUND(amount_reversed * 100)")
    op.execute("UPDATE prices SET unit_amount_cents = ROUND(unit_amount * 100)")
    op.execute("UPDATE connected_accounts SET balance_cents = ROUND(balance * 100)")

    # 3. Alter columns to be non-nullable
    op.alter_column('payments', 'amount_cents', nullable=False)
    op.alter_column('transfers', 'amount_cents', nullable=False)
    op.alter_column('prices', 'unit_amount_cents', nullable=False)
    op.alter_column('connected_accounts', 'balance_cents', nullable=False, server_default=sa.text('0'))

    # 4. Drop new Numeric columns
    op.drop_column('payments', 'amount')
    op.drop_column('transfers', 'amount')
    op.drop_column('transfers', 'amount_reversed')
    op.drop_column('prices', 'unit_amount')
    op.drop_column('connected_accounts', 'balance')
