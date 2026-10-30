import sqlalchemy as sa
from alembic import op
from pgvector.sqlalchemy import VECTOR

revision = "0001_initial_schema"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "leads",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(160), nullable=False),
        sa.Column("email", sa.String(254)),
        sa.Column("phone", sa.String(40)),
        sa.Column("company", sa.String(160)),
        sa.Column("source", sa.String(120)),
        sa.Column("status", sa.String(32), nullable=False, server_default="new"),
        sa.Column("deal_value", sa.Float(), nullable=False, server_default="0"),
        sa.Column("notes", sa.Text(), nullable=False, server_default=""),
        sa.Column("last_contact_at", sa.String(64)),
        sa.Column("next_follow_up_at", sa.String(64)),
        sa.Column("opted_out", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.String(64), nullable=False),
        sa.Column("updated_at", sa.String(64), nullable=False),
    )
    op.create_index("ix_leads_status", "leads", ["status"])
    op.create_table(
        "drafts",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("lead_id", sa.Integer(), sa.ForeignKey("leads.id", ondelete="CASCADE"), nullable=False),
        sa.Column("channel", sa.String(24), nullable=False),
        sa.Column("subject", sa.String(500), nullable=False, server_default=""),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("created_at", sa.String(64), nullable=False),
    )
    op.create_index("ix_drafts_lead_id", "drafts", ["lead_id"])
    op.create_table(
        "knowledge_documents",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("title", sa.String(240), nullable=False),
        sa.Column("source", sa.String(500)),
        sa.Column("created_at", sa.String(64), nullable=False),
    )
    op.create_table(
        "knowledge_chunks",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("document_id", sa.Integer(), sa.ForeignKey("knowledge_documents.id", ondelete="CASCADE"), nullable=False),
        sa.Column("chunk_index", sa.Integer(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("embedding", VECTOR(768)),
    )
    op.create_index("ix_knowledge_chunks_document_id", "knowledge_chunks", ["document_id"])
    op.execute(
        "CREATE INDEX ix_knowledge_chunks_embedding_hnsw "
        "ON knowledge_chunks USING hnsw (embedding vector_cosine_ops)"
    )


def downgrade():
    op.drop_index("ix_knowledge_chunks_embedding_hnsw", table_name="knowledge_chunks")
    op.drop_index("ix_knowledge_chunks_document_id", table_name="knowledge_chunks")
    op.drop_table("knowledge_chunks")
    op.drop_table("knowledge_documents")
    op.drop_index("ix_drafts_lead_id", table_name="drafts")
    op.drop_table("drafts")
    op.drop_index("ix_leads_status", table_name="leads")
    op.drop_table("leads")
