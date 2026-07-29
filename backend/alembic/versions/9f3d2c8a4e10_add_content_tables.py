"""add content tables: prompts / categories / stories（管理后台运营内容）

Revision ID: 9f3d2c8a4e10
Revises: 7c4a9d5e21b3
Create Date: 2026-07-29 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '9f3d2c8a4e10'
down_revision: Union[str, None] = '7c4a9d5e21b3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('prompts',
    sa.Column('key', sa.String(length=64), nullable=False),
    sa.Column('content', sa.Text(), nullable=False),
    sa.Column('remark', sa.String(length=255), nullable=False),
    sa.Column('updated_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
    sa.PrimaryKeyConstraint('key')
    )
    op.create_table('categories',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('module_type', sa.String(length=32), nullable=False),
    sa.Column('name', sa.String(length=32), nullable=False),
    sa.Column('sort_order', sa.Integer(), nullable=False),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('module_type', 'name', name='uk_module_name')
    )
    op.create_index(op.f('ix_categories_module_type'), 'categories', ['module_type'], unique=False)
    op.create_table('stories',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('module_type', sa.String(length=32), nullable=False),
    sa.Column('title', sa.String(length=64), nullable=False),
    sa.Column('seed', sa.String(length=64), nullable=True),
    sa.Column('cat', sa.String(length=32), nullable=False),
    sa.Column('content', sa.JSON(), nullable=False),
    sa.Column('sort_order', sa.Integer(), nullable=False),
    sa.Column('enabled', sa.Boolean(), nullable=False),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('module_type', 'seed', name='uk_module_seed')
    )
    op.create_index(op.f('ix_stories_module_type'), 'stories', ['module_type'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_stories_module_type'), table_name='stories')
    op.drop_table('stories')
    op.drop_index(op.f('ix_categories_module_type'), table_name='categories')
    op.drop_table('categories')
    op.drop_table('prompts')
