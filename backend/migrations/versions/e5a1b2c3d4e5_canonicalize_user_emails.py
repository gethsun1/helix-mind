"""canonicalize user email identities

Revision ID: e5a1b2c3d4e5
Revises: d4f0a1b2c3d4
Create Date: 2026-08-24
"""

from alembic import op


revision = "e5a1b2c3d4e5"
down_revision = "d4f0a1b2c3d4"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "UPDATE users SET email = lower(btrim(email)) "
        "WHERE email IS DISTINCT FROM lower(btrim(email))"
    )
    op.execute(
        "CREATE UNIQUE INDEX uq_users_email_canonical "
        "ON users (lower(btrim(email)))"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS uq_users_email_canonical")
