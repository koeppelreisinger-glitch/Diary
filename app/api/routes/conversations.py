import uuid
from typing import Optional
from fastapi import APIRouter, Query

from app.core.deps import SessionDep, CurrentUser
from app.schemas.common import ApiResponse
from app.schemas.conversation import (
    TodayConversationResponse,
    CreateConversationResponse,
    MessageListResponse,
    SendMessageRequest,
    SendMessageResponse,
    CompleteConversationResponse
)
from app.services.conversation_service import ConversationService

router = APIRouter()


@router.get("/conversations/today", response_model=ApiResponse[TodayConversationResponse], tags=["Conversations"])
async def get_today_conversation(
    session: SessionDep,
    current_user: CurrentUser
):
    """获取今天的会话状态；若今日尚无会话，返回空状态而非 404"""
    resp = await ConversationService.get_today_conversation(session, current_user.id)
    return ApiResponse(data=resp)


@router.post("/conversations", response_model=ApiResponse[CreateConversationResponse], tags=["Conversations"])
async def create_today_conversation(
    session: SessionDep,
    current_user: CurrentUser
):
    """创建今天的会话；今日会话已存在时返回 409"""
    resp = await ConversationService.create_today_conversation(session, current_user.id)
    return ApiResponse(data=resp)


@router.get("/conversations/{conversation_id}/messages", response_model=ApiResponse[MessageListResponse], tags=["Conversations"])
async def get_messages(
    conversation_id: uuid.UUID,
    session: SessionDep,
    current_user: CurrentUser,
    limit: int = Query(50, le=100),
    before_sequence: Optional[int] = Query(None)
):
    """获取指定会话的消息列表，按 sequence_number 升序排列"""
    resp = await ConversationService.get_messages(session, conversation_id, current_user.id, limit, before_sequence)
    return ApiResponse(data=resp)


@router.post("/conversations/{conversation_id}/messages", response_model=ApiResponse[SendMessageResponse], tags=["Conversations"])
async def send_message(
    conversation_id: uuid.UUID,
    request: SendMessageRequest,
    session: SessionDep,
    current_user: CurrentUser
):
    """
    发送用户消息，同步返回 AI 回复。

    Phase 2 补写通道：当 is_supplement=true 时，已 completed 的会话也允许继续接收消息。
    - completed + is_supplement=true  → 允许，AI 正常回复
    - completed + is_supplement=false → 409（旧行为）
    - completing（任何情况）          → 409
    """
    resp = await ConversationService.send_message(session, conversation_id, current_user.id, request)
    return ApiResponse(data=resp)


@router.post("/conversations/{conversation_id}/complete", response_model=ApiResponse[CompleteConversationResponse], tags=["Conversations"])
async def complete_conversation(
    conversation_id: uuid.UUID,
    session: SessionDep,
    current_user: CurrentUser
):
    """结束今日记录，并直接连通总结服务完成日记录分析和入库闭环"""
    resp = await ConversationService.complete_conversation(session, conversation_id, current_user.id)
    return ApiResponse(data=resp)
