import json
import uuid
from fastapi import APIRouter
from fastapi.responses import StreamingResponse

from app.agents.base import classify_intent, get_agent
from app.deps import AuthDep, MemoryDep
from app.models.schemas import ChatRequest

router = APIRouter(prefix="/api/chat", tags=["chat"])


async def _event_stream(body: ChatRequest, memory):
    session_id = body.session_id or str(uuid.uuid4())
    history = [m.model_dump() for m in body.history]

    # 1. Classify intent
    intent = await classify_intent(body.message, history)
    yield f"event: intent\ndata: {json.dumps({'intent': intent, 'session_id': session_id})}\n\n"

    # 2. Load memory context
    ctx = memory.load_context(intent)

    # 3. Get the right agent
    agent = get_agent(intent, memory)

    # 4. Stream the response
    full_response = []
    async for token in agent.stream(body.message, history, ctx):
        full_response.append(token)
        yield f"event: token\ndata: {json.dumps({'text': token})}\n\n"

    # 5. Post-process: propose memory updates
    complete_response = "".join(full_response)
    updates = await agent.post_process(complete_response, body.message, ctx)

    payload = {
        "intent": intent,
        "session_id": session_id,
        "proposed_updates": [u.model_dump() for u in updates],
    }
    yield f"event: complete\ndata: {json.dumps(payload)}\n\n"


@router.post("")
async def chat(body: ChatRequest, _: AuthDep, memory: MemoryDep):
    return StreamingResponse(
        _event_stream(body, memory),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )
