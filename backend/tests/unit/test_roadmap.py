import pytest
from datetime import date, timedelta
from app.features.roadmap import schedule_revision_roadmap

def test_roadmap_deterministic_generation():
    today = date(2026, 11, 1)
    exam_date = date(2026, 11, 20)  # 19 days
    daily_minutes = 90
    topics = [
        {"id": "t1", "title": "Calculus", "weightage_marks": 10.0},
        {"id": "t2", "title": "Vectors", "weightage_marks": 7.0},
        {"id": "t3", "title": "Algebra", "weightage_marks": 5.0}
    ]

    plan = schedule_revision_roadmap(
        today=today,
        exam_date=exam_date,
        daily_minutes=daily_minutes,
        topics=topics,
        mistake_topic_ids={"t1"},
        flashcard_mastery={}
    )

    assert len(plan) > 0
    # Highest priority mistake topic t1 should be scheduled with task_type 'drill'
    t1_drills = [item for item in plan if item["topic_id"] == "t1" and item["task_type"] == "drill"]
    assert len(t1_drills) > 0

def test_roadmap_last_days_revision():
    """Last 3 days are revision-only."""
    today = date(2026, 11, 1)
    exam_date = date(2026, 11, 4)  # 3 days remaining
    topics = [{"id": "t1", "title": "Topic A", "weightage_marks": 5.0}]

    plan = schedule_revision_roadmap(
        today=today,
        exam_date=exam_date,
        daily_minutes=60,
        topics=topics,
        mistake_topic_ids=set(),
        flashcard_mastery={}
    )
    for item in plan:
        assert item["task_type"] == "revise"

def test_roadmap_past_date_raises_error():
    today = date(2026, 11, 10)
    past_exam = date(2026, 11, 1)
    with pytest.raises(ValueError, match="Exam date cannot be in the past"):
        schedule_revision_roadmap(today, past_exam, 90, [], set(), {})
