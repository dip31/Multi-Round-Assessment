"""add_profile_tables_and_resume_columns

Revision ID: 7b404c6a0d4f
Revises: 545b4e6f20d4
Create Date: 2026-09-18 23:15:45.582678

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '7b404c6a0d4f'
down_revision: Union[str, None] = '545b4e6f20d4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── Create profile tables ─────────────────────────────────────────
    op.create_table('student_profiles',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('roll_number', sa.String(length=50), nullable=True),
        sa.Column('department', sa.String(length=100), nullable=False, server_default='Computer Science'),
        sa.Column('cgpa', sa.Float(), nullable=False, server_default='7.5'),
        sa.Column('graduation_year', sa.Integer(), nullable=False, server_default='2026'),
        sa.Column('backlogs_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('institution', sa.String(length=200), nullable=False, server_default='Engineering College'),
        sa.Column('target_role', sa.String(length=100), nullable=True),
        sa.Column('skills_json', postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default='[]'),
        sa.Column('phone_number', sa.String(length=20), nullable=True),
        sa.Column('mobile_no', sa.String(length=50), nullable=True),
        sa.Column('full_name', sa.String(length=150), nullable=True),
        sa.Column('college_email_id', sa.String(length=150), nullable=True),
        sa.Column('gender', sa.String(length=50), nullable=True),
        sa.Column('date_of_birth', sa.String(length=50), nullable=True),
        sa.Column('nationality', sa.String(length=100), nullable=True, server_default='Indian'),
        sa.Column('tenth_marks', sa.Float(), nullable=True),
        sa.Column('twelfth_marks', sa.Float(), nullable=True),
        sa.Column('bio', sa.Text(), nullable=True),
        sa.Column('portfolio_data', postgresql.JSONB(astext_type=sa.Text()), server_default='{}', nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_student_profiles_id', 'student_profiles', ['id'], unique=False)
    op.create_index('ix_student_profiles_user_id', 'student_profiles', ['user_id'], unique=True)

    op.create_table('faculty_profiles',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('department', sa.String(length=100), nullable=False, server_default='Computer Science'),
        sa.Column('designation', sa.String(length=100), nullable=False, server_default='Assistant Professor'),
        sa.Column('institution', sa.String(length=200), nullable=False, server_default='Engineering College'),
        sa.Column('employee_id', sa.String(length=50), nullable=True),
        sa.Column('bio', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_faculty_profiles_id', 'faculty_profiles', ['id'], unique=False)
    op.create_index('ix_faculty_profiles_user_id', 'faculty_profiles', ['user_id'], unique=True)

    op.create_table('tpo_profiles',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('institution', sa.String(length=200), nullable=False, server_default='Engineering College'),
        sa.Column('designation', sa.String(length=100), nullable=False, server_default='Training & Placement Officer'),
        sa.Column('contact_email', sa.String(length=150), nullable=True),
        sa.Column('contact_phone', sa.String(length=20), nullable=True),
        sa.Column('bio', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_tpo_profiles_id', 'tpo_profiles', ['id'], unique=False)
    op.create_index('ix_tpo_profiles_user_id', 'tpo_profiles', ['user_id'], unique=True)

    # ── Add missing columns to user_resumes ───────────────────────────
    op.add_column('user_resumes', sa.Column('cv_name', sa.String(length=200), nullable=False, server_default='My Resume'))
    op.add_column('user_resumes', sa.Column('cv_type', sa.String(length=100), nullable=False, server_default='Software Developer'))
    op.add_column('user_resumes', sa.Column('file_name', sa.String(length=255), nullable=False, server_default='resume.pdf'))
    op.add_column('user_resumes', sa.Column('file_path', sa.String(length=500), nullable=False, server_default=''))
    op.add_column('user_resumes', sa.Column('file_size', sa.Integer(), nullable=False, server_default='0'))


def downgrade() -> None:
    op.drop_column('user_resumes', 'file_size')
    op.drop_column('user_resumes', 'file_path')
    op.drop_column('user_resumes', 'file_name')
    op.drop_column('user_resumes', 'cv_type')
    op.drop_column('user_resumes', 'cv_name')

    op.drop_index('ix_tpo_profiles_user_id', table_name='tpo_profiles')
    op.drop_index('ix_tpo_profiles_id', table_name='tpo_profiles')
    op.drop_table('tpo_profiles')

    op.drop_index('ix_faculty_profiles_user_id', table_name='faculty_profiles')
    op.drop_index('ix_faculty_profiles_id', table_name='faculty_profiles')
    op.drop_table('faculty_profiles')

    op.drop_index('ix_student_profiles_user_id', table_name='student_profiles')
    op.drop_index('ix_student_profiles_id', table_name='student_profiles')
    op.drop_table('student_profiles')
