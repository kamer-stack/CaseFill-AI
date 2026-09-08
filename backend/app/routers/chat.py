"""
Help chatbot and routing endpoints.
"""

from fastapi import APIRouter, Depends

from ..models import ChatRequest, RouteRequest
from ..services.chatbot import chat_completion
from ..services.routing_engine import route_address
from .auth import get_current_user

router = APIRouter(tags=["ai-services"])


@router.post("/api/help-chat")
def help_chat(req: ChatRequest, user: dict = Depends(get_current_user)):
    """AI help chatbot endpoint."""
    reply = chat_completion(
        message=req.message,
        history=req.history,
        current_role=req.current_role,
        current_task=req.current_task,
        task_label=req.task_label,
        active_step=req.active_step,
        case_context=req.case_context,
    )
    return {"reply": reply}


@router.post("/api/route-region")
def route_region(req: RouteRequest, user: dict = Depends(get_current_user)):
    """AI-based address to region routing."""
    result = route_address(req.address)
    return result
