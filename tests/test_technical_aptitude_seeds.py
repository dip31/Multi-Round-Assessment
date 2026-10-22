from sqlalchemy import create_engine, func
from sqlalchemy.orm import sessionmaker

from app.models.aptitude import AptitudeQuestion, AptitudeTopic
from seed_all_questions import seed_technical_aptitude_questions


def test_technical_aptitude_seed_creates_selector_topics_idempotently():
    engine = create_engine("sqlite:///:memory:")
    AptitudeTopic.__table__.create(engine)
    AptitudeQuestion.__table__.create(engine)
    session = sessionmaker(bind=engine)()
    expected_topics = {
        "Operating Systems",
        "Computer Networks",
        "Object-Oriented Programming",
        "Database Management Systems",
        "Data Structures",
    }

    seed_technical_aptitude_questions(session)
    seed_technical_aptitude_questions(session)

    topic_counts = dict(
        session.query(AptitudeTopic.name, func.count(AptitudeQuestion.id))
        .join(AptitudeQuestion)
        .group_by(AptitudeTopic.name)
        .all()
    )
    assert expected_topics <= topic_counts.keys()
    assert all(topic_counts[topic] == 1 for topic in expected_topics)
    session.close()
    engine.dispose()
