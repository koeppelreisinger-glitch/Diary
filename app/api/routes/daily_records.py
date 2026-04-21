import uuid
from fastapi import APIRouter

from app.core.deps import SessionDep, CurrentUser
from app.schemas.common import ApiResponse
from app.schemas.daily_record import (
    TodayDailyRecordResponse,
    DailyRecordDetailResponse,
    UpdateDailyRecordRequest,
    UpdateDailyRecordBodyRequest,
    SaveSupplementRequest,
    CreateManualRecordRequest,
)
from app.services.daily_record_service import DailyRecordService

router = APIRouter()


@router.get("/daily-records/today", response_model=ApiResponse[TodayDailyRecordResponse], tags=["Daily Records"])
async def get_today_record(
    session: SessionDep,
    current_user: CurrentUser
):
    """获取今日总结详情（含 body_text 正文）；若仍在生成中则返回等待状态"""
    resp = await DailyRecordService.get_today_record(session, current_user.id)
    return ApiResponse(data=resp)


@router.post("/daily-records/manual", response_model=ApiResponse[DailyRecordDetailResponse], tags=["Daily Records"])
async def create_manual_record(
    request: CreateManualRecordRequest,
    session: SessionDep,
    current_user: CurrentUser
):
    """
    补录日记：从正文内容直接为指定日期创建日记记录。
    适合在「今日」页底部弹层为过往无记录日期手动补录。
    - 若该日期已有记录，返回 400。
    - 成功时同步提取结构化数据（事件/情绪/消费/地点/标签）并返回完整 DailyRecordDetailResponse。
    """
    resp = await DailyRecordService.create_from_manual_body(session, current_user.id, request)
    return ApiResponse(data=resp)


@router.put("/daily-records/{record_id}", response_model=ApiResponse[DailyRecordDetailResponse], tags=["Daily Records"])
async def update_record(
    record_id: uuid.UUID,
    request: UpdateDailyRecordRequest,
    session: SessionDep,
    current_user: CurrentUser
):
    """轻量标注编辑：更新 user_note、keywords 及标签增删。不触发结构化重建。"""
    resp = await DailyRecordService.update_record(session, current_user.id, record_id, request)
    return ApiResponse(data=resp)


@router.put("/daily-records/{record_id}/body", response_model=ApiResponse[DailyRecordDetailResponse], tags=["Daily Records"])
async def update_record_body(
    record_id: uuid.UUID,
    request: UpdateDailyRecordBodyRequest,
    session: SessionDep,
    current_user: CurrentUser
):
    """
    Path A — 手动改正文：
    - 更新 body_text
    - 同步重新派生 summary_text / emotion_overall_score / keywords
    - 全量软删旧结构化子表（保留用户手动加的 tags），重新提取写入
    - 整个过程在同一事务内，失败则全量回滚
    """
    resp = await DailyRecordService.update_body(session, current_user.id, record_id, request)
    return ApiResponse(data=resp)


@router.post("/daily-records/{record_id}/supplement", response_model=ApiResponse[DailyRecordDetailResponse], tags=["Daily Records"])
async def save_supplement(
    record_id: uuid.UUID,
    request: SaveSupplementRequest,
    session: SessionDep,
    current_user: CurrentUser
):
    """
    Path B — 保存本次补充 / AI 重新生成：
    - 从关联 conversation 的完整消息历史中重新生成 body_text
    - 若 conversation 无消息（如手动补录 / 直接点 AI 重新生成），则基于现有 body_text 做风格变化重建
    - 全量重建 summary_text / 五子表（与 Path A 共用 DiaryRebuildService）
    - 整个过程在同一事务内，失败则全量回滚
    """
    resp = await DailyRecordService.save_supplement(session, current_user.id, record_id, request)
    return ApiResponse(data=resp)


# ── 开发工具（保留原有 mock 接口） ─────────────────────────────────

from sqlalchemy import select
from app.models.conversation import Conversation
from app.models.daily_record import DailyRecord, RecordTag, RecordEvent, RecordEmotion, RecordExpense, RecordLocation
from app.models.base import utc_now


@router.post("/dev/mock-summary/{conversation_id}", tags=["Dev Tool"])
async def dev_mock_generate_summary(
    conversation_id: uuid.UUID,
    session: SessionDep,
    current_user: CurrentUser
):
    """[开发工具] 一键将正在 completing 的会话打入假数据闭环（同时写 body_text）"""
    conv_stmt = select(Conversation).where(
        Conversation.id == conversation_id,
        Conversation.user_id == current_user.id
    )
    conv = (await session.execute(conv_stmt)).scalar_one_or_none()

    if not conv or conv.status != "completing":
        return ApiResponse(code=40000, message="找不到该会话或其状态不处于 completing 中")

    body_text_value = "这是一段测试总结，工作充实，感觉不错。"
    dr = DailyRecord(
        user_id=current_user.id,
        conversation_id=conversation_id,
        record_date=conv.record_date,
        body_text=body_text_value,
        summary_text=body_text_value,
        emotion_overall_score=8,
        keywords=["测试", "Mock生成", "成就感"]
    )
    session.add(dr)
    await session.commit()
    await session.refresh(dr)

    session.add_all([
        RecordEvent(record_id=dr.id, user_id=current_user.id, content="测试事件A", source="ai"),
        RecordEmotion(record_id=dr.id, user_id=current_user.id, emotion_label="兴奋", intensity=5, source="ai"),
        RecordExpense(record_id=dr.id, user_id=current_user.id, amount=12.5, category="餐饮", source="ai"),
        RecordLocation(record_id=dr.id, user_id=current_user.id, name="静安寺附近", source="ai"),
        RecordTag(record_id=dr.id, user_id=current_user.id, tag_name="开发中", source="ai")
    ])

    conv.status = "completed"
    await session.commit()

    return ApiResponse(code=20000, message="Mock结构化数据落地完毕！")
