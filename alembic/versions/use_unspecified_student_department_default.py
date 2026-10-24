"""Stop defaulting unprovided student departments to Computer Science.

Revision ID: use_unspecified_student_department_default
Revises: add_faculty_practice_assignments
"""
from alembic import op
import sqlalchemy as sa


revision = "use_unspecified_student_department_default"
down_revision = "add_faculty_practice_assignments"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("student_profiles") as batch_op:
        batch_op.alter_column(
            "department",
            existing_type=sa.String(length=100),
            existing_nullable=False,
            existing_server_default=sa.text("'Computer Science'"),
            server_default="Department Not Specified",
        )


def downgrade():
    with op.batch_alter_table("student_profiles") as batch_op:
        batch_op.alter_column(
            "department",
            existing_type=sa.String(length=100),
            existing_nullable=False,
            existing_server_default=sa.text("'Department Not Specified'"),
            server_default="Computer Science",
        )
