"""Add durable Messenger inbox state and retry metadata.

Revision ID: 0003_messenger_inbox
Revises: 0002_messenger_events
"""

from alembic import op
import sqlalchemy as sa


revision = "0003_messenger_inbox"
down_revision = "0002_messenger_events"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("messenger_events", sa.Column("psid", sa.String(length=160), nullable=True))
    op.add_column("messenger_events", sa.Column("text", sa.Text(), nullable=True))
    op.add_column("messenger_events", sa.Column("status", sa.String(length=24), nullable=False, server_default="done"))
    op.add_column("messenger_events", sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("messenger_events", sa.Column("last_error", sa.Text(), nullable=True))
    op.add_column("messenger_events", sa.Column("processed_at", sa.DateTime(), nullable=True))
    op.create_index("ix_messenger_events_psid", "messenger_events", ["psid"])
    op.create_index("ix_messenger_events_status", "messenger_events", ["status"])


def downgrade():
    op.drop_index("ix_messenger_events_status", table_name="messenger_events")
    op.drop_index("ix_messenger_events_psid", table_name="messenger_events")
    for column in ("processed_at", "last_error", "attempts", "status", "text", "psid"):
        op.drop_column("messenger_events", column)
