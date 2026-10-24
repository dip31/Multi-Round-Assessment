"""Add persisted faculty practice assignments and engine result links.

Revision ID: add_faculty_practice_assignments
Revises: add_competency_mapping_status_4g
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "add_faculty_practice_assignments"
down_revision = "add_competency_mapping_status_4g"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "faculty_practice_assessments",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("faculty_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("request_key", sa.String(80), nullable=True),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("instructions", sa.Text(), nullable=True),
        sa.Column("availability_start", sa.DateTime(), nullable=True),
        sa.Column("availability_end", sa.DateTime(), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="published"),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("faculty_id", "request_key", name="uq_faculty_practice_request_key"),
    )
    op.create_index("ix_faculty_practice_assessments_faculty_id", "faculty_practice_assessments", ["faculty_id"])
    op.create_table(
        "faculty_practice_assessment_rounds",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("assessment_id", sa.Integer(), sa.ForeignKey("faculty_practice_assessments.id", ondelete="CASCADE"), nullable=False),
        sa.Column("round_type", sa.String(20), nullable=False),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("configuration", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.UniqueConstraint("assessment_id", "sequence", name="uq_faculty_practice_round_sequence"),
    )
    op.create_index("ix_faculty_practice_assessment_rounds_assessment_id", "faculty_practice_assessment_rounds", ["assessment_id"])
    op.create_table(
        "faculty_practice_assignments",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("assessment_id", sa.Integer(), sa.ForeignKey("faculty_practice_assessments.id", ondelete="CASCADE"), nullable=False),
        sa.Column("student_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("assigned_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("assessment_id", "student_id", name="uq_faculty_practice_recipient"),
    )
    op.create_index("ix_faculty_practice_assignments_assessment_id", "faculty_practice_assignments", ["assessment_id"])
    op.create_index("ix_faculty_practice_assignments_student_id", "faculty_practice_assignments", ["student_id"])
    op.create_table(
        "faculty_practice_round_attempts",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("assignment_id", sa.Integer(), sa.ForeignKey("faculty_practice_assignments.id", ondelete="CASCADE"), nullable=False),
        sa.Column("assessment_round_id", sa.Integer(), sa.ForeignKey("faculty_practice_assessment_rounds.id", ondelete="CASCADE"), nullable=False),
        sa.Column("session_id", sa.Integer(), sa.ForeignKey("assessment_sessions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("round_id", sa.Integer(), sa.ForeignKey("assessment_rounds.id", ondelete="CASCADE"), nullable=False),
        sa.UniqueConstraint("assignment_id", "assessment_round_id", name="uq_faculty_practice_round_attempt"),
        sa.UniqueConstraint("session_id", "round_id", name="uq_faculty_practice_engine_link"),
    )
    op.create_index("ix_faculty_practice_round_attempts_assignment_id", "faculty_practice_round_attempts", ["assignment_id"])


def downgrade():
    op.drop_index("ix_faculty_practice_round_attempts_assignment_id", table_name="faculty_practice_round_attempts")
    op.drop_table("faculty_practice_round_attempts")
    op.drop_index("ix_faculty_practice_assignments_student_id", table_name="faculty_practice_assignments")
    op.drop_index("ix_faculty_practice_assignments_assessment_id", table_name="faculty_practice_assignments")
    op.drop_table("faculty_practice_assignments")
    op.drop_index("ix_faculty_practice_assessment_rounds_assessment_id", table_name="faculty_practice_assessment_rounds")
    op.drop_table("faculty_practice_assessment_rounds")
    op.drop_index("ix_faculty_practice_assessments_faculty_id", table_name="faculty_practice_assessments")
    op.drop_table("faculty_practice_assessments")
