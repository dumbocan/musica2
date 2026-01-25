"""create_stored_image_path_table

Revision ID: create_stored_image_path
Revises:
Create Date: 2025-01-25

Create the storedimagepath table for filesystem-based image storage.

"""
from typing import Union
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by alembic.
revision: str = 'create_stored_image_path'
down_revision: Union[str, None] = None
branch_labels: Union[str, None] = None
depends_on: Union[str, None] = None


def upgrade() -> None:
    # Create storedimagepath table
    op.create_table(
        'storedimagepath',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('entity_type', sa.String(), nullable=False),
        sa.Column('entity_id', sa.Integer(), nullable=True),
        sa.Column('source_url', sa.String(length=500), nullable=False),
        sa.Column('path_128', sa.String(), nullable=True),
        sa.Column('path_256', sa.String(), nullable=True),
        sa.Column('path_512', sa.String(), nullable=True),
        sa.Column('path_1024', sa.String(), nullable=True),
        sa.Column('original_width', sa.Integer(), nullable=True),
        sa.Column('original_height', sa.Integer(), nullable=True),
        sa.Column('format', sa.String(), nullable=False, server_default='webp'),
        sa.Column('file_size_bytes', sa.Integer(), nullable=True),
        sa.Column('content_hash', sa.String(length=64), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.Column('last_accessed_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('entity_type', 'entity_id')
    )
    op.create_index('ix_storedimagepath_entity_type', 'storedimagepath', ['entity_type'])
    op.create_index('ix_storedimagepath_entity_id', 'storedimagepath', ['entity_id'])
    op.create_index('ix_storedimagepath_content_hash', 'storedimagepath', ['content_hash'])


def downgrade() -> None:
    op.drop_index('ix_storedimagepath_content_hash', 'storedimagepath')
    op.drop_index('ix_storedimagepath_entity_id', 'storedimagepath')
    op.drop_index('ix_storedimagepath_entity_type', 'storedimagepath')
    op.drop_table('storedimagepath')
