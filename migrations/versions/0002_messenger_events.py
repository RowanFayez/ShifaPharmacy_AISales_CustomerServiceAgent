"""Add durable inbound Messenger event deduplication.

Revision ID: 0002_messenger_events
Revises: 0001_initial_schema
"""

from alembic import op
import sqlalchemy as sa


revision = "0002_messenger_events"
down_revision = "0001_initial_schema"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "messenger_events",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("event_id", sa.String(length=160), nullable=False),
        sa.Column("received_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("event_id"),
    )
    op.create_index("ix_messenger_events_event_id", "messenger_events", ["event_id"])


def downgrade():
    op.drop_table("messenger_events")
