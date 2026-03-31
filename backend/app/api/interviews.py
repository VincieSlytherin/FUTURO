import json
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.deps import AuthDep, DbDep, MemoryDep
from app.models.db import Interview, Company, CompanyEvent
from app.models.schemas import InterviewCreate, DebriefRequest, InterviewResponse

router = APIRouter(prefix="/api/interviews", tags=["interviews"])


@router.get("", response_model=list[InterviewResponse])
async def list_interviews(_: AuthDep, db: DbDep):
    result = await db.execute(
        select(Interview).order_by(Interview.scheduled_at.desc())
    )
    return result.scalars().all()


@router.post("", response_model=InterviewResponse, status_code=201)
async def create_interview(body: InterviewCreate, _: AuthDep, db: DbDep):
    result = await db.execute(select(Company).where(Company.id == body.company_id))
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Company not found")

    interview = Interview(**body.model_dump())
    db.add(interview)

    db.add(CompanyEvent(
        company_id=body.company_id,
        event_type="INTERVIEW_SCHEDULED",
        description=f"{body.round_name} scheduled",
    ))
    await db.commit()
    await db.refresh(interview)
    return interview


@router.post("/{interview_id}/debrief")
async def debrief(
    interview_id: int,
    body: DebriefRequest,
    _: AuthDep,
    db: DbDep,
    memory: MemoryDep,
):
    result = await db.execute(
        select(Interview).options(selectinload(Interview.company)).where(Interview.id == interview_id)
    )
    interview = result.scalar_one_or_none()
    if not interview:
        raise HTTPException(status_code=404, detail="Interview not found")

    # Persist debrief fields
    interview.questions_asked = json.dumps(body.questions_asked)
    interview.strong_moments = body.strong_moments
    interview.weak_moments = body.weak_moments
    interview.gut_feeling = body.gut_feeling
    interview.my_answers = body.notes
    await db.commit()

    # Build debrief message and stream through DEBRIEF agent
    from app.agents.base import get_agent
    agent = get_agent("DEBRIEF", memory)
    ctx = memory.load_context("DEBRIEF")

    debrief_msg = (
        f"I just finished an interview at {interview.company.name} — {interview.round_name}.\n\n"
        f"Questions asked: {', '.join(body.questions_asked) if body.questions_asked else 'not listed'}\n"
        f"What felt strong: {body.strong_moments or 'not noted'}\n"
        f"What felt weak: {body.weak_moments or 'not noted'}\n"
        f"Gut feeling: {body.gut_feeling}/5\n"
        f"Additional notes: {body.notes or 'none'}"
    )

    async def _stream():
        async for token in agent.stream(debrief_msg, [], ctx):
            yield f"event: token\ndata: {json.dumps({'text': token})}\n\n"
        yield f"event: complete\ndata: {json.dumps({'interview_id': interview_id})}\n\n"

    return StreamingResponse(_stream(), media_type="text/event-stream")


@router.get("/patterns")
async def get_patterns(_: AuthDep, db: DbDep):
    result = await db.execute(select(Interview))
    interviews = result.scalars().all()
    return {
        "total_interviews": len(interviews),
        "with_debrief": sum(1 for i in interviews if i.strong_moments or i.weak_moments),
        "avg_gut_feeling": (
            round(sum(i.gut_feeling for i in interviews if i.gut_feeling) /
                  max(1, sum(1 for i in interviews if i.gut_feeling)), 1)
        ),
    }
