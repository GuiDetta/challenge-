from fastapi import APIRouter, Depends, Query

from app.schemas import AssistantChatRequest, AssistantChatResponse
from app.services.assistant_service import AssistantService
from app.services.container import get_assistant_service

router = APIRouter(prefix="/api/assistant", tags=["assistant"])


@router.get("/alerts")
def alerts(owner_id: str = Query(..., min_length=1), service: AssistantService = Depends(get_assistant_service)) -> dict[str, list[str]]:
    return {"alerts": service.alerts(service.context(owner_id))}


@router.post("/chat", response_model=AssistantChatResponse)
def chat(request: AssistantChatRequest, service: AssistantService = Depends(get_assistant_service)) -> AssistantChatResponse:
    return service.chat(request)
