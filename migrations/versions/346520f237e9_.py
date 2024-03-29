"""empty message

Revision ID: 346520f237e9
Revises: b932d1acd222
Create Date: 2021-11-10 07:58:11.166781

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '346520f237e9'
down_revision = 'b932d1acd222'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column('users', sa.Column('created_at', sa.DateTime(), nullable=True))
    op.add_column('users', sa.Column('updated_at', sa.DateTime(), nullable=True))
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_column('users', 'updated_at')
    op.drop_column('users', 'created_at')
    # ### end Alembic commands ###
