"""lock passwordless google accounts

Accounts created by Google sign-in were given a guessable password: "test" (the old
/google_oauth route, via the User model's default) or "" (the API callback). Replace
those with a random password nobody knows. Accounts whose owner has since set a real
password are left alone.

Revision ID: 575e522c5a88
Revises: 8037750ee7a5
Create Date: 2026-10-26 02:12:48.421052

"""
import secrets

from alembic import op
import sqlalchemy as sa
from passlib.hash import pbkdf2_sha256


# revision identifiers, used by Alembic.
revision = '575e522c5a88'
down_revision = '8037750ee7a5'
branch_labels = None
depends_on = None

GUESSABLE_PASSWORDS = ("test", "")


def _is_guessable(password_hash):
    for password in GUESSABLE_PASSWORDS:
        try:
            if pbkdf2_sha256.verify(password, password_hash):
                return True
        except ValueError:
            # Not a pbkdf2 hash, so neither password can match it
            return False
    return False


def upgrade():
    connection = op.get_bind()
    google_users = connection.execute(
        sa.text(
            "SELECT DISTINCT u.id, u.password FROM users u "
            "JOIN user_oauth_profiles p ON p.user_id = u.id"
        )
    ).fetchall()

    locked = 0
    for user_id, password_hash in google_users:
        if password_hash and _is_guessable(password_hash):
            connection.execute(
                sa.text("UPDATE users SET password = :password WHERE id = :id"),
                {
                    "password": pbkdf2_sha256.hash(secrets.token_urlsafe(32)),
                    "id": user_id,
                },
            )
            locked += 1

    print(f"Locked {locked} of {len(google_users)} Google sign-in accounts")


def downgrade():
    # The old passwords were the security hole; there's nothing to restore
    pass
