"""Initial schema.

Revision ID: 0001_initial
Revises:
Create Date: 2026-08-31
"""
from alembic import op
import sqlalchemy as sa

revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("username", sa.String(length=64), unique=True),
        sa.Column("display_name", sa.String(length=128), nullable=False),
        sa.Column("password_hash", sa.String(length=256), nullable=False),
        sa.Column("role", sa.String(length=16), server_default="user"),
        sa.Column("is_active", sa.Boolean(), server_default="true"),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_users_username", "users", ["username"])
    op.create_index("ix_users_role", "users", ["role"])
    op.create_index("ix_users_is_active", "users", ["is_active"])

    op.create_table(
        "conversations",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "conversation_members",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("conversation_id", sa.Integer(), sa.ForeignKey("conversations.id"), nullable=False),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("conversation_id", "user_id", name="uq_conversation_member"),
    )
    op.create_index("ix_conversation_members_conversation_id", "conversation_members", ["conversation_id"])
    op.create_index("ix_conversation_members_user_id", "conversation_members", ["user_id"])

    op.create_table(
        "attachments",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("message_id", sa.Integer(), sa.ForeignKey("messages.id"), nullable=False),
        sa.Column("encrypted_storage_key", sa.String(length=512), unique=True, nullable=False),
        sa.Column("storage_backend", sa.String(length=32), server_default="local"),
        sa.Column("original_filename", sa.String(length=512), nullable=False),
        sa.Column("mime_type", sa.String(length=128), nullable=False),
        sa.Column("size", sa.BigInteger(), nullable=False),
        sa.Column("encryption_metadata", sa.String(length=2048), server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "messages",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("conversation_id", sa.Integer(), sa.ForeignKey("conversations.id"), nullable=False),
        sa.Column("sender_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("message_type", sa.String(length=16), server_default="text"),
        sa.Column("encrypted_content", sa.Text(), nullable=True),
        sa.Column("attachment_id", sa.Integer(), sa.ForeignKey("attachments.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("edited_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_messages_conversation_id", "messages", ["conversation_id"])
    op.create_index("ix_messages_sender_id", "messages", ["sender_id"])
    op.create_index("ix_messages_created_at", "messages", ["created_at"])

    op.create_table(
        "message_receipts",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("message_id", sa.Integer(), sa.ForeignKey("messages.id"), nullable=False),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("delivered_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("read_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_message_receipts_message_id", "message_receipts", ["message_id"])
    op.create_index("ix_message_receipts_user_id", "message_receipts", ["user_id"])
    op.create_index("ix_attachments_message_id", "attachments", ["message_id"])


def downgrade() -> None:
    op.drop_index("ix_attachments_message_id", table_name="attachments")
    op.drop_index("ix_message_receipts_user_id", table_name="message_receipts")
    op.drop_index("ix_message_receipts_message_id", table_name="message_receipts")
    op.drop_table("message_receipts")
    op.drop_index("ix_messages_created_at", table_name="messages")
    op.drop_index("ix_messages_sender_id", table_name="messages")
    op.drop_index("ix_messages_conversation_id", table_name="messages")
    op.drop_table("messages")
    op.drop_table("attachments")
    op.drop_index("ix_conversation_members_user_id", table_name="conversation_members")
    op.drop_index("ix_conversation_members_conversation_id", table_name="conversation_members")
    op.drop_table("conversation_members")
    op.drop_table("conversations")
    op.drop_index("ix_users_is_active", table_name="users")
    op.drop_index("ix_users_role", table_name="users")
    op.drop_index("ix_users_username", table_name="users")
    op.drop_table("users")