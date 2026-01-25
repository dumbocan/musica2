"""add_image_path_id_to_artist_album

Revision ID: add_image_path_id
Revises:
Create Date: 2025-01-25

"""
from typing import Union
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by alembic.
revision: str = 'add_image_path_id'
down_revision: Union[str, None] = 'create_stored_image_path'
branch_labels: Union[str, None] = None
depends_on: Union[str, None] = None


def upgrade() -> None:
    # Add image_path_id column to artist table
    op.add_column('artist', sa.Column('image_path_id', sa.Integer(), nullable=True))
    op.create_foreign_key(
        'fk_artist_image_path_id',
        'artist', 'storedimagepath',
        ['image_path_id'], ['id'],
        ondelete='SET NULL'
    )
    op.create_index('ix_artist_image_path_id', 'artist', ['image_path_id'])

    # Add image_path_id column to album table
    op.add_column('album', sa.Column('image_path_id', sa.Integer(), nullable=True))
    op.create_foreign_key(
        'fk_album_image_path_id',
        'album', 'storedimagepath',
        ['image_path_id'], ['id'],
        ondelete='SET NULL'
    )
    op.create_index('ix_album_image_path_id', 'album', ['image_path_id'])


def downgrade() -> None:
    op.drop_index('ix_album_image_path_id', 'album')
    op.drop_constraint('fk_album_image_path_id', 'album', type_='foreignkey')
    op.drop_column('album', 'image_path_id')

    op.drop_index('ix_artist_image_path_id', 'artist')
    op.drop_constraint('fk_artist_image_path_id', 'artist', type_='foreignkey')
    op.drop_column('artist', 'image_path_id')
