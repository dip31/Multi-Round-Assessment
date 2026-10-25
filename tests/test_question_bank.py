"""Tests for the EDI5 Question Bank seeding and selection."""

import pytest
from sqlalchemy.orm import Session

from app.database.db import SessionLocal
from app.models.aptitude import AptitudeQuestion, AptitudeTopic
from app.models.coding import CodingProblem, CodingTestCase
from app.models.question_competency_mapping import (
    QuestionCompetencyMapping, SOURCE_TYPE_APTITUDE, SOURCE_TYPE_CODING
)
from app.skills.taxonomy import (
    SKILLS, normalize_skill, get_skills_for_round, get_competencies_for_skill
)
from app.modules.aptitude.services.question_selector import (
    select_question_by_skills,
    select_question_by_competencies,
    select_coding_problem_by_skills,
    resolve_skill_competencies,
    get_competency_coverage,
)


@pytest.fixture
def db() -> Session:
    """Provide a database session for tests."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


class TestSkillTaxonomy:
    """Test the canonical skill taxonomy."""
    
    def test_all_skills_have_code_and_name(self):
        for code, skill in SKILLS.items():
            assert skill.code == code
            assert skill.name
            assert skill.category
            assert isinstance(skill.competencies, list)
    
    def test_normalize_skill_known_aliases(self):
        assert normalize_skill("Python") == "python"
        assert normalize_skill("JS") == "javascript"
        assert normalize_skill("TS") == "typescript"
        assert normalize_skill("React.js") == "react"
        assert normalize_skill("Postgres") == "sql"
        assert normalize_skill("DSA") == "data_structures_algorithms"
        assert normalize_skill("OOP") == "oop"
        assert normalize_skill("OS") == "operating_systems"
        assert normalize_skill("CN") == "computer_networks"
        assert normalize_skill("DBMS") == "dbms"
    
    def test_normalize_skill_unknown_returns_none(self):
        assert normalize_skill("UnknownSkill") is None
        assert normalize_skill("") is None
        assert normalize_skill("   ") is None
    
    def test_round_skill_mapping(self):
        aptitude_skills = get_skills_for_round("aptitude")
        assert "quantitative_aptitude" in aptitude_skills
        assert "logical_reasoning" in aptitude_skills
        assert "verbal_ability" in aptitude_skills
        
        technical_skills = get_skills_for_round("technical")
        assert "operating_systems" in technical_skills
        assert "data_structures_algorithms" in technical_skills
        
        coding_skills = get_skills_for_round("coding")
        assert "data_structures_algorithms" in coding_skills
        assert "python" in coding_skills


class TestQuestionBankSeeding:
    """Test that the question bank has been properly seeded."""
    
    def test_aptitude_questions_exist(self, db: Session):
        count = db.query(AptitudeQuestion).filter(AptitudeQuestion.is_active == True).count()
        assert count >= 90, f"Expected at least 90 aptitude questions, got {count}"
    
    def test_coding_problems_exist(self, db: Session):
        count = db.query(CodingProblem).count()
        assert count >= 30, f"Expected at least 30 coding problems, got {count}"
    
    def test_aptitude_topics_exist(self, db: Session):
        topics = db.query(AptitudeTopic).all()
        topic_names = {t.name for t in topics}
        expected_topics = {
            "Quantitative Aptitude", "Logical Reasoning", "Verbal Ability",
            "Data Interpretation", "Operating Systems", "Computer Networks",
            "DBMS", "Object Oriented Programming", "Data Structures & Algorithms"
        }
        for expected in expected_topics:
            assert expected in topic_names, f"Missing topic: {expected}"
    
    def test_competency_mappings_exist(self, db: Session):
        count = db.query(QuestionCompetencyMapping).count()
        assert count >= 100, f"Expected at least 100 competency mappings, got {count}"
    
    def test_aptitude_questions_have_mappings(self, db: Session):
        """Verify each aptitude question has at least one competency mapping."""
        questions = db.query(AptitudeQuestion).filter(AptitudeQuestion.is_active == True).all()
        for q in questions:
            mappings = db.query(QuestionCompetencyMapping).filter(
                QuestionCompetencyMapping.source_type == SOURCE_TYPE_APTITUDE,
                QuestionCompetencyMapping.source_id == q.id
            ).count()
            assert mappings >= 1, f"Question {q.id} has no competency mapping"
    
    def test_coding_problems_have_mappings(self, db: Session):
        """Verify each coding problem has at least one competency mapping."""
        problems = db.query(CodingProblem).all()
        for p in problems:
            mappings = db.query(QuestionCompetencyMapping).filter(
                QuestionCompetencyMapping.source_type == SOURCE_TYPE_CODING,
                QuestionCompetencyMapping.source_id == p.id
            ).count()
            assert mappings >= 1, f"Coding problem {p.id} ({p.title}) has no competency mapping"
    
    def test_coding_problems_have_test_cases(self, db: Session):
        """Verify each coding problem has test cases."""
        problems = db.query(CodingProblem).all()
        for p in problems:
            tc_count = db.query(CodingTestCase).filter(CodingTestCase.problem_id == p.id).count()
            assert tc_count >= 2, f"Coding problem {p.id} ({p.title}) has only {tc_count} test cases"
            
            # Check for hidden test cases
            hidden_count = db.query(CodingTestCase).filter(
                CodingTestCase.problem_id == p.id,
                CodingTestCase.is_hidden == True
            ).count()
            assert hidden_count >= 1, f"Coding problem {p.id} has no hidden test cases"


class TestCompetencyCoverage:
    """Test competency coverage for different skill sets."""
    
    def test_aptitude_full_coverage(self, db: Session):
        coverage = get_competency_coverage(db, ["quantitative_aptitude", "logical_reasoning"], "aptitude")
        assert coverage["coverage_pct"] == 100.0, f"Aptitude coverage should be 100%, got {coverage['coverage_pct']}%"
    
    def test_technical_good_coverage(self, db: Session):
        coverage = get_competency_coverage(db, ["operating_systems", "data_structures_algorithms"], "technical")
        assert coverage["coverage_pct"] >= 75.0, f"Technical coverage should be >= 75%, got {coverage['coverage_pct']}%"
    
    def test_coding_good_coverage(self, db: Session):
        coverage = get_competency_coverage(db, ["python", "data_structures_algorithms"], "coding")
        assert coverage["coverage_pct"] >= 80.0, f"Coding coverage should be >= 80%, got {coverage['coverage_pct']}%"


class TestQuestionSelection:
    """Test question selection by skills and competencies."""
    
    def test_select_aptitude_by_skills(self, db: Session):
        question = select_question_by_skills(db, ["quantitative_aptitude", "logical_reasoning"], "aptitude", "easy")
        assert question is not None
        assert question.difficulty == "easy"
        assert question.topic.name in ["Quantitative Aptitude", "Logical Reasoning"]
    
    def test_select_technical_by_skills(self, db: Session):
        question = select_question_by_skills(db, ["operating_systems", "data_structures_algorithms"], "technical", "medium")
        assert question is not None
        assert question.topic.name in ["Operating Systems", "Data Structures & Algorithms"]
    
    def test_select_by_competencies(self, db: Session):
        question = select_question_by_competencies(db, ["QUANT_EASY", "LOGIC_EASY"], "easy")
        assert question is not None
        assert question.difficulty == "easy"
    
    def test_select_coding_by_skills(self, db: Session):
        problem = select_coding_problem_by_skills(db, ["python", "data_structures_algorithms"], "easy")
        assert problem is not None
        assert problem.difficulty == "easy"
        # Problem should have some tags (either DSA tags like array/string or Python tags)
        assert problem.tags_list is not None and len(problem.tags_list) > 0
    
    def test_exclude_ids_works(self, db: Session):
        # Get first question
        q1 = select_question_by_skills(db, ["quantitative_aptitude"], "aptitude", "easy")
        assert q1 is not None
        
        # Exclude it and get another
        q2 = select_question_by_skills(db, ["quantitative_aptitude"], "aptitude", "easy", exclude_ids=[q1.id])
        assert q2 is not None
        assert q2.id != q1.id
    
    def test_resolve_skill_competencies(self):
        competencies = resolve_skill_competencies(["python", "data_structures_algorithms"], "coding")
        assert "PY_BASICS" in competencies
        assert "PY_ADVANCED" in competencies
        assert "DSA_ARRAYS" in competencies
        assert "DSA_HASHING" in competencies
    
    def test_resolve_skill_competencies_filters_by_round(self):
        # DSA competencies should appear in both technical and coding
        tech_comps = resolve_skill_competencies(["data_structures_algorithms"], "technical")
        coding_comps = resolve_skill_competencies(["data_structures_algorithms"], "coding")
        
        # Both should have DSA competencies
        assert "DSA_ARRAYS" in tech_comps
        assert "DSA_ARRAYS" in coding_comps
        
        # But python competencies only in coding
        python_comps = resolve_skill_competencies(["python"], "coding")
        assert "PY_BASICS" in python_comps
        
        python_tech_comps = resolve_skill_competencies(["python"], "technical")
        assert "PY_BASICS" not in python_tech_comps  # Python not in technical round


class TestIdempotentSeeding:
    """Test that seeding is idempotent (running twice doesn't create duplicates)."""
    
    def test_seed_script_is_idempotent(self, db: Session):
        """Verify no duplicate questions exist."""
        # Check for duplicate aptitude questions (same text + topic)
        from sqlalchemy import func
        duplicates = db.query(
            AptitudeQuestion.question_text,
            AptitudeQuestion.topic_id,
            func.count(AptitudeQuestion.id).label('count')
        ).group_by(
            AptitudeQuestion.question_text,
            AptitudeQuestion.topic_id
        ).having(func.count(AptitudeQuestion.id) > 1).all()
        
        assert len(duplicates) == 0, f"Found {len(duplicates)} duplicate aptitude questions"
        
        # Check for duplicate coding problems (same title)
        coding_duplicates = db.query(
            CodingProblem.title,
            func.count(CodingProblem.id).label('count')
        ).group_by(CodingProblem.title).having(func.count(CodingProblem.id) > 1).all()
        
        assert len(coding_duplicates) == 0, f"Found {len(coding_duplicates)} duplicate coding problems"
        
        # Check for duplicate competency mappings
        mapping_duplicates = db.query(
            QuestionCompetencyMapping.source_type,
            QuestionCompetencyMapping.source_id,
            QuestionCompetencyMapping.competency_code,
            func.count(QuestionCompetencyMapping.id).label('count')
        ).group_by(
            QuestionCompetencyMapping.source_type,
            QuestionCompetencyMapping.source_id,
            QuestionCompetencyMapping.competency_code
        ).having(func.count(QuestionCompetencyMapping.id) > 1).all()
        
        assert len(mapping_duplicates) == 0, f"Found {len(mapping_duplicates)} duplicate competency mappings"


class TestQuestionQuality:
    """Test question quality requirements."""
    
    def test_aptitude_questions_have_valid_structure(self, db: Session):
        questions = db.query(AptitudeQuestion).filter(AptitudeQuestion.is_active == True).all()
        for q in questions:
            assert q.question_text and len(q.question_text) > 10
            assert q.option_a and q.option_b and q.option_c and q.option_d
            assert q.correct_option in ["A", "B", "C", "D"]
            assert q.difficulty in ["easy", "medium", "hard"]
            assert q.topic_id is not None
    
    def test_coding_problems_have_valid_structure(self, db: Session):
        problems = db.query(CodingProblem).all()
        for p in problems:
            assert p.title and len(p.title) > 3
            assert p.description and len(p.description) > 20
            assert p.difficulty in ["easy", "medium", "hard"]
            assert p.input_format
            assert p.output_format
    
    def test_no_duplicate_questions_across_topics(self, db: Session):
        """Ensure the same question text doesn't appear in multiple topics."""
        from sqlalchemy import func
        duplicates = db.query(
            AptitudeQuestion.question_text,
            func.count(AptitudeQuestion.topic_id).label('topic_count')
        ).group_by(AptitudeQuestion.question_text).having(func.count(AptitudeQuestion.topic_id) > 1).all()
        
        # Some questions might legitimately be in multiple topics, but very few
        assert len(duplicates) <= 2, f"Found {len(duplicates)} questions appearing in multiple topics"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])