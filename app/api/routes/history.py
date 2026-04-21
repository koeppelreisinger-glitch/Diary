from datetime import date, datetime
from typing import Optional
from fastapi import APIRouter, Query, Path

from app.core.deps import SessionDep, CurrentUser
from app.core.exceptions import ErrorResponseAPIException
from app.schemas.common import ApiResponse
from app.schemas.history import (
    HistoryListResponse,
    HistoryCalendarResponse,
    HistoryTimelineResponse,
    HistoryEventListResponse,
    HistoryTagListResponse,
    HistoryEmotionListResponse,
    HistoryLocationListResponse,
    HistoryExpenseListResponse,
)
from app.schemas.daily_record import DailyRecordDetailResponse
from app.services.history_service import HistoryService


router = APIRouter(prefix="/history", tags=["History"])

SUPPORTED_DATE_FORMATS = (
    "%Y-%m-%d",
    "%Y/%m/%d",
    "%Y.%m.%d",
    "%Y%m%d",
)


def _parse_api_date(raw_value: Optional[str], field_name: str, required: bool = False) -> Optional[date]:
    if raw_value is None:
        if required:
            raise ErrorResponseAPIException(status_code=422, detail=f"{field_name} 不能为空", code=40001)
        return None

    value = raw_value.strip()
    if not value:
        if required:
            raise ErrorResponseAPIException(status_code=422, detail=f"{field_name} 不能为空", code=40001)
        return None

    for fmt in SUPPORTED_DATE_FORMATS:
        try:
            return datetime.strptime(value, fmt).date()
        except ValueError:
            continue

    raise ErrorResponseAPIException(
        status_code=422,
        detail=f"{field_name} 格式非法，支持 YYYY-MM-DD / YYYY/MM/DD / YYYY.MM.DD / YYYYMMDD",
        code=40001,
    )


# ──────────────────────────────────────────────
# 历史记录列表
# ──────────────────────────────────────────────

@router.get("/daily-records", response_model=ApiResponse[HistoryListResponse])
async def get_history_daily_records(
    session: SessionDep,
    current_user: CurrentUser,
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=100, description="每页数量"),
    start_date: Optional[str] = Query(None, description="起始日期，支持 YYYY-MM-DD / YYYY/MM/DD / YYYY.MM.DD / YYYYMMDD"),
    end_date: Optional[str] = Query(None, description="结束日期，支持 YYYY-MM-DD / YYYY/MM/DD / YYYY.MM.DD / YYYYMMDD"),
    keyword: Optional[str] = Query(None, description="关键词模糊匹配(仅在 summary_text 中)"),
    tag: Optional[str] = Query(None, description="按有效标签名精准筛选"),
    min_emotion_score: Optional[int] = Query(None, description="最低情绪分"),
    max_emotion_score: Optional[int] = Query(None, description="最高情绪分")
):
    """
    获取历史记录列表，支持基本的分页筛选，仅返回主表轻量字段，不带子表。
    """
    start_date = _parse_api_date(start_date, "start_date")
    end_date = _parse_api_date(end_date, "end_date")

    result = await HistoryService.list_daily_records(
        session=session,
        user_id=current_user.id,
        page=page,
        page_size=page_size,
        start_date=start_date,
        end_date=end_date,
        keyword=keyword,
        tag=tag,
        min_emotion_score=min_emotion_score,
        max_emotion_score=max_emotion_score
    )
    return ApiResponse(data=result)


# ──────────────────────────────────────────────
# 指定日期详情
# ──────────────────────────────────────────────

@router.get("/daily-records/{record_date:path}", response_model=ApiResponse[DailyRecordDetailResponse])
async def get_history_daily_record_detail(
    session: SessionDep,
    current_user: CurrentUser,
    record_date: str = Path(..., description="记录日期，支持 YYYY-MM-DD / YYYY/MM/DD / YYYY.MM.DD / YYYYMMDD")
):
    """
    获取某一天的完整详情，通过 selectinload 带出五张子表的全部资源。
    """
    target_date = _parse_api_date(record_date, "record_date", required=True)

    result = await HistoryService.get_daily_record_detail_by_date(
        session=session,
        user_id=current_user.id,
        record_date=target_date
    )
    return ApiResponse(data=result)


# ──────────────────────────────────────────────
# 日历视图
# ──────────────────────────────────────────────

@router.get("/calendar", response_model=ApiResponse[HistoryCalendarResponse])
async def get_history_calendar(
    session: SessionDep,
    current_user: CurrentUser,
    year: int = Query(..., ge=2000, le=2100, description="年份"),
    month: int = Query(..., ge=1, le=12, description="月份")
):
    """
    获取日历视图，返回该月中存在记录的轻量打卡点状态，用于绘制挂历总览。
    """
    result = await HistoryService.get_calendar_view(
        session=session,
        user_id=current_user.id,
        year=year,
        month=month
    )
    return ApiResponse(data=result)


# ──────────────────────────────────────────────
# 时间轴视图
# ──────────────────────────────────────────────

@router.get("/timeline", response_model=ApiResponse[HistoryTimelineResponse])
async def get_history_timeline(
    session: SessionDep,
    current_user: CurrentUser,
    start_date: str = Query(..., description="起始日期，支持 YYYY-MM-DD / YYYY/MM/DD / YYYY.MM.DD / YYYYMMDD"),
    end_date: str = Query(..., description="结束日期，支持 YYYY-MM-DD / YYYY/MM/DD / YYYY.MM.DD / YYYYMMDD"),
    limit: int = Query(100, ge=1, le=500, description="最大返回记录条数")
):
    """
    获取历史时间轴，返回倒序记录，在 Python 层按月（YYYY-MM）分组下发。
    limit 参数防止大跨度查询拖库，默认 100，最大 500。
    """
    parsed_start_date = _parse_api_date(start_date, "start_date", required=True)
    parsed_end_date = _parse_api_date(end_date, "end_date", required=True)

    result = await HistoryService.get_timeline_view(
        session=session,
        user_id=current_user.id,
        start_date=parsed_start_date,
        end_date=parsed_end_date,
        limit=limit
    )
    return ApiResponse(data=result)


# ──────────────────────────────────────────────
# 五表主视图 — events
# ──────────────────────────────────────────────

@router.get("/events", response_model=ApiResponse[HistoryEventListResponse])
async def get_history_events(
    session: SessionDep,
    current_user: CurrentUser,
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=100, description="每页数量"),
    start_date: Optional[str] = Query(None, description="起始日期，支持 YYYY-MM-DD / YYYY/MM/DD / YYYY.MM.DD / YYYYMMDD"),
    end_date: Optional[str] = Query(None, description="结束日期，支持 YYYY-MM-DD / YYYY/MM/DD / YYYY.MM.DD / YYYYMMDD"),
    keyword: Optional[str] = Query(None, description="关键词模糊匹配事件内容")
):
    """
    跨日事件表格接口，用于记录主页下半区"事件"表格。
    每条记录包含 record_date 和 daily_record_id，前端可跳转至历史详情页。
    """
    start_date = _parse_api_date(start_date, "start_date")
    end_date = _parse_api_date(end_date, "end_date")

    result = await HistoryService.list_events(
        session=session,
        user_id=current_user.id,
        page=page,
        page_size=page_size,
        start_date=start_date,
        end_date=end_date,
        keyword=keyword
    )
    return ApiResponse(data=result)


# ──────────────────────────────────────────────
# 五表主视图 — tags
# ──────────────────────────────────────────────

@router.get("/tags", response_model=ApiResponse[HistoryTagListResponse])
async def get_history_tags(
    session: SessionDep,
    current_user: CurrentUser,
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=100, description="每页数量"),
    start_date: Optional[str] = Query(None, description="起始日期，支持 YYYY-MM-DD / YYYY/MM/DD / YYYY.MM.DD / YYYYMMDD"),
    end_date: Optional[str] = Query(None, description="结束日期，支持 YYYY-MM-DD / YYYY/MM/DD / YYYY.MM.DD / YYYYMMDD"),
    tag_name: Optional[str] = Query(None, description="按标签名精准筛选（自动去除首尾空白）")
):
    """
    跨日标签表格接口，用于记录主页下半区"标签"表格。
    每条记录包含 record_date 和 daily_record_id，前端可跳转至历史详情页。
    """
    start_date = _parse_api_date(start_date, "start_date")
    end_date = _parse_api_date(end_date, "end_date")

    result = await HistoryService.list_tags(
        session=session,
        user_id=current_user.id,
        page=page,
        page_size=page_size,
        start_date=start_date,
        end_date=end_date,
        tag_name=tag_name
    )
    return ApiResponse(data=result)


# ──────────────────────────────────────────────
# 五表主视图 — emotions
# ──────────────────────────────────────────────

@router.get("/emotions", response_model=ApiResponse[HistoryEmotionListResponse])
async def get_history_emotions(
    session: SessionDep,
    current_user: CurrentUser,
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=100, description="每页数量"),
    start_date: Optional[str] = Query(None, description="起始日期，支持 YYYY-MM-DD / YYYY/MM/DD / YYYY.MM.DD / YYYYMMDD"),
    end_date: Optional[str] = Query(None, description="结束日期，支持 YYYY-MM-DD / YYYY/MM/DD / YYYY.MM.DD / YYYYMMDD"),
    emotion_label: Optional[str] = Query(None, description="按情绪标签精准筛选"),
    min_intensity: Optional[int] = Query(None, ge=1, le=5, description="最低情绪强度 (1~5)"),
    max_intensity: Optional[int] = Query(None, ge=1, le=5, description="最高情绪强度 (1~5)")
):
    """
    跨日情绪表格接口，用于记录主页下半区"情绪"表格。
    每条记录包含 record_date 和 daily_record_id，前端可跳转至历史详情页。
    """
    start_date = _parse_api_date(start_date, "start_date")
    end_date = _parse_api_date(end_date, "end_date")

    result = await HistoryService.list_emotions(
        session=session,
        user_id=current_user.id,
        page=page,
        page_size=page_size,
        start_date=start_date,
        end_date=end_date,
        emotion_label=emotion_label,
        min_intensity=min_intensity,
        max_intensity=max_intensity
    )
    return ApiResponse(data=result)


# ──────────────────────────────────────────────
# 五表主视图 — locations
# ──────────────────────────────────────────────

@router.get("/locations", response_model=ApiResponse[HistoryLocationListResponse])
async def get_history_locations(
    session: SessionDep,
    current_user: CurrentUser,
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=100, description="每页数量"),
    start_date: Optional[str] = Query(None, description="起始日期，支持 YYYY-MM-DD / YYYY/MM/DD / YYYY.MM.DD / YYYYMMDD"),
    end_date: Optional[str] = Query(None, description="结束日期，支持 YYYY-MM-DD / YYYY/MM/DD / YYYY.MM.DD / YYYYMMDD"),
    name: Optional[str] = Query(None, description="按地点名称模糊匹配")
):
    """
    跨日地点表格接口，用于记录主页下半区"地点"表格。
    每条记录包含 record_date 和 daily_record_id，前端可跳转至历史详情页。
    """
    start_date = _parse_api_date(start_date, "start_date")
    end_date = _parse_api_date(end_date, "end_date")

    result = await HistoryService.list_locations(
        session=session,
        user_id=current_user.id,
        page=page,
        page_size=page_size,
        start_date=start_date,
        end_date=end_date,
        name=name
    )
    return ApiResponse(data=result)


# ──────────────────────────────────────────────
# 五表主视图 — expenses
# ──────────────────────────────────────────────

@router.get("/expenses", response_model=ApiResponse[HistoryExpenseListResponse])
async def get_history_expenses(
    session: SessionDep,
    current_user: CurrentUser,
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=100, description="每页数量"),
    start_date: Optional[str] = Query(None, description="起始日期，支持 YYYY-MM-DD / YYYY/MM/DD / YYYY.MM.DD / YYYYMMDD"),
    end_date: Optional[str] = Query(None, description="结束日期，支持 YYYY-MM-DD / YYYY/MM/DD / YYYY.MM.DD / YYYYMMDD"),
    category: Optional[str] = Query(None, description="按消费分类精准筛选（自动去除首尾空白）"),
    min_amount: Optional[float] = Query(None, ge=0, description="最低金额"),
    max_amount: Optional[float] = Query(None, ge=0, description="最高金额")
):
    """
    跨日消费表格接口，用于记录主页下半区"消费"表格。
    每条记录包含 record_date 和 daily_record_id，前端可跳转至历史详情页。
    """
    start_date = _parse_api_date(start_date, "start_date")
    end_date = _parse_api_date(end_date, "end_date")

    result = await HistoryService.list_expenses(
        session=session,
        user_id=current_user.id,
        page=page,
        page_size=page_size,
        start_date=start_date,
        end_date=end_date,
        category=category,
        min_amount=min_amount,
        max_amount=max_amount
    )
    return ApiResponse(data=result)
