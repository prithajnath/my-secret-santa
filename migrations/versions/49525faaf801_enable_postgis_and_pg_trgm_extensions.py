"""enable postgis and pg_trgm extensions

Revision ID: 49525faaf801
Revises: 05d3bcc394b7
Create Date: 2026-10-25 20:12:37.602148

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '49525faaf801'
down_revision = '05d3bcc394b7'
branch_labels = None
depends_on = None


def upgrade():
    # Requires the postgis/postgis image (see docker-compose files)
    op.execute("CREATE EXTENSION IF NOT EXISTS postgis")
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")


def downgrade():
    op.execute("DROP EXTENSION IF EXISTS pg_trgm")
    op.execute("DROP EXTENSION IF EXISTS postgis")
