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
    # Create assessment_policies table
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
    op.create_index("ix_assessment_policies_id", "assessment_policies", ["id"])
    
    # Create assessment_contexts table
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
    op.create_index("ix_assessment_contexts_id", "assessment_contexts", ["id"])
    op.create_index("ix_assessment_contexts_mode", "assessment_contexts", ["mode"])
    op.create_index("ix_assessment_contexts_student_id", "assessment_contexts", ["student_id"])
    
    # Add context_id to assessment_sessions (nullable initially)
    op.add_column("assessment_sessions", sa.Column("context_id", sa.Integer(), nullable=True))
    op.create_index("ix_assessment_sessions_context_id", "assessment_sessions", ["context_id"])
    
    # Insert default legacy practice policy
    op.execute("""
        INSERT INTO assessment_policies (
            id, name, session_duration_minutes, round_duration_minutes, 
            max_attempts, resume_allowed, exit_allowed, 
            progression_mode, progression_config
        ) VALUES (
            1, 'Legacy Practice Policy', 180, 30,
            NULL, true, true,
            'sequential', '{"rounds": ["aptitude", "coding", "interview"]}'
        )
    """)
    
    # Insert default practice policy (for future use)
    op.execute("""
        INSERT INTO assessment_policies (
            id, name, session_duration_minutes, round_duration_minutes,
            max_attempts, resume_allowed, exit_allowed,
            progression_mode, progression_config
        ) VALUES (
            2, 'Practice Policy', 180, 30,
            NULL, true, true,
            'independent', '{}'
        )
    """)
    
    # Create legacy context for backfilling existing sessions
    op.execute("""
        INSERT INTO assessment_contexts (
            id, mode, purpose, policy_id, status
        ) VALUES (
            1, 'practice', 'legacy', 1, 'active'
        )
    """)
    
    # Reset sequences for PostgreSQL
    bind = op.get_bind()
    if bind.dialect.name == 'postgresql':
        op.execute("SELECT setval('assessment_policies_id_seq', (SELECT MAX(id) FROM assessment_policies))")
        op.execute("SELECT setval('assessment_contexts_id_seq', (SELECT MAX(id) FROM assessment_contexts))")
    
    # Backfill existing sessions to legacy context
    op.execute("""
        UPDATE assessment_sessions 
        SET context_id = 1 
        WHERE context_id IS NULL
    """)
    
    # Now add foreign key constraint
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
