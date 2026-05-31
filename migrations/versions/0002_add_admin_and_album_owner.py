"""Add is_admin to users and user_id owner FK to albums.

Revision ID: 0002
Revises: 0001
Create Date: 2025-01-02 00:00:00.000000
"""
from alembic import op
import sqlalchemy as sa

revision = '0002'
down_revision = '0001'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add is_admin flag to users (default False)
    op.add_column(
        'users',
        sa.Column('is_admin', sa.Boolean(), nullable=False, server_default='false'),
    )

    # Add owner FK to albums (nullable so legacy rows keep working)
    op.add_column(
        'albums',
        sa.Column('user_id', sa.String(36), nullable=True),
    )
    op.create_foreign_key(
        'fk_albums_user_id',
        'albums', 'users',
        ['user_id'], ['id'],
        ondelete='SET NULL',
    )


def downgrade() -> None:
    op.drop_constraint('fk_albums_user_id', 'albums', type_='foreignkey')
    op.drop_column('albums', 'user_id')
    op.drop_column('users', 'is_admin')
