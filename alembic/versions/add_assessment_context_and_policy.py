"""Add assessment context and policy for M2-E.

Revision ID: add_assessment_context_and_policy
Revises: add_assessment_lifecycle_timing
Create Date: 2026-09-22

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB


revision: str = "add_context_policy_m2e"
down_revision: Union[str, Sequence[str], None] = "add_assessment_lifecycle_timing"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing_tables = inspector.get_table_names()

    # Tables already created by the 20260924_baseline migration.
    # Guard all DDL so this is a no-op on a fresh database.
    if 'assessment_policies' not in existing_tables:
        op.create_table(
            "assessment_policies",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("name", sa.String(length=100), nullable=False),
            sa.Column("session_duration_minutes", sa.Integer(), nullable=False, server_default="180"),
            sa.Column("round_duration_minutes", sa.Integer(), nullable=False, server_default="30"),
            sa.Column("max_attempts", sa.Integer(), nullable=True),
            sa.Column("resume_allowed", sa.Boolean(), nullable=False, server_default="true"),
            sa.Column("exit_allowed", sa.Boolean(), nullable=False, server_default="true"),
            sa.Column("progression_mode", sa.String(length=20), nullable=False, server_default="sequential"),
            sa.Column("progression_config", JSONB, nullable=False, server_default="{}"),
            sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
            sa.PrimaryKeyConstraint("id"),
        )
    ap_indexes = {idx['name'] for idx in inspector.get_indexes('assessment_policies')}
    if 'ix_assessment_policies_id' not in ap_indexes:
        op.create_index("ix_assessment_policies_id", "assessment_policies", ["id"])

    if 'assessment_contexts' not in existing_tables:
        op.create_table(
            "assessment_contexts",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("mode", sa.String(length=50), nullable=False),
            sa.Column("purpose", sa.String(length=100), nullable=True),
            sa.Column("created_by_id", sa.Integer(), nullable=True),
            sa.Column("student_id", sa.Integer(), nullable=True),
            sa.Column("company_name", sa.String(length=200), nullable=True),
            sa.Column("target_role", sa.String(length=100), nullable=True),
            sa.Column("jd_text", sa.Text(), nullable=True),
            sa.Column("availability_start", sa.DateTime(), nullable=True),
            sa.Column("availability_end", sa.DateTime(), nullable=True),
            sa.Column("policy_id", sa.Integer(), nullable=False),
            sa.Column("status", sa.String(length=20), nullable=False, server_default="active"),
            sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
            sa.Column("completed_at", sa.DateTime(), nullable=True),
            sa.ForeignKeyConstraint(["created_by_id"], ["users.id"]),
            sa.ForeignKeyConstraint(["student_id"], ["users.id"]),
            sa.ForeignKeyConstraint(["policy_id"], ["assessment_policies.id"]),
            sa.PrimaryKeyConstraint("id"),
        )
    ac_indexes = {idx['name'] for idx in inspector.get_indexes('assessment_contexts')}
    for idx_name, col in [
        ("ix_assessment_contexts_id", ["id"]),
        ("ix_assessment_contexts_mode", ["mode"]),
        ("ix_assessment_contexts_student_id", ["student_id"]),
    ]:
        if idx_name not in ac_indexes:
            op.create_index(idx_name, "assessment_contexts", col)

    # Add context_id to assessment_sessions (nullable initially)
    session_cols = {col['name'] for col in inspector.get_columns('assessment_sessions')}
    if 'context_id' not in session_cols:
        op.add_column("assessment_sessions", sa.Column("context_id", sa.Integer(), nullable=True))
    as_indexes = {idx['name'] for idx in inspector.get_indexes('assessment_sessions')}
    if 'ix_assessment_sessions_context_id' not in as_indexes:
        op.create_index("ix_assessment_sessions_context_id", "assessment_sessions", ["context_id"])

    # Insert default policies only if they don't already exist
    op.execute("""
        INSERT INTO assessment_policies (
            id, name, session_duration_minutes, round_duration_minutes,
            max_attempts, resume_allowed, exit_allowed,
            progression_mode, progression_config
        )
        SELECT 1, 'Legacy Practice Policy', 180, 30, NULL, true, true,
               'sequential', '{"rounds": ["aptitude", "coding", "interview"]}'
        WHERE NOT EXISTS (SELECT 1 FROM assessment_policies WHERE id = 1)
    """)
    op.execute("""
        INSERT INTO assessment_policies (
            id, name, session_duration_minutes, round_duration_minutes,
            max_attempts, resume_allowed, exit_allowed,
            progression_mode, progression_config
        )
        SELECT 2, 'Practice Policy', 180, 30, NULL, true, true, 'independent', '{}'
        WHERE NOT EXISTS (SELECT 1 FROM assessment_policies WHERE id = 2)
    """)
    op.execute("""
        INSERT INTO assessment_contexts (id, mode, purpose, policy_id, status)
        SELECT 1, 'practice', 'legacy', 1, 'active'
        WHERE NOT EXISTS (SELECT 1 FROM assessment_contexts WHERE id = 1)
    """)

    # Reset sequences for PostgreSQL
    if bind.dialect.name == 'postgresql':
        op.execute("SELECT setval('assessment_policies_id_seq', (SELECT MAX(id) FROM assessment_policies))")
        op.execute("SELECT setval('assessment_contexts_id_seq', (SELECT MAX(id) FROM assessment_contexts))")

    # Backfill existing sessions to legacy context
    op.execute("""
        UPDATE assessment_sessions
        SET context_id = 1
        WHERE context_id IS NULL
    """)

    # Add foreign key constraint only if it doesn't already exist
    fk_names = {fk['name'] for fk in inspector.get_foreign_keys('assessment_sessions')}
    if 'fk_assessment_sessions_context_id' not in fk_names:
        op.create_foreign_key(
            "fk_assessment_sessions_context_id",
            "assessment_sessions",
            "assessment_contexts",
            ["context_id"],
            ["id"],
        )


def downgrade() -> None:
    # Remove foreign key first
    op.drop_constraint("fk_assessment_sessions_context_id", "assessment_sessions", type_="foreignkey")

    # Remove context_id column
    op.drop_index("ix_assessment_sessions_context_id", table_name="assessment_sessions")
    op.drop_column("assessment_sessions", "context_id")

    # Drop assessment_contexts
    op.drop_index("ix_assessment_contexts_student_id", table_name="assessment_contexts")
    op.drop_index("ix_assessment_contexts_mode", table_name="assessment_contexts")
    op.drop_index("ix_assessment_contexts_id", table_name="assessment_contexts")
    op.drop_table("assessment_contexts")

    # Drop assessment_policies
    op.drop_index("ix_assessment_policies_id", table_name="assessment_policies")
    op.drop_table("assessment_policies")
