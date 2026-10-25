"""Database-free regression coverage for verified schema/ORM drift fixes."""

import app.models  # noqa: F401 - populate the declarative metadata registry
import app.models.coding  # noqa: F401
import app.models.rl  # noqa: F401
from app.database.base import Base


def _foreign_key_signature(table_name):
    table = Base.metadata.tables[table_name]
    return {
        (
            fk.parent.name,
            fk.target_fullname,
            fk.ondelete,
        )
        for fk in table.foreign_keys
    }


def test_rl_attempt_log_metadata_matches_live_source_foreign_keys():
    assert _foreign_key_signature("rl_attempt_log") == {
        ("user_id", "users.id", None),
        ("session_id", "assessment_sessions.id", None),
        ("question_id", "aptitude_questions.id", None),
    }


def test_active_session_partial_unique_index_matches_migration():
    table = Base.metadata.tables["assessment_sessions"]
    index = next(index for index in table.indexes if index.name == "one_active_session_per_user")
    assert index.unique is True
    assert [column.name for column in index.columns] == ["user_id"]
    assert str(index.dialect_options["postgresql"]["where"]) == "status = 'in_progress'"
    assert str(index.dialect_options["sqlite"]["where"]) == "status = 'in_progress'"


def test_active_round_partial_unique_index_matches_migration():
    table = Base.metadata.tables["assessment_rounds"]
    index = next(index for index in table.indexes if index.name == "one_active_round_per_session")
    assert index.unique is True
    assert [column.name for column in index.columns] == ["session_id"]
    assert str(index.dialect_options["postgresql"]["where"]) == "status = 'active'"
    assert str(index.dialect_options["sqlite"]["where"]) == "status = 'active'"


def test_department_default_remains_application_side_only_until_migration_review():
    column = Base.metadata.tables["student_profiles"].c.department
    assert column.nullable is False
    assert column.default.arg == "Department Not Specified"
    assert column.server_default is None


def test_coding_blueprint_relationship_is_nullable_and_set_null():
    column = Base.metadata.tables["coding_problems"].c.blueprint_id
    foreign_key = next(iter(column.foreign_keys))
    assert column.nullable is True
    assert foreign_key.target_fullname == "company_blueprints.id"
    assert foreign_key.ondelete == "SET NULL"
