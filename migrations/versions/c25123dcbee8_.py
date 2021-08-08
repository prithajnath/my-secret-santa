"""empty message

Revision ID: c25123dcbee8
Revises: 0da06f77d661
Create Date: 2020-12-05 14:07:44.775737

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "c25123dcbee8"
down_revision = "0da06f77d661"
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_constraint(
        "email_invites_invited_email_key", "email_invites", type_="unique"
    )
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_unique_constraint(
        "email_invites_invited_email_key", "email_invites", ["invited_email"]
    )
    # ### end Alembic commands ###
