"""add messages.raw (原始逐字转录，5b 阶段B 产出)

Revision ID: 7c4a9d5e21b3
Revises: 2b1e160e8df4
Create Date: 2026-07-29 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '7c4a9d5e21b3'
down_revision: Union[str, None] = '2b1e160e8df4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # MySQL TEXT 列不支持字面量 DEFAULT：先加可空列，回填空串后再收紧 NOT NULL
    op.add_column('messages', sa.Column('raw', sa.Text(), nullable=True))
    op.execute("UPDATE messages SET raw = '' WHERE raw IS NULL")
    op.alter_column('messages', 'raw', existing_type=sa.Text(), nullable=False)


def downgrade() -> None:
    op.drop_column('messages', 'raw')
