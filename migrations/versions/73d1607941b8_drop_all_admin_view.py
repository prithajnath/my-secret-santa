"""drop all_admin_view

Nothing reads this materialized view any more: group admin checks read
groups_and_users directly, and only the retired server-rendered /groups page
refreshed it.

Revision ID: 73d1607941b8
Revises: 575e522c5a88
Create Date: 2026-10-26 02:51:12.000000

"""
from alembic import op


# revision identifiers, used by Alembic.
revision = '73d1607941b8'
down_revision = '575e522c5a88'
branch_labels = None
depends_on = None


def upgrade():
    op.execute("DROP MATERIALIZED VIEW IF EXISTS all_admin_view")


def downgrade():
    op.execute(
        """
        CREATE MATERIALIZED VIEW all_admin_view AS (
            WITH admins AS (
                SELECT user_id, group_id
                FROM groups_and_users
                WHERE group_admin = 't'
            )
            SELECT
                gen_random_uuid() AS id,
                user_id,
                username,
                group_id,
                groups.name AS groupname
            FROM users
            INNER JOIN admins ON users.id = admins.user_id
            INNER JOIN groups ON groups.id = admins.group_id
        )
        """
    )
    op.execute("CREATE UNIQUE INDEX ON all_admin_view (id)")
