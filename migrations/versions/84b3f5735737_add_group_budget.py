"""add group budget

Revision ID: 84b3f5735737
Revises: 73d1607941b8
Create Date: 2026-10-29 08:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '84b3f5735737'
down_revision = '73d1607941b8'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('groups', sa.Column('budget_cents', sa.Integer(), nullable=True))
    op.add_column(
        'groups',
        sa.Column(
            'budget_currency', sa.String(length=3), server_default='USD', nullable=False
        ),
    )


def downgrade():
    op.drop_column('groups', 'budget_currency')
    op.drop_column('groups', 'budget_cents')
