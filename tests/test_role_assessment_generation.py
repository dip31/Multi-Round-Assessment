"""No-history role assessment generation: deterministic tests, no live LLM calls."""

import httpx
import pytest
from types import SimpleNamespace
from fastapi import HTTPException
from groq import RateLimitError
from sqlalchemy import create_engine
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.orm import Session

from app.database.base import Base
from app.models import user as _user_model  # noqa: F401
from app.models.company_data import CompanyBlueprint, CompanyHistoricalData, CompanyPattern
from app.models.mock_drive import MockDrive
from app.models import mock_drive as _mock_drive_model  # noqa: F401
from app.schemas.company_data import RoleAssessmentGenerationRequest
from app.schemas.mock_drive import MockDriveCreate
from app.services.company_blueprint_service import approve_blueprint, generate_blueprint_from_pattern
from app.services.company_data_service import review_pattern
from app.services.role_assessment_service import generate_role_assessment_pattern
from app.services.mock_drive_service import create_mock_drive
from app.services.groq_service import GroqService


@compiles(JSONB, "sqlite")
def compile_jsonb_sqlite(type_, compiler, **kw):
    return "TEXT"


@pytest.fixture
def db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        yield session
    engine.dispose()


def definition(context):
    role = context["target_role"]
    rounds = {}
    for index, round_config in enumerate(context["rounds"]):
        round_type = round_config["round_type"]
        topics = [f"{role} capability {index + 1}", f"{role} practice {index + 1}"]
        rounds[round_type] = {
            "topics": topics,
            "topic_weights": {topics[0]: 60, topics[1]: 40},
        }
    return {
        "role": role,
        "role_understanding": {
            "summary": f"Assessment design for {role}.",
            "responsibilities": ["Deliver role outcomes"],
            "core_skills": ["Role analysis"],
            "tools_and_technologies": ["Relevant tools"],
            "competencies": ["Communication"],
        },
        "rounds": rounds,
    }


def request(company, role, rounds=None, job_description=None):
    configured = rounds or ["aptitude", "coding", "technical_interview"]
    return RoleAssessmentGenerationRequest(
        company_name=company,
        target_role=role,
        rounds=[{"round_type": r, "question_count": 5, "duration_minutes": 30,
                 "difficulty_distribution": {"easy": 0.2, "medium": 0.6, "hard": 0.2}}
                for r in configured],
        job_description=job_description,
    )


@pytest.mark.parametrize("role", ["Data Analyst", "Product Manager", "Software Engineer"])
def test_generates_role_specific_pending_pattern_without_generic_seed(db, role):
    pattern = generate_role_assessment_pattern(
        db, request(f"NoHistory {role}", role), 1, llm_generator=definition
    )
    assert pattern.target_role == role
    assert pattern.source_count == 0
    assert pattern.pattern_data["source_provenance"]["generation_method"] == "llm_role_assessment"
    assert pattern.pattern_data["source_provenance"]["empirical_source_count"] == 0
    assert pattern.pattern_data["source_provenance"]["requested_company"] == f"NoHistory {role}"
    assert pattern.pattern_data["source_provenance"]["requested_role"] == role
    assert pattern.pattern_data["source_provenance"]["historical_source_count"] == 0
    assert pattern.pattern_data["source_provenance"]["historical_evidence_used"] is False
    assert pattern.pattern_data["review_status"] == "pending_review"
    assert db.query(CompanyHistoricalData).count() == 0
    assert db.query(CompanyBlueprint).count() == 0


@pytest.mark.parametrize("bad_response", [
    {"not": "the schema"},
    {
        "role": "Data Analyst",
        "role_understanding": {"summary": "x", "responsibilities": [], "core_skills": [], "tools_and_technologies": [], "competencies": []},
        "rounds": {
            "aptitude": {"topics": [], "topic_weights": {}},
            "coding": {"topics": ["x"], "topic_weights": {"x": 100}},
            "technical_interview": {"topics": ["y"], "topic_weights": {"y": 100}},
        },
    },
])
def test_invalid_or_empty_model_output_fails_without_persistence(db, bad_response):
    with pytest.raises(HTTPException) as exc:
        generate_role_assessment_pattern(
            db, request("NoHistory Invalid", "Data Analyst"), 1,
            llm_generator=lambda _: bad_response,
        )
    assert exc.value.detail["code"] == "ROLE_ASSESSMENT_GENERATION_FAILED"
    assert db.query(CompanyPattern).count() == 0
    assert db.query(CompanyBlueprint).count() == 0


@pytest.mark.parametrize("failure", [
    "missing_field", "empty_competencies", "duplicate_topics", "negative_weight",
    "unsupported_round", "role_mismatch",
])
def test_schema_rejects_invalid_definition_before_persistence(db, failure):
    def invalid(_):
        result = definition({"target_role": "Data Analyst", "rounds": request("x", "x").rounds})
        if failure == "missing_field":
            del result["role_understanding"]["summary"]
        elif failure == "empty_competencies":
            result["role_understanding"]["competencies"] = []
        elif failure == "duplicate_topics":
            result["rounds"]["aptitude"]["topics"] = ["SQL", "sql"]
            result["rounds"]["aptitude"]["topic_weights"] = {"SQL": 50, "sql": 50}
        elif failure == "negative_weight":
            result["rounds"]["aptitude"]["topic_weights"] = {"Data Analyst capability 1": -1, "Data Analyst practice 1": 101}
        elif failure == "unsupported_round":
            result["rounds"]["devops"] = result["rounds"].pop("coding")
        elif failure == "role_mismatch":
            result["role"] = "Software Engineer"
        return result

    with pytest.raises(HTTPException) as exc:
        generate_role_assessment_pattern(db, request(f"Invalid {failure}", "Data Analyst"), 1, llm_generator=invalid)
    assert exc.value.detail["code"] == "ROLE_ASSESSMENT_GENERATION_FAILED"
    assert db.query(CompanyPattern).count() == 0
    assert db.query(CompanyBlueprint).count() == 0


def test_groq_rate_limit_error_maps_to_http_429(db):
    response = httpx.Response(
        429,
        request=httpx.Request("POST", "https://api.groq.com/openai/v1/chat/completions"),
    )
    upstream = (
        "Error code: 429 - {'error': {'message': 'Rate limit reached for model "
        "`openai/gpt-oss-120b` in organization `org_test` service tier `on_demand` on tokens "
        "per minute (TPM): Limit 8000, Used 4090, Requested 4808. Please try again in 6.735s. "
        "Need more tokens? Upgrade to Dev Tier today.', 'type': 'tokens', "
        "'code': 'rate_limit_exceeded'}}"
    )

    def rate_limited(_):
        raise RateLimitError(upstream, response=response, body={"error": {"code": "rate_limit_exceeded"}})

    with pytest.raises(HTTPException) as exc:
        generate_role_assessment_pattern(
            db, request("RateLimited Co", "Data Analyst"), 1, llm_generator=rate_limited
        )
    assert exc.value.status_code == 429
    assert exc.value.detail["code"] == "GROQ_RATE_LIMITED"
    assert "6.735s" in exc.value.detail["message"]
    assert db.query(CompanyPattern).count() == 0
    assert db.query(CompanyBlueprint).count() == 0


def test_generic_llm_failure_still_maps_to_http_502(db):
    def broken(_):
        raise ValueError("LLM output rounds do not match the requested rounds")

    with pytest.raises(HTTPException) as exc:
        generate_role_assessment_pattern(
            db, request("GenericFailure Co", "Data Analyst"), 1, llm_generator=broken
        )
    assert exc.value.status_code == 502
    assert exc.value.detail["code"] == "ROLE_ASSESSMENT_GENERATION_FAILED"
    assert exc.value.detail["message"] == "LLM output rounds do not match the requested rounds"
    assert db.query(CompanyPattern).count() == 0
    assert db.query(CompanyBlueprint).count() == 0


@pytest.mark.parametrize("job_description", [None, "Lead analytics strategy and own executive reporting."])
def test_round_configuration_and_optional_job_description_reach_llm(db, job_description):
    seen = {}

    def capture(context):
        seen.update(context)
        return definition(context)

    pattern = generate_role_assessment_pattern(
        db, request(f"Context {job_description}", "Data Analyst", job_description=job_description),
        1, llm_generator=capture,
    )
    assert seen["job_description"] == job_description
    assert seen["rounds"][0]["question_count"] == 5
    assert seen["rounds"][0]["duration_minutes"] == 30
    assert seen["company_evidence"] is None
    assert "experience_level" not in pattern.pattern_data
    assert "job_description" not in pattern.pattern_data


def test_generated_pattern_flows_through_existing_blueprint_and_approval(db):
    pattern = generate_role_assessment_pattern(
        db, request("NoHistory Blueprint", "Product Manager"), 1, llm_generator=definition
    )
    with pytest.raises(HTTPException):
        generate_blueprint_from_pattern(db, "NoHistory Blueprint", "Product Manager", 1)
    review_pattern(db, "NoHistory Blueprint", "Product Manager", "approved", None, "tpo@example.test")
    blueprint = generate_blueprint_from_pattern(db, "NoHistory Blueprint", "Product Manager", 1)
    assert blueprint.status == "draft"
    assert blueprint.evidence_sources_count == 0
    for round_config in blueprint.blueprint_data["rounds"]:
        assert [topic["weight_pct"] for topic in round_config["topics"]] == [60.0, 40.0]
        assert all(topic["is_default"] is False for topic in round_config["topics"])
        assert round_config["question_count"] == 5
        assert round_config["time_limit_minutes"] == 30
    assert [item["difficulty_distribution"] for item in blueprint.blueprint_data["rounds"]] == [
        {"easy": 0.2, "medium": 0.6, "hard": 0.2},
        {"easy": 0.2, "medium": 0.6, "hard": 0.2},
        {"easy": 0.2, "medium": 0.6, "hard": 0.2},
    ]
    approved = approve_blueprint(db, "NoHistory Blueprint", "Product Manager", "approved", None, 1)
    assert approved.status == "approved"


@pytest.mark.parametrize("selected", [
    ["aptitude", "technical_interview"], ["coding"], ["aptitude", "coding"],
    ["aptitude", "coding", "technical_interview", "hr_interview"],
])
def test_selected_rounds_and_drive_settings_survive_pattern_generation(db, selected):
    cfg = [{"round_type": r, "question_count": 17 + index, "duration_minutes": 21 + index,
            "difficulty_distribution": {"easy": 0, "medium": 0.5, "hard": 0.5}}
           for index, r in enumerate(selected)]
    payload = RoleAssessmentGenerationRequest(company_name="Drive Co", target_role="Data Analyst", rounds=cfg)
    pattern = generate_role_assessment_pattern(db, payload, 1, llm_generator=definition)
    assert pattern.pattern_data["assessment_rounds"] == selected
    review_pattern(db, "Drive Co", "Data Analyst", "approved", None, "tpo@example.test")
    blueprint = generate_blueprint_from_pattern(db, "Drive Co", "Data Analyst", 1)
    actual = blueprint.blueprint_data["rounds"]
    assert [round_config["round_type"] for round_config in actual] == selected
    assert [round_config["question_count"] for round_config in actual] == [item["question_count"] for item in cfg]
    assert [round_config["time_limit_minutes"] for round_config in actual] == [item["duration_minutes"] for item in cfg]
    assert [round_config["difficulty_distribution"] for round_config in actual] == [item["difficulty_distribution"] for item in cfg]


@pytest.mark.parametrize("field,value", [
    ("question_count", 0), ("duration_minutes", 301),
    ("difficulty_distribution", {"easy": 0.2, "medium": 0.2, "hard": 0.2}),
])
def test_invalid_drive_configuration_is_rejected_before_generation(field, value):
    config = {"question_count": 5, "duration_minutes": 30,
              "difficulty_distribution": {"easy": 0, "medium": 1, "hard": 0}}
    config[field] = value
    with pytest.raises(ValueError):
        RoleAssessmentGenerationRequest(company_name="Invalid", target_role="Data Analyst", rounds=[{
            "round_type": "aptitude", **config,
        }])
    with pytest.raises(ValueError):
        MockDriveCreate(company_name="Invalid", target_role="Data Analyst",
                        selected_rounds={"aptitude": True}, round_configurations={"aptitude": config})


def test_mock_drive_persists_its_selected_round_configuration(db):
    configuration = {"coding": {
        "question_count": 4,
        "duration_minutes": 35,
        "difficulty_distribution": {"easy": 0, "medium": 0.5, "hard": 0.5},
    }}
    drive = create_mock_drive(db, MockDriveCreate(
        company_name="Drive Config Co", target_role="Data Analyst",
        selected_rounds={"coding": True}, round_configurations=configuration,
    ), created_by_id=1)
    db.refresh(drive)
    assert drive.round_configurations == configuration
    assert db.query(MockDrive).filter_by(id=drive.id).one().round_configurations == configuration


def test_legacy_generic_source_is_not_used_as_evidence_or_mutated(db):
    source = CompanyHistoricalData(
        company_name="Legacy Generic Co", target_role="Data Analyst", label="old generic",
        source_type="pre_seeded", raw_data={
            "benchmark_reference": "Generic Benchmark - Software Engineer",
            "source_provenance": {"classification": "generic_fallback", "explicit_fallback_requested": True},
        }, created_by_id=1,
    )
    db.add(source)
    db.commit()
    original_data = dict(source.raw_data)
    pattern = generate_role_assessment_pattern(
        db, request("Legacy Generic Co", "Data Analyst"), 1, llm_generator=definition
    )
    assert pattern.source_count == 0
    db.refresh(source)
    assert source.raw_data == original_data


def test_legacy_generic_row_without_provenance_is_not_compatible_even_for_software_engineer(db):
    source = CompanyHistoricalData(
        company_name="Legacy SWE Co", target_role="Software Engineer", label="old seed",
        source_type="pre_seeded", raw_data={
            "benchmark_reference": "Generic Benchmark - Software Engineer",
            "topics": ["Data Structures & Algorithms"],
        }, created_by_id=1,
    )
    db.add(source)
    db.commit()
    pattern = generate_role_assessment_pattern(
        db, request("Legacy SWE Co", "Software Engineer"), 1, llm_generator=definition
    )
    assert pattern.pattern_data["source_provenance"]["generation_method"] == "llm_role_assessment"
    assert pattern.pattern_data["topics"]
    assert "Data Structures & Algorithms" not in pattern.pattern_data["topics"]


def test_legacy_generic_pattern_can_be_replaced_without_changing_source_rows(db):
    source = CompanyHistoricalData(
        company_name="Legacy Pattern Co", target_role="Data Analyst", label="generic source",
        source_type="pre_seeded", raw_data={
            "benchmark_reference": "Generic Benchmark - Software Engineer",
            "source_provenance": {"classification": "generic_fallback", "explicit_fallback_requested": True},
            "topics": ["Data Structures & Algorithms"],
        }, created_by_id=1,
    )
    old_pattern = CompanyPattern(
        company_name="Legacy Pattern Co", target_role="Data Analyst",
        pattern_data={"is_fallback": True, "source_provenance": {"classification": "generic_fallback"}},
        source_count=1, created_by_id=1,
    )
    db.add_all([source, old_pattern])
    db.commit()
    original_source = dict(source.raw_data)
    pattern = generate_role_assessment_pattern(
        db, request("Legacy Pattern Co", "Data Analyst"), 1, llm_generator=definition
    )
    assert pattern.id == old_pattern.id
    assert pattern.source_count == 0
    assert pattern.pattern_data["source_provenance"]["generation_method"] == "llm_role_assessment"
    db.refresh(source)
    assert source.raw_data == original_source


def test_existing_pattern_or_blueprint_is_never_overwritten(db):
    existing = CompanyPattern(
        company_name="Existing Co", target_role="Data Analyst", pattern_data={"review_status": "approved"},
        source_count=0, created_by_id=1,
    )
    db.add(existing)
    db.commit()
    with pytest.raises(HTTPException) as exc:
        generate_role_assessment_pattern(db, request("Existing Co", "Data Analyst"), 2, llm_generator=definition)
    assert exc.value.detail["code"] == "ROLE_ASSESSMENT_ALREADY_EXISTS"
    db.refresh(existing)
    assert existing.pattern_data == {"review_status": "approved"}


def test_existing_approved_blueprint_blocks_role_pattern_generation(db):
    existing = CompanyBlueprint(
        company_name="Protected Co", target_role="Data Analyst", status="approved", version=4,
        confidence_level="high", evidence_sources_count=2, blueprint_data={"status": "approved", "rounds": []},
        created_by_id=1,
    )
    db.add(existing)
    db.commit()
    with pytest.raises(HTTPException) as exc:
        generate_role_assessment_pattern(db, request("Protected Co", "Data Analyst"), 2, llm_generator=definition)
    assert exc.value.detail["code"] == "ROLE_ASSESSMENT_ALREADY_EXISTS"
    db.refresh(existing)
    assert existing.status == "approved"
    assert existing.version == 4
    assert existing.blueprint_data == {"status": "approved", "rounds": []}


def test_compatible_historical_evidence_blocks_llm_path(db):
    source = CompanyHistoricalData(
        company_name="Historical Co", target_role="Data Analyst", label="drive history",
        source_type="manual", raw_data={"topics": ["SQL"]}, created_by_id=1,
    )
    db.add(source)
    db.commit()
    original = dict(source.raw_data)
    with pytest.raises(HTTPException) as exc:
        generate_role_assessment_pattern(db, request("Historical Co", "Data Analyst"), 1, llm_generator=definition)
    assert exc.value.detail["code"] == "HISTORICAL_EVIDENCE_AVAILABLE"
    db.refresh(source)
    assert source.raw_data == original
    assert db.query(CompanyPattern).count() == 0


@pytest.mark.parametrize("corruption", ["empty_topics", "missing_round", "incompatible_topics"])
def test_blueprint_path_rejects_corrupt_llm_topics_instead_of_defaulting(db, corruption):
    pattern = generate_role_assessment_pattern(
        db, request(f"Corrupt {corruption}", "Data Analyst"), 1, llm_generator=definition
    )
    review_pattern(db, pattern.company_name, pattern.target_role, "approved", None, "tpo@example.test")
    data = dict(pattern.pattern_data)
    rounds = {key: dict(value) for key, value in data["round_patterns"].items()}
    frequency = list(data["topic_frequency"])
    if corruption == "empty_topics":
        rounds["coding"]["focus_areas"] = []
        rounds["coding"]["topic_weights"] = {}
    elif corruption == "missing_round":
        rounds.pop("coding")
    else:
        rounds["coding"]["focus_areas"] = ["Incompatible topic"]
        rounds["coding"]["topic_weights"] = {"Incompatible topic": 100}
    data["round_patterns"] = rounds
    if corruption == "empty_topics":
        data["topic_frequency"] = [item for item in frequency if item["typical_round"] != "coding"]
    pattern.pattern_data = data
    db.commit()
    with pytest.raises(HTTPException):
        generate_blueprint_from_pattern(db, pattern.company_name, pattern.target_role, 1)
    assert db.query(CompanyBlueprint).count() == 0


def test_groq_role_assessment_uses_json_mode_timeout_and_rejects_malformed_json():
    captured = {}

    class FakeCompletions:
        def create(self, **kwargs):
            captured.update(kwargs)
            message = SimpleNamespace(content='{"role":"Data Analyst"}')
            return SimpleNamespace(choices=[SimpleNamespace(message=message)])

    service = GroqService.__new__(GroqService)
    service.client = SimpleNamespace(chat=SimpleNamespace(completions=FakeCompletions()))
    result = service.generate_role_assessment_definition({
        "company_name": "Example", "target_role": "Data Analyst",
        "job_description": None, "company_evidence": None,
        "rounds": [{"round_type": "aptitude", "question_count": 5, "duration_minutes": 30,
                    "difficulty_distribution": {"easy": 0.2, "medium": 0.6, "hard": 0.2}}],
    })
    assert result["role"] == "Data Analyst"
    assert captured["temperature"] == 0.1
    assert captured["max_tokens"] == 3000
    assert captured["timeout"] == 45.0
    assert captured["response_format"] == {"type": "json_object"}
    assert captured["messages"][0]["role"] == "system"

    class MalformedCompletions:
        def create(self, **kwargs):
            return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content="not json"))])

    service.client = SimpleNamespace(chat=SimpleNamespace(completions=MalformedCompletions()))
    with pytest.raises(ValueError, match="malformed role assessment JSON"):
        service.generate_role_assessment_definition({
            "company_name": "Example", "target_role": "Data Analyst",
            "rounds": [{"round_type": "aptitude", "question_count": 5, "duration_minutes": 30,
                        "difficulty_distribution": {"easy": 0.2, "medium": 0.6, "hard": 0.2}}],
        })
