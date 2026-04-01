from pydantic import BaseModel
from fastapi import APIRouter

from app.config import settings
from app.custom_instructions import CustomInstructionManager, INSTRUCTION_KEYS
from app.deps import AuthDep

router = APIRouter(prefix="/api/instructions", tags=["instructions"])


class InstructionConfigRequest(BaseModel):
    global_instruction: str = ""
    general_instruction: str = ""
    bq_instruction: str = ""
    story_instruction: str = ""
    resume_instruction: str = ""
    debrief_instruction: str = ""
    strategy_instruction: str = ""
    scout_instruction: str = ""
    intake_instruction: str = ""


def _manager() -> CustomInstructionManager:
    return CustomInstructionManager(settings.custom_instructions_path)


def _to_payload(data: dict[str, str]) -> dict[str, str]:
    return {
        "global_instruction": data["global"],
        "general_instruction": data["GENERAL"],
        "bq_instruction": data["BQ"],
        "story_instruction": data["STORY"],
        "resume_instruction": data["RESUME"],
        "debrief_instruction": data["DEBRIEF"],
        "strategy_instruction": data["STRATEGY"],
        "scout_instruction": data["SCOUT"],
        "intake_instruction": data["INTAKE"],
    }


@router.get("")
async def get_instructions(_: AuthDep):
    return _to_payload(_manager().load())


@router.put("")
async def update_instructions(body: InstructionConfigRequest, _: AuthDep):
    saved = _manager().save({
        "global": body.global_instruction,
        "GENERAL": body.general_instruction,
        "BQ": body.bq_instruction,
        "STORY": body.story_instruction,
        "RESUME": body.resume_instruction,
        "DEBRIEF": body.debrief_instruction,
        "STRATEGY": body.strategy_instruction,
        "SCOUT": body.scout_instruction,
        "INTAKE": body.intake_instruction,
    })
    return {"saved": True, **_to_payload(saved)}
