from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException
from sqlalchemy import select, func
from sqlalchemy.orm import selectinload

from app.deps import AuthDep, DbDep
from app.models.db import Company, CompanyEvent
from app.models.schemas import (
    CompanyCreate, CompanyUpdate, CompanyResponse,
    StageUpdateRequest, CampaignStats, VALID_STAGES,
)

router = APIRouter(prefix="/api/campaign", tags=["campaign"])

ACTIVE_STAGES = {"RESEARCHING", "APPLIED", "SCREENING", "TECHNICAL", "ONSITE", "OFFER"}


@router.get("/companies", response_model=list[CompanyResponse])
async def list_companies(
    _: AuthDep,
    db: DbDep,
    stage: str | None = None,
    priority: str | None = None,
):
    q = select(Company).options(selectinload(Company.events)).order_by(Company.updated_at.desc())
    if stage:
        q = q.where(Company.stage == stage.upper())
    if priority:
        q = q.where(Company.priority == priority.upper())
    result = await db.execute(q)
    return result.scalars().all()


@router.post("/companies", response_model=CompanyResponse, status_code=201)
async def create_company(body: CompanyCreate, _: AuthDep, db: DbDep):
    company = Company(**body.model_dump())
    db.add(company)
    # Log creation event
    db.add(CompanyEvent(
        company=company,
        event_type="ADDED",
        description=f"Added {body.name} to pipeline",
        stage_to="RESEARCHING",
    ))
    await db.commit()
    await db.refresh(company)
    return company


@router.get("/companies/{company_id}", response_model=CompanyResponse)
async def get_company(company_id: int, _: AuthDep, db: DbDep):
    result = await db.execute(
        select(Company)
        .options(selectinload(Company.events))
        .where(Company.id == company_id)
    )
    company = result.scalar_one_or_none()
    if not company:
        raise HTTPException(status_code=404, detail="Company not found")
    return company


@router.patch("/companies/{company_id}", response_model=CompanyResponse)
async def update_company(company_id: int, body: CompanyUpdate, _: AuthDep, db: DbDep):
    result = await db.execute(select(Company).where(Company.id == company_id))
    company = result.scalar_one_or_none()
    if not company:
        raise HTTPException(status_code=404, detail="Company not found")
    for field, value in body.model_dump(exclude_none=True).items():
        setattr(company, field, value)
    await db.commit()
    await db.refresh(company)
    return company


@router.patch("/companies/{company_id}/stage", response_model=CompanyResponse)
async def update_stage(company_id: int, body: StageUpdateRequest, _: AuthDep, db: DbDep):
    if body.stage.upper() not in VALID_STAGES:
        raise HTTPException(status_code=400, detail=f"Invalid stage: {body.stage}")

    result = await db.execute(
        select(Company).options(selectinload(Company.events)).where(Company.id == company_id)
    )
    company = result.scalar_one_or_none()
    if not company:
        raise HTTPException(status_code=404, detail="Company not found")

    old_stage = company.stage
    new_stage = body.stage.upper()
    company.stage = new_stage

    if new_stage == "APPLIED" and not company.applied_at:
        company.applied_at = datetime.now(timezone.utc)
    if new_stage in ("CLOSED_WON", "CLOSED_LOST", "WITHDREW"):
        company.closed_at = datetime.now(timezone.utc)

    db.add(CompanyEvent(
        company_id=company_id,
        event_type="STAGE_CHANGE",
        description=body.description or f"Moved from {old_stage} to {new_stage}",
        stage_from=old_stage,
        stage_to=new_stage,
    ))
    await db.commit()
    await db.refresh(company)
    return company


@router.post("/companies/{company_id}/events")
async def add_event(
    company_id: int,
    event_type: str,
    description: str | None = None,
    _: AuthDep = None,
    db: DbDep = None,
):
    result = await db.execute(select(Company).where(Company.id == company_id))
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Company not found")
    db.add(CompanyEvent(
        company_id=company_id,
        event_type=event_type.upper(),
        description=description,
    ))
    await db.commit()
    return {"ok": True}


@router.delete("/companies/{company_id}", status_code=204)
async def delete_company(company_id: int, _: AuthDep, db: DbDep):
    result = await db.execute(select(Company).where(Company.id == company_id))
    company = result.scalar_one_or_none()
    if not company:
        raise HTTPException(status_code=404, detail="Company not found")
    await db.delete(company)
    await db.commit()


@router.get("/stats", response_model=CampaignStats)
async def get_stats(_: AuthDep, db: DbDep):
    result = await db.execute(select(Company))
    companies = result.scalars().all()

    active = [c for c in companies if c.stage in ACTIVE_STAGES]
    by_stage: dict[str, int] = {}
    for s in VALID_STAGES:
        by_stage[s] = sum(1 for c in companies if c.stage == s)

    applied = [c for c in companies if c.applied_at]
    responded = [
        c for c in applied
        if c.stage not in ("APPLIED",) and c.stage in ACTIVE_STAGES | {"CLOSED_WON", "CLOSED_LOST"}
    ]
    response_rate = len(responded) / len(applied) if applied else 0.0

    days_list = []
    for c in responded:
        if c.applied_at and c.updated_at:
            delta = (c.updated_at - c.applied_at).days
            if delta >= 0:
                days_list.append(delta)
    avg_days = sum(days_list) / len(days_list) if days_list else None

    return CampaignStats(
        total_active=len(active),
        by_stage=by_stage,
        response_rate=round(response_rate, 2),
        avg_days_to_response=round(avg_days, 1) if avg_days is not None else None,
        offers=by_stage.get("OFFER", 0),
    )
