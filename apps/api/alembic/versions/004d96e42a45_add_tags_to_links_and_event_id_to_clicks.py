"""add_tags_to_links_and_event_id_to_clicks

Revision ID: 004d96e42a45
Revises: 5b6501baea2c
Create Date: 2026-11-15 00:36:51.887381

"""
from typing import Sequence, Union

from alembic import context, op
import sqlalchemy as sa
from sqlalchemy import inspect


# revision identifiers, used by Alembic.
revision: str = '004d96e42a45'
down_revision: Union[str, Sequence[str], None] = '5b6501baea2c'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema: add tags to links and event_id to click_events."""
    bind = op.get_bind()
    is_online = bind is not None and not context.is_offline_mode()

    existing_links_cols = set()
    existing_clicks_cols = set()
    existing_clicks_indexes = set()

    if is_online:
        insp = inspect(bind)
        existing_links_cols = {col['name'] for col in insp.get_columns('links')}
        existing_clicks_cols = {col['name'] for col in insp.get_columns('click_events')}
        existing_clicks_indexes = {idx['name'] for idx in insp.get_indexes('click_events')}

    # 1. Add tags column to links table as nullable VARCHAR(256)
    if not is_online or 'tags' not in existing_links_cols:
        op.add_column('links', sa.Column('tags', sa.String(length=256), nullable=True))

    # 2. Add event_id column to click_events table as nullable VARCHAR(64)
    if not is_online or 'event_id' not in existing_clicks_cols:
        op.add_column('click_events', sa.Column('event_id', sa.String(length=64), nullable=True))

    # 3. Create unique index for event_id matching SQLAlchemy unique=True, index=True
    index_name = op.f('ix_click_events_event_id')
    if not is_online or index_name not in existing_clicks_indexes:
        op.create_index(index_name, 'click_events', ['event_id'], unique=True)


def downgrade() -> None:
    """Downgrade schema: safely remove event_id index/column and tags column."""
    bind = op.get_bind()
    is_online = bind is not None and not context.is_offline_mode()

    existing_links_cols = set()
    existing_clicks_cols = set()
    existing_clicks_indexes = set()

    if is_online:
        insp = inspect(bind)
        existing_links_cols = {col['name'] for col in insp.get_columns('links')}
        existing_clicks_cols = {col['name'] for col in insp.get_columns('click_events')}
        existing_clicks_indexes = {idx['name'] for idx in insp.get_indexes('click_events')}

    index_name = op.f('ix_click_events_event_id')
    if not is_online or index_name in existing_clicks_indexes:
        op.drop_index(index_name, table_name='click_events')

    if not is_online or 'event_id' in existing_clicks_cols:
        op.drop_column('click_events', 'event_id')

    if not is_online or 'tags' in existing_links_cols:
        op.drop_column('links', 'tags')
