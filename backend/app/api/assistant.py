"""VigilAI endpoints.  The Gemini API is only ever called from here (server side)."""
from __future__ import annotations

from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.assistant import service as assistant_service
from app.core.config import settings
from app.core.database import get_db
from app.core.permissions import require_permission
from app.models.models import User
from app.schemas.schemas import ChatRequest, ChatResponse

router = APIRouter(prefix="/assistant", tags=["VigilAI"])


@router.get("/status")
def assistant_status(
    db: Session = Depends(get_db),
    _user: User = Depends(require_permission("assistant:use")),
) -> Dict[str, Any]:
    return assistant_service.status(db)


@router.post("/chat", response_model=ChatResponse, responses={429: {"description": "Rate limited"}})
def assistant_chat(
    payload: ChatRequest,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("assistant:use")),
) -> Dict[str, Any]:
    """Ask VigilAI a question.  Answers are read-only and limited to the VigilOps platform."""
    if len(payload.message.strip()) > settings.AI_MAX_INPUT_CHARS:
        raise HTTPException(
            status_code=422,
            detail=f"The message is too long (maximum {settings.AI_MAX_INPUT_CHARS} characters).",
        )
    try:
        return assistant_service.chat(
            db, user, payload.message, [turn.model_dump() for turn in payload.history]
        )
    except assistant_service.AssistantRateLimited as exc:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"You are sending messages too quickly. Try again in {exc.retry_after} seconds.",
            headers={"Retry-After": str(exc.retry_after)},
        )
