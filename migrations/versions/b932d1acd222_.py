"""empty message

Revision ID: b932d1acd222
Revises: 150015ed75c9
Create Date: 2021-11-06 20:08:12.872730

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "b932d1acd222"
down_revision = "150015ed75c9"
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column(
        "pairs", sa.Column("channel_id", postgresql.UUID(as_uuid=True), nullable=True)
    )
    op.create_unique_constraint(None, "pairs", ["channel_id"])
    op.add_column(
        "messages",
        sa.Column("pair_channel_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_foreign_key(
        None, "messages", "pairs", ["pair_channel_id"], ["channel_id"]
    )
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_constraint(None, "pairs", type_="unique")
    op.drop_column("pairs", "channel_id")
    op.drop_constraint(None, "messages", type_="foreignkey")
    op.drop_column("messages", "pair_channel_id")
    # ### end Alembic commands ###
