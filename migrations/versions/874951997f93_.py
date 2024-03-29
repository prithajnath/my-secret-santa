"""empty message

Revision ID: 874951997f93
Revises: 6d85567e6a5e
Create Date: 2020-11-29 10:28:26.195478

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "874951997f93"
down_revision = "6d85567e6a5e"
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_table(
        "email_invites",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("timestamp", sa.Date(), nullable=True),
        sa.Column("invited_email", sa.String(length=120), nullable=False),
        sa.Column("group_id", sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(
            ["group_id"],
            ["groups.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("invited_email"),
    )
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_table("email_invites")
    # ### end Alembic commands ###
