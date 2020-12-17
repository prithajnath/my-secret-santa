"""empty message

Revision ID: 0da06f77d661
Revises: 874951997f93
Create Date: 2020-12-05 04:51:54.818201

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '0da06f77d661'
down_revision = '874951997f93'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_unique_constraint(None, 'users', ['username'])
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_constraint(None, 'users', type_='unique')
    # ### end Alembic commands ###