import uuid
from datetime import date, datetime, timezone, timedelta
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, delete
from app.db.engine import get_db
from app.db.models import User, ExamTarget, RoadmapItem, SyllabusTopic, UserMistake, Flashcard
from app.deps import get_current_user

router = APIRouter(tags=["roadmap"])

class CreateExamTargetRequest(BaseModel):
    class_level: int = Field(ge=9, le=12)
    subject: str
    exam_date: date
    daily_minutes: int = Field(default=90, ge=15, le=600)

def schedule_revision_roadmap(
    today: date,
    exam_date: date,
    daily_minutes: int,
    topics: List[Dict[str, Any]],
    mistake_topic_ids: set,
    flashcard_mastery: Dict[str, float]
) -> List[Dict[str, Any]]:
    """
    Pure Python deterministic roadmap scheduler.
    """
    days_until_exam = (exam_date - today).days
    if days_until_exam < 0:
        raise ValueError("Exam date cannot be in the past")
    if daily_minutes < 15:
        raise ValueError("Daily minutes must be at least 15")
    if not topics:
        return []

    urgency = 1.0 + 1.0 / max(1.0, days_until_exam / 7.0)

    # Compute priority for each topic
    scored_topics = []
    for t in topics:
        t_id = t["id"]
        weight = float(t.get("weightage_marks") or 5.0)

        # Base mastery
        if t_id in mistake_topic_ids:
            mastery = 0.2
        elif t_id in flashcard_mastery:
            mastery = 0.7 * flashcard_mastery[t_id] + 0.3 * 0.5
        else:
            mastery = 0.5  # Prior when no data

        priority = weight * (1.0 - mastery) * urgency
        
        # Determine default task type
        if t_id in mistake_topic_ids:
            task_type = "drill"
        elif mastery < 0.4:
            task_type = "learn"
        else:
            task_type = "revise"

        est_min = int(min(60, max(15, round(weight * 8))))

        scored_topics.append({
            "topic_id": t_id,
            "title": t["title"],
            "weight": weight,
            "priority": priority,
            "task_type": task_type,
            "est_minutes": est_min
        })

    # Sort topics descending by priority score
    scored_topics.sort(key=lambda x: x["priority"], reverse=True)

    scheduled_items = []
    current_day = today
    topic_cursor = 0
    num_topics = len(scored_topics)

    total_plan_days = max(1, days_until_exam)

    for day_offset in range(total_plan_days):
        plan_d = today + timedelta(days=day_offset)
        remaining_days_from_plan = (exam_date - plan_d).days

        # Rule: One mock exam every 7 days
        if day_offset > 0 and day_offset % 7 == 0:
            mock_topic = scored_topics[0]
            scheduled_items.append({
                "topic_id": mock_topic["topic_id"],
                "plan_date": plan_d,
                "task_type": "mock",
                "est_minutes": min(daily_minutes, 120),
                "priority_score": round(mock_topic["priority"] * 1.5, 4)
            })
            continue

        # Rule: Last 3 days are revision-only
        is_last_3_days = (remaining_days_from_plan <= 3)
        # Rule: Last day before exam is light recap
        is_day_before_exam = (remaining_days_from_plan == 1)

        day_capacity = daily_minutes // 2 if is_day_before_exam else daily_minutes
        used_minutes = 0

        while used_minutes < day_capacity and num_topics > 0:
            top = scored_topics[topic_cursor % num_topics]
            topic_cursor += 1

            t_type = "revise" if (is_last_3_days or is_day_before_exam) else top["task_type"]
            item_min = min(top["est_minutes"], day_capacity - used_minutes)
            if item_min < 15 and used_minutes > 0:
                break

            scheduled_items.append({
                "topic_id": top["topic_id"],
                "plan_date": plan_d,
                "task_type": t_type,
                "est_minutes": max(15, item_min),
                "priority_score": round(top["priority"], 4)
            })
            used_minutes += max(15, item_min)

    return scheduled_items

@router.post("/exam-targets")
async def create_exam_target_and_plan(
    payload: CreateExamTargetRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    today = date.today()
    if payload.exam_date <= today:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Exam date must be in the future"
        )

    # Upsert ExamTarget
    target_stmt = select(ExamTarget).where(
        ExamTarget.user_id == user.id,
        ExamTarget.class_level == payload.class_level,
        ExamTarget.subject == payload.subject
    )
    target = (await db.execute(target_stmt)).scalar_one_or_none()

    if not target:
        target = ExamTarget(
            id=uuid.uuid4(),
            user_id=user.id,
            class_level=payload.class_level,
            subject=payload.subject,
            exam_date=payload.exam_date,
            daily_minutes=payload.daily_minutes,
            created_at=datetime.now(timezone.utc)
        )
        db.add(target)
        await db.flush()
    else:
        target.exam_date = payload.exam_date
        target.daily_minutes = payload.daily_minutes

    # Fetch leaf topics for subject & class
    top_stmt = select(SyllabusTopic).where(
        SyllabusTopic.class_level == payload.class_level,
        SyllabusTopic.subject == payload.subject,
        SyllabusTopic.parent_id.is_not(None)
    )
    topics_rows = (await db.execute(top_stmt)).scalars().all()
    if not topics_rows:
        # Fallback to general topics
        top_stmt2 = select(SyllabusTopic).where(SyllabusTopic.parent_id.is_not(None)).limit(20)
        topics_rows = (await db.execute(top_stmt2)).scalars().all()

    topics_data = [{"id": t.id, "title": t.title, "weightage_marks": float(t.weightage_marks or 5.0)} for t in topics_rows]

    # Fetch mistake topics
    m_stmt = select(UserMistake.topic_id).where(UserMistake.user_id == user.id, UserMistake.resolved.is_(False))
    mistake_topic_ids = set((await db.execute(m_stmt)).scalars().all())

    # Schedule plan
    plan_items = schedule_revision_roadmap(
        today=today,
        exam_date=payload.exam_date,
        daily_minutes=payload.daily_minutes,
        topics=topics_data,
        mistake_topic_ids=mistake_topic_ids,
        flashcard_mastery={}
    )

    # Preserve items with done_at set, replace uncompleted future items
    await db.execute(
        delete(RoadmapItem).where(
            RoadmapItem.exam_target_id == target.id,
            RoadmapItem.done_at.is_(None)
        )
    )

    for item in plan_items:
        r_item = RoadmapItem(
            id=uuid.uuid4(),
            user_id=user.id,
            exam_target_id=target.id,
            topic_id=item["topic_id"],
            plan_date=item["plan_date"],
            task_type=item["task_type"],
            est_minutes=item["est_minutes"],
            priority_score=item["priority_score"]
        )
        db.add(r_item)

    await db.commit()

    return {
        "target_id": str(target.id),
        "exam_date": target.exam_date.isoformat(),
        "daily_minutes": target.daily_minutes,
        "scheduled_items_count": len(plan_items)
    }

@router.get("/roadmap")
async def get_roadmap(
    target_date: Optional[date] = None,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    query_date = target_date or date.today()
    stmt = (
        select(RoadmapItem, SyllabusTopic.title)
        .join(SyllabusTopic, RoadmapItem.topic_id == SyllabusTopic.id)
        .where(
            RoadmapItem.user_id == user.id,
            RoadmapItem.plan_date == query_date
        )
        .order_by(RoadmapItem.priority_score.desc())
    )
    results = (await db.execute(stmt)).all()

    return {
        "date": query_date.isoformat(),
        "tasks": [
            {
                "id": str(item.id),
                "topic_id": str(item.topic_id),
                "topic_title": title,
                "task_type": item.task_type,
                "est_minutes": item.est_minutes,
                "priority_score": float(item.priority_score),
                "completed": item.done_at is not None
            } for item, title in results
        ]
    }
